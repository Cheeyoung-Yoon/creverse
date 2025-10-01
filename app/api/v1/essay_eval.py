import os
import time
import asyncio
import logging
import traceback
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Optional, Any, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, Response, BackgroundTasks

from app.client.bootstrap import build_llm
from app.models.request import EssayEvalRequest
from app.models.response import EssayEvalResponse
from app.services.essay_evaluator import EssayEvaluator
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM
from app.core.async_manager import (
    get_connection_pool, 
    get_task_manager, 
    async_timeout,
    async_retry
)
from app.core.dependencies import (
    get_async_llm,
    get_async_prompt_loader,
    get_performance_monitor,
    PerformanceMonitor
)

logger = logging.getLogger(__name__)

# Constants for better readability
MAX_EVALUATION_TIMEOUT = 1000.0  # seconds
MAX_PING_TIMEOUT = 45.0  # seconds
MAX_RETRY_ATTEMPTS = 2
RETRY_DELAY = 1.0  # seconds
VALIDATION_TIMEOUT = 15.0  # seconds
METRICS_TIMEOUT = 300.0  # seconds

# HTTP Status constants
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_REQUEST_TIMEOUT = 408

# Custom Exception Classes
class EvaluationException(Exception):
    """Base exception for evaluation errors"""
    def __init__(self, message: str, details: dict = None, error_code: str = "EVALUATION_ERROR"):
        self.message = message
        self.details = details or {}
        self.error_code = error_code
        super().__init__(message)

class ValidationException(EvaluationException):
    """Input validation errors"""
    def __init__(self, message: str, field: str = None, details: dict = None):
        self.field = field
        super().__init__(message, details, "VALIDATION_ERROR")

class PromptLoadException(EvaluationException):
    """Prompt loading errors"""
    def __init__(self, message: str, version: str = None, details: dict = None):
        self.version = version
        super().__init__(message, details, "PROMPT_LOAD_ERROR")

class LLMConnectionException(EvaluationException):
    """LLM connection and API errors"""
    def __init__(self, message: str, details: dict = None, retry_after: int = 30):
        self.retry_after = retry_after
        super().__init__(message, details, "LLM_CONNECTION_ERROR")

class TokenLimitException(EvaluationException):
    """Token limit exceeded errors"""
    def __init__(self, message: str, max_tokens: int = None, actual_tokens: int = None):
        details = {}
        if max_tokens:
            details["max_tokens"] = max_tokens
        if actual_tokens:
            details["actual_tokens"] = actual_tokens
        super().__init__(message, details, "TOKEN_LIMIT_ERROR")

class ContentFilterException(EvaluationException):
    """Content filtering errors"""
    def __init__(self, message: str, filtered_content: str = None):
        details = {"filtered_content": filtered_content} if filtered_content else {}
        super().__init__(message, details, "CONTENT_FILTER_ERROR")

class RateLimitException(EvaluationException):
    """Rate limiting errors"""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, {"retry_after": retry_after}, "RATE_LIMIT_ERROR")
        self.retry_after = retry_after

# Fixed prompt version
FIXED_PROMPT_VERSION = "v1.5.0"


# Enhanced route timer with connection pooling and performance monitoring
async def enhanced_route_timer(request: Request) -> AsyncIterator[None]:
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    request_id = f"req_{int(time.time() * 1000)}"
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    logger.info(f"[{request_id}] → {method} {path}")
    
    # Get performance monitor
    perf_monitor = get_performance_monitor()
    success = True
    
    try:
        yield
    except Exception as e:
        success = False
        logger.error(f"[{request_id}] Request failed: {e}")
        raise
    finally:
        dur_ms = (time.perf_counter() - start) * 1000.0
        slow_ms = float(os.getenv("SLOW_REQUEST_MS", "2000"))
        slow_tag = " SLOW" if dur_ms > slow_ms else ""
        
        # Record performance metrics
        perf_monitor.record_request(dur_ms, success)
        
        logger.info(f"[{request_id}] ← {method} {path} {dur_ms:.1f}ms{slow_tag}")
        print(f"[API] [{request_id}] ← {method} {path} {dur_ms:.1f}ms{slow_tag}", flush=True)


# Error response helper functions
def create_error_response(status_code: int, error_type: str, message: str, request_id: str, **extra_details) -> HTTPException:
    """Create standardized error response"""
    detail = {
        "error": message,
        "type": error_type,
        "request_id": request_id,
        **extra_details
    }
    return HTTPException(status_code=status_code, detail=detail)

def create_error_response_with_headers(status_code: int, error_type: str, message: str, request_id: str, headers: dict, **extra_details) -> HTTPException:
    """Create standardized error response with custom headers"""
    detail = {
        "error": message,
        "type": error_type,
        "request_id": request_id,
        **extra_details
    }
    return HTTPException(status_code=status_code, detail=detail, headers=headers)

async def handle_evaluation_execution(evaluator: EssayEvaluator, req: EssayEvalRequest, request_id: str) -> Tuple[Any, float]:
    """Execute evaluation and return result with timing"""
    evaluation_start = time.time()
    try:
        result = await evaluator.evaluate(req)
        evaluation_time = time.time() - evaluation_start
        return result, evaluation_time
    except Exception as e:
        evaluation_time = time.time() - evaluation_start
        logger.error(f"[{request_id}] Evaluation failed after {evaluation_time:.2f}s: {e}")
        await _handle_evaluation_error(e, req, request_id, evaluation_time)
        raise

async def process_evaluation_result(result: Any, response: Response, request_id: str, evaluation_time: float, background_tasks: BackgroundTasks, metrics_task_id: str) -> Any:
    """Process and validate evaluation results"""
    # Validate result
    if not result or not hasattr(result, 'timings'):
        logger.error(f"[{request_id}] Invalid evaluation result")
        raise EvaluationException(
            "Invalid evaluation result",
            details={"result_type": type(result).__name__, "request_id": request_id}
        )
    
    # Enhanced response processing
    await _process_evaluation_response(
        result, response, request_id, evaluation_time, background_tasks
    )
    
    # Background cleanup task
    background_tasks.add_task(
        _post_evaluation_cleanup,
        request_id, metrics_task_id, evaluation_time
    )
    
    logger.info(
        f"[{request_id}] Evaluation completed successfully in {evaluation_time:.2f}s "
        f"for level: {result.level_group if hasattr(result, 'level_group') else 'unknown'}"
    )
    
    return result


router = APIRouter(dependencies=[Depends(enhanced_route_timer)])


# Basic sync dependencies for compatibility
@lru_cache()
def get_loader() -> PromptLoader:
    """기본 프롬프트 로더 (동기식, 기존 호환성)"""
    return PromptLoader(version=FIXED_PROMPT_VERSION)

@lru_cache()
def get_llm() -> LLM:
    """기본 LLM (동기식, 기존 호환성)"""
    return build_llm()

def get_evaluator(
    llm: LLM = Depends(get_llm),
    loader: PromptLoader = Depends(get_loader),
) -> EssayEvaluator:
    return EssayEvaluator(llm, loader)


# Enhanced async dependencies with connection pooling
async def get_llm_with_pool() -> LLM:
    """연결 풀을 사용하는 비동기 LLM 획득"""
    connection_pool = get_connection_pool()
    
    async with connection_pool.acquire():
        return await get_async_llm()

async def get_loader_with_validation() -> PromptLoader:
    """검증이 포함된 비동기 PromptLoader 획득"""
    try:
        loader = await get_async_prompt_loader(FIXED_PROMPT_VERSION)
        
        # 백그라운드에서 추가 검증 수행
        task_manager = get_task_manager()
        validation_task_id = await task_manager.run_in_background(
            _validate_loader_comprehensive(loader),
            task_id=f"validation_{int(time.time())}",
            timeout=10.0
        )
        
        logger.info(f"Started background validation task: {validation_task_id}")
        return loader
        
    except Exception as e:
        logger.error(f"Failed to get validated loader: {e}")
        raise PromptLoadException(
            f"Failed to load and validate prompts for version {FIXED_PROMPT_VERSION}",
            version=FIXED_PROMPT_VERSION,
            details={"error": str(e)}
        )

async def _validate_loader_comprehensive(loader: PromptLoader) -> None:
    """포괄적인 프롬프트 로더 검증"""
    sections = ["grammar", "introduction", "body", "conclusion"]
    levels = ["Basic", "Intermediate", "Advanced", "Expert"]
    
    for section in sections:
        for level in levels:
            prompt = loader.load_prompt(section, level)
            if not prompt or len(prompt.strip()) < 20:
                raise ValueError(f"Invalid prompt: {section}/{level}")
    
    logger.info("Comprehensive prompt validation completed")


@router.post("/essay-eval", response_model=EssayEvalResponse)
@async_timeout(MAX_EVALUATION_TIMEOUT)
@async_retry(max_attempts=MAX_RETRY_ATTEMPTS, delay=RETRY_DELAY)
async def essay_eval(
    req: EssayEvalRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    llm: LLM = Depends(get_llm_with_pool),
    loader: PromptLoader = Depends(get_loader_with_validation),
    performance_monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> EssayEvalResponse:
    """Enhanced essay evaluation with comprehensive async processing"""
    
    request_id = getattr(req, 'request_id', f"req_{int(time.time() * 1000)}")
    connection_pool = get_connection_pool()
    task_manager = get_task_manager()
    
    logger.info(f"[{request_id}] Starting enhanced essay evaluation for level: {req.rubric_level}")
    
    try:
        # Enhanced input validation with async processing
        await _validate_request_async(req, request_id)
        
        # Connection pool을 통한 리소스 관리
        async with connection_pool.acquire():
            # Create evaluator with managed resources
            evaluator = EssayEvaluator(llm, loader)
            
            logger.info(f"[{request_id}] Using prompt version: {FIXED_PROMPT_VERSION}")
            
            # Start background metrics collection
            metrics_task_id = await task_manager.run_in_background(
                _collect_evaluation_metrics(req, request_id),
                task_id=f"metrics_{request_id}",
                timeout=METRICS_TIMEOUT
            )
            
            # Execute evaluation
            result, evaluation_time = await handle_evaluation_execution(evaluator, req, request_id)
            
            # Process and validate results
            final_result = await process_evaluation_result(
                result, response, request_id, evaluation_time, background_tasks, metrics_task_id
            )
            
            return final_result
    
    except ValidationException as e:
        logger.error(f"[{request_id}] Validation error: {e.message}")
        raise create_error_response(
            HTTP_UNPROCESSABLE_ENTITY, "ValidationError", e.message, request_id,
            field=e.field, details=e.details
        )
    except PromptLoadException as e:
        logger.error(f"[{request_id}] Prompt loading error: {e.message}")
        raise create_error_response(
            HTTP_SERVICE_UNAVAILABLE, "PromptLoadError", "Prompt system unavailable", request_id,
            version=e.version
        )
    except LLMConnectionException as e:
        logger.error(f"[{request_id}] LLM connection error: {e.message}")
        raise create_error_response_with_headers(
            HTTP_SERVICE_UNAVAILABLE, "LLMConnectionError", "AI service unavailable", request_id,
            headers={"Retry-After": str(e.retry_after)}, retry_after=e.retry_after
        )
    except RateLimitException as e:
        logger.warning(f"[{request_id}] Rate limit error: {e.message}")
        raise create_error_response_with_headers(
            HTTP_TOO_MANY_REQUESTS, "RateLimitError", "Rate limit exceeded", request_id,
            headers={"Retry-After": str(e.retry_after)}, retry_after=e.retry_after
        )
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {e}")
        logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
        raise create_error_response(
            HTTP_INTERNAL_SERVER_ERROR, "InternalError", "Internal server error", request_id,
            message=str(e)
        )


# Ping endpoint helper functions
async def perform_health_checks(ping_id: str, connection_pool, task_manager) -> Tuple[Any, float]:
    """Perform comprehensive health checks and return LLM response and connection time"""
    # Test LLM initialization
    try:
        llm = await get_async_llm()
        logger.info(f"[{ping_id}] LLM type: {type(llm)}")
    except Exception as e:
        logger.error(f"[{ping_id}] LLM initialization failed: {e}")
        raise LLMConnectionException(
            "Failed to initialize LLM client",
            details={"initialization_error": str(e), "ping_id": ping_id}
        )
    
    # Test prompt loading with validation
    try:
        loader = await get_async_prompt_loader(FIXED_PROMPT_VERSION)
        validation_task_id = await task_manager.run_in_background(
            _validate_all_prompts(loader, ping_id),
            task_id=f"validation_{ping_id}",
            timeout=VALIDATION_TIMEOUT
        )
        logger.info(f"[{ping_id}] Prompt validation started: {validation_task_id}")
    except Exception as e:
        logger.error(f"[{ping_id}] Prompt validation failed: {e}")
        raise PromptLoadException(
            "Prompt validation failed",
            version=FIXED_PROMPT_VERSION,
            details={"validation_error": str(e), "ping_id": ping_id}
        )
    
    # Test LLM connection with enhanced monitoring
    try:
        connection_start = time.time()
        res = await llm.run_azure_openai(
            messages=[{"role": "user", "content": "health check ping"}],
            json_schema={
                "type": "object",
                "properties": {"status": {"type": "string"}, "ok": {"type": "boolean"}},
                "required": ["status", "ok"],
                "additionalProperties": False,
                "title": "HealthCheck",
            },
            name="api.ping.health_check",
        )
        connection_time = (time.time() - connection_start) * 1000
        return res, connection_time
        
    except Exception as e:
        connection_time = (time.time() - connection_start) * 1000
        logger.error(f"[{ping_id}] LLM connection test failed after {connection_time:.1f}ms: {e}")
        await _handle_ping_error(e, ping_id, connection_time)
        raise  # _handle_ping_error will raise appropriate exception

def create_ping_response(ping_id: str, response_time: float, connection_time: float, res: Any, system_stats: dict) -> dict[str, Any]:
    """Create standardized ping response"""
    return {
        "status": "healthy",
        "ok": True,
        "raw": bool(res),
        "prompt_version": FIXED_PROMPT_VERSION,
        "response_time_ms": round(response_time, 1),
        "connection_time_ms": round(connection_time, 1),
        "timestamp": time.time(),
        "ping_id": ping_id,
        "services": {
            "llm": "connected",
            "prompts": "loaded",
            "api": "operational",
            "connection_pool": "active",
            "task_manager": "operational"
        },
        "system_stats": system_stats
    }

def handle_ping_exception(e: Exception, ping_id: str, start_time: float) -> HTTPException:
    """Handle ping-specific exceptions with appropriate error responses"""
    response_time = (time.time() - start_time) * 1000
    
    if isinstance(e, ValidationException):
        logger.error(f"[{ping_id}] Validation error during ping: {e.message}")
        return create_error_response(
            HTTP_UNPROCESSABLE_ENTITY, "ValidationError", e.message, ping_id,
            status="unhealthy", response_time_ms=round(response_time, 1)
        )
    elif isinstance(e, PromptLoadException):
        logger.error(f"[{ping_id}] Prompt loading error during ping: {e.message}")
        return create_error_response(
            HTTP_SERVICE_UNAVAILABLE, "PromptLoadError", "Prompt system unavailable", ping_id,
            status="unhealthy", version=e.version, response_time_ms=round(response_time, 1)
        )
    elif isinstance(e, LLMConnectionException):
        logger.error(f"[{ping_id}] LLM connection error during ping: {e.message}")
        return create_error_response_with_headers(
            HTTP_SERVICE_UNAVAILABLE, "LLMConnectionError", "AI service unavailable", ping_id,
            headers={"Retry-After": str(e.retry_after)},
            status="unhealthy", retry_after=e.retry_after, response_time_ms=round(response_time, 1)
        )
    elif isinstance(e, RateLimitException):
        logger.warning(f"[{ping_id}] Rate limit during ping: {e.message}")
        return create_error_response_with_headers(
            HTTP_TOO_MANY_REQUESTS, "RateLimitError", "Rate limit exceeded", ping_id,
            headers={"Retry-After": str(e.retry_after)},
            status="rate_limited", retry_after=e.retry_after, response_time_ms=round(response_time, 1)
        )
    else:
        logger.error(f"[{ping_id}] Unexpected error during ping: {e}")
        logger.error(f"[{ping_id}] Traceback: {traceback.format_exc()}")
        return create_error_response(
            HTTP_SERVICE_UNAVAILABLE, "ServiceError", "Health check failed", ping_id,
            status="error", message=str(e), response_time_ms=round(response_time, 1)
        )
@router.get("/ping")
@async_timeout(MAX_PING_TIMEOUT)
async def ping(
    background_tasks: BackgroundTasks,
    performance_monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> dict[str, Any]:
    """Enhanced health check endpoint with comprehensive monitoring and connection pooling"""
    ping_id = f"ping_{int(time.time() * 1000)}"
    start_time = time.time()
    connection_pool = get_connection_pool()
    task_manager = get_task_manager()
    
    try:
        logger.info(f"[{ping_id}] Starting comprehensive health check")
        
        # Perform health checks with connection pooling
        async with connection_pool.acquire():
            res, connection_time = await perform_health_checks(ping_id, connection_pool, task_manager)
        
        response_time = (time.time() - start_time) * 1000  # milliseconds
        
        # Collect system statistics
        system_stats = {
            "connection_pool": connection_pool.get_stats(),
            "task_manager": task_manager.get_all_tasks_status(),
            "performance": performance_monitor.get_stats()
        }
        
        # Start background detailed system monitoring
        background_tasks.add_task(
            _detailed_system_monitoring,
            ping_id, response_time, system_stats
        )
        
        logger.info(f"[{ping_id}] Health check completed successfully in {response_time:.1f}ms")
        
        return create_ping_response(ping_id, response_time, connection_time, res, system_stats)
        
    except (ValidationException, PromptLoadException, LLMConnectionException, RateLimitException, Exception) as e:
        raise handle_ping_exception(e, ping_id, start_time)


# Helper functions for enhanced async processing
async def _validate_request_async(req: EssayEvalRequest, request_id: str) -> None:
    """비동기 요청 검증"""
    if not req.submit_text or len(req.submit_text.strip()) < 10:
        raise ValidationException(
            "Essay text too short", 
            field="submit_text",
            details={
                "min_length": 10, 
                "actual_length": len(req.submit_text.strip()) if req.submit_text else 0,
                "request_id": request_id
            }
        )
    
    if len(req.submit_text) > 50000:  # 50KB 제한
        raise ValidationException(
            "Essay text too long",
            field="submit_text", 
            details={
                "max_length": 50000,
                "actual_length": len(req.submit_text),
                "request_id": request_id
            }
        )
    
    # CPU 집약적인 검증을 백그라운드에서 수행
    task_manager = get_task_manager()
    await task_manager.run_in_background(
        _intensive_content_validation(req.submit_text, request_id),
        task_id=f"content_validation_{request_id}",
        timeout=30.0
    )

async def _intensive_content_validation(text: str, request_id: str) -> None:
    """CPU 집약적인 콘텐츠 검증"""
    # 언어 감지, 스팸 검사 등
    import re
    
    # 기본적인 패턴 검사
    suspicious_patterns = [
        r'(.)\1{50,}',  # 같은 문자 50번 이상 반복
        r'[^\w\s]{20,}',  # 특수문자만 20개 이상
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text):
            logger.warning(f"[{request_id}] Suspicious pattern detected: {pattern}")
            raise ValidationException(
                "Content contains suspicious patterns",
                field="submit_text",
                details={"pattern": pattern, "request_id": request_id}
            )

async def _collect_evaluation_metrics(req: EssayEvalRequest, request_id: str) -> None:
    """평가 메트릭 수집 (백그라운드 작업)"""
    try:
        # 메트릭 수집 로직
        metrics = {
            "text_length": len(req.submit_text),
            "word_count": len(req.submit_text.split()),
            "rubric_level": req.rubric_level,
            "timestamp": time.time(),
            "request_id": request_id
        }
        
        # 외부 메트릭 시스템에 전송
        logger.info(f"[{request_id}] Metrics collected: {metrics}")
        
    except Exception as e:
        logger.warning(f"[{request_id}] Failed to collect metrics: {e}")

async def _handle_evaluation_error(error: Exception, req: EssayEvalRequest, request_id: str, evaluation_time: float) -> None:
    """평가 오류 처리"""
    error_str = str(error).lower()
    
    if "timeout" in error_str:
        raise LLMConnectionException(
            "Evaluation timeout - please try with shorter text",
            details={
                "timeout_duration": evaluation_time,
                "text_length": len(req.submit_text),
                "request_id": request_id
            },
            retry_after=120
        )
    elif "rate limit" in error_str:
        raise RateLimitException("Service temporarily busy - please try again later")
    elif "token" in error_str and ("limit" in error_str or "exceed" in error_str):
        raise TokenLimitException(
            "Text too long for processing",
            actual_tokens=len(req.submit_text.split()) * 1.3  # 추정값
        )
    else:
        raise EvaluationException(
            "Evaluation failed",
            details={"original_error": str(error), "request_id": request_id}
        )

async def _process_evaluation_response(
    result, response: Response, request_id: str, evaluation_time: float, background_tasks: BackgroundTasks
) -> None:
    """평가 응답 처리"""
    # 응답 헤더 설정
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Evaluation-Time"] = f"{evaluation_time:.2f}s"
    response.headers["X-Prompt-Version"] = FIXED_PROMPT_VERSION
    
    # 성능 정보 로깅
    logger.info(f"[{request_id}] Response headers set - evaluation time: {evaluation_time:.2f}s")

async def _post_evaluation_cleanup(request_id: str, metrics_task_id: str, evaluation_time: float) -> None:
    """평가 후 정리 작업 (백그라운드)"""
    try:
        task_manager = get_task_manager()
        
        # 메트릭 태스크 상태 확인
        metrics_status = task_manager.get_task_status(metrics_task_id)
        if metrics_status:
            logger.debug(f"[{request_id}] Metrics task status: {metrics_status}")
        
        logger.info(f"[{request_id}] Post-evaluation cleanup completed")
        
    except Exception as e:
        logger.warning(f"[{request_id}] Post-evaluation cleanup failed: {e}")


# Ping endpoint helper functions
async def _validate_all_prompts(loader: PromptLoader, ping_id: str) -> None:
    """모든 프롬프트 유효성 검증 (백그라운드 작업)"""
    try:
        sections = ["grammar", "introduction", "body", "conclusion"]
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        validation_results = []
        
        for section in sections:
            for level in levels:
                prompt = loader.load_prompt(section, level)
                if not prompt or len(prompt.strip()) < 20:
                    validation_results.append(f"FAILED: {section}/{level}")
                else:
                    validation_results.append(f"OK: {section}/{level}")
        
        failed_validations = [r for r in validation_results if r.startswith("FAILED")]
        
        if failed_validations:
            logger.error(f"[{ping_id}] Prompt validation failures: {failed_validations}")
            raise ValueError(f"Prompt validation failed: {len(failed_validations)} failures")
        
        logger.info(f"[{ping_id}] All prompts validated successfully: {len(validation_results)} checks")
        
    except Exception as e:
        logger.error(f"[{ping_id}] Comprehensive prompt validation failed: {e}")
        raise

async def _handle_ping_error(error: Exception, ping_id: str, connection_time: float) -> None:
    """핑 에러 처리"""
    error_str = str(error).lower()
    
    if "rate limit" in error_str:
        raise RateLimitException("API rate limit exceeded during health check")
    elif "unauthorized" in error_str or "authentication" in error_str:
        raise LLMConnectionException(
            "Authentication failed",
            details={"auth_error": str(error), "ping_id": ping_id, "connection_time_ms": connection_time}
        )
    elif "timeout" in error_str or isinstance(error, asyncio.TimeoutError):
        raise LLMConnectionException(
            "LLM connection timeout",
            details={"timeout_error": str(error), "ping_id": ping_id, "connection_time_ms": connection_time},
            retry_after=60
        )
    else:
        raise LLMConnectionException(
            "LLM service test failed",
            details={"connection_error": str(error), "ping_id": ping_id, "connection_time_ms": connection_time}
        )

async def _detailed_system_monitoring(ping_id: str, response_time: float, system_stats: dict) -> None:
    """상세 시스템 모니터링 (백그라운드 작업)"""
    try:
        # 성능 지표 분석
        pool_stats = system_stats.get("connection_pool", {})
        task_stats = system_stats.get("task_manager", {})
        perf_stats = system_stats.get("performance", {})
        
        # 모니터링 로깅
        logger.info(f"[{ping_id}] System monitoring:")
        logger.info(f"  Response time: {response_time:.1f}ms")
        logger.info(f"  Connection pool: {pool_stats}")
        logger.info(f"  Task manager: {task_stats}")
        logger.info(f"  Performance: {perf_stats}")
        
        # 알림 조건 체크
        if response_time > 10000:  # 10초 이상
            logger.warning(f"[{ping_id}] Slow ping response: {response_time:.1f}ms")
        
        if pool_stats.get("success_rate", 1.0) < 0.9:  # 90% 미만 성공률
            logger.warning(f"[{ping_id}] Low connection pool success rate: {pool_stats.get('success_rate', 0):.2%}")
        
        # 외부 모니터링 시스템에 메트릭 전송
        # await send_to_external_monitoring(ping_id, response_time, system_stats)
        
    except Exception as e:
        logger.warning(f"[{ping_id}] Detailed system monitoring failed: {e}")