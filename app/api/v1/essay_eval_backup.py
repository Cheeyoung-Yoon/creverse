import os
import time
import asyncio
import logging
import traceback
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Optional

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

# Setup logger
logger = logging.getLogger(__name__)

# Custom exceptions with detailed error context
class EvaluationException(Exception):
    """Base exception for evaluation errors"""
    def __init__(self, message: str, details: dict = None, error_code: str = None):
        self.message = message
        self.details = details or {}
        self.error_code = error_code
        super().__init__(self.message)

class PromptLoadException(EvaluationException):
    """Prompt loading related errors"""
    def __init__(self, message: str, version: str = None, details: dict = None):
        super().__init__(message, details, "PROMPT_LOAD_ERROR")
        self.version = version

class LLMConnectionException(EvaluationException):
    """LLM connection/timeout errors"""
    def __init__(self, message: str, details: dict = None, retry_after: int = 30):
        super().__init__(message, details, "LLM_CONNECTION_ERROR")
        self.retry_after = retry_after

class ValidationException(EvaluationException):
    """Input validation errors"""
    def __init__(self, message: str, field: str = None, details: dict = None):
        super().__init__(message, details, "VALIDATION_ERROR")
        self.field = field

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


router = APIRouter(dependencies=[Depends(enhanced_route_timer)])


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

async def _validate_loader_comprehensive(loader: PromptLoader):
    """포괄적인 프롬프트 로더 검증"""
    sections = ["grammar", "introduction", "body", "conclusion"]
    levels = ["Basic", "Intermediate", "Advanced", "Expert"]
    
    for section in sections:
        for level in levels:
            prompt = loader.load_prompt(section, level)
            if not prompt or len(prompt.strip()) < 20:
                raise ValueError(f"Invalid prompt: {section}/{level}")
    
    logger.info("Comprehensive prompt validation completed")


def get_evaluator(
    llm: LLM = Depends(get_llm),
    loader: PromptLoader = Depends(get_loader),
) -> EssayEvaluator:
    return EssayEvaluator(llm, loader)

@lru_cache()
def get_loader() -> PromptLoader:
    """기본 프롬프트 로더 (동기식, 기존 호환성)"""
    return PromptLoader(version=FIXED_PROMPT_VERSION)

@lru_cache()
def get_llm() -> LLM:
    """기본 LLM (동기식, 기존 호환성)"""
    return build_llm()


@router.post("/essay-eval", response_model=EssayEvalResponse)
@async_timeout(180.0)  # 3분 타임아웃
@async_retry(max_attempts=2, delay=1.0)  # 최대 2회 재시도
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
            
            # 백그라운드에서 성능 메트릭 수집 시작
            metrics_task_id = await task_manager.run_in_background(
                _collect_evaluation_metrics(req, request_id),
                task_id=f"metrics_{request_id}",
                timeout=300.0
            )
            
            # Run evaluation with enhanced timeout and monitoring
            evaluation_start = time.time()
            try:
                # 평가 실행 (이미 타임아웃과 재시도가 데코레이터로 적용됨)
                result = await evaluator.evaluate(req)
                
            except Exception as e:
                evaluation_time = time.time() - evaluation_start
                logger.error(f"[{request_id}] Evaluation failed after {evaluation_time:.2f}s: {e}")
                
                # 구체적인 에러 분류 및 처리
                await _handle_evaluation_error(e, req, request_id, evaluation_time)
                raise  # 위의 함수에서 적절한 HTTPException이 발생됨
            
            evaluation_time = time.time() - evaluation_start
            
            # Process and validate results
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
            
            # 백그라운드에서 후처리 작업 시작
            background_tasks.add_task(
                _post_evaluation_cleanup,
                request_id, metrics_task_id, evaluation_time
            )
            
            logger.info(
                f"[{request_id}] Evaluation completed successfully in {evaluation_time:.2f}s "
                f"for level: {req.rubric_level}"
            )
            return result
    
    except ValidationException as e:
        logger.error(f"[{request_id}] Validation error: {e.message}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": e.message,
                "type": "ValidationError",
                "field": e.field,
                "request_id": request_id,
                "details": e.details
            }
        )
    except PromptLoadException as e:
        logger.error(f"[{request_id}] Prompt loading error: {e.message}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Prompt system unavailable",
                "type": "PromptLoadError",
                "version": e.version,
                "request_id": request_id
            }
        )
    except LLMConnectionException as e:
        logger.error(f"[{request_id}] LLM connection error: {e.message}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service unavailable",
                "type": "LLMConnectionError",
                "retry_after": e.retry_after,
                "request_id": request_id
            },
            headers={"Retry-After": str(e.retry_after)}
        )
    except RateLimitException as e:
        logger.warning(f"[{request_id}] Rate limit error: {e.message}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "type": "RateLimitError",
                "retry_after": e.retry_after,
                "request_id": request_id
            },
            headers={"Retry-After": str(e.retry_after)}
        )
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {e}")
        logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "type": "InternalError",
                "message": str(e),
                "request_id": request_id
            }
        )

# Helper functions for enhanced async processing
async def _validate_request_async(req: EssayEvalRequest, request_id: str):
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
    
    # CPU 집약적인 검증 작업을 스레드 풀에서 실행
    task_manager = get_task_manager()
    validation_result = await task_manager.run_in_thread(
        _cpu_intensive_validation, req.submit_text, request_id
    )
    
    if not validation_result["valid"]:
        raise ValidationException(
            validation_result["error"],
            field="submit_text",
            details=validation_result["details"]
        )

def _cpu_intensive_validation(text: str, request_id: str) -> dict:
    """CPU 집약적인 텍스트 검증"""
    word_count = len(text.split())
    unique_words = len(set(text.lower().split()))
    
    if word_count > 1000:
        return {
            "valid": False,
            "error": "Essay too long",
            "details": {
                "word_count": word_count,
                "max_words": 1000,
                "request_id": request_id
            }
        }
    
    if unique_words < word_count * 0.2:
        return {
            "valid": False,
            "error": "Essay appears to have excessive repetition",
            "details": {
                "word_count": word_count,
                "unique_words": unique_words,
                "repetition_ratio": unique_words / word_count if word_count > 0 else 0,
                "request_id": request_id
            }
        }
    
    return {"valid": True}

async def _handle_evaluation_error(error: Exception, req: EssayEvalRequest, request_id: str, evaluation_time: float):
    """평가 에러 처리"""
    error_str = str(error).lower()
    
    if "token" in error_str and ("limit" in error_str or "too long" in error_str):
        raise TokenLimitException(
            "Text too long for processing",
            max_tokens=4000,
            actual_tokens=len(req.submit_text.split())
        )
    elif "rate limit" in error_str or "quota" in error_str:
        raise RateLimitException(
            "API rate limit exceeded",
            retry_after=60
        )
    elif "content filter" in error_str or "inappropriate" in error_str:
        raise ContentFilterException(
            "Content was filtered by safety systems"
        )
    elif isinstance(error, asyncio.TimeoutError):
        raise LLMConnectionException(
            "Evaluation timeout - request took too long",
            details={
                "evaluation_time": evaluation_time,
                "request_id": request_id,
                "essay_length": len(req.submit_text)
            },
            retry_after=60
        )
    else:
        raise LLMConnectionException(
            "AI service error during evaluation",
            details={
                "original_error": str(error),
                "error_type": type(error).__name__,
                "request_id": request_id,
                "evaluation_time": evaluation_time
            }
        )

async def _process_evaluation_response(
    result, response: Response, request_id: str, evaluation_time: float, background_tasks: BackgroundTasks
):
    """평가 응답 처리"""
    timings = result.timings
    if timings:
        parts = []
        for key in ("pre_process", "grammar", "structure", "aggregate", "post_process", "total"):
            duration = timings.get(key)
            if duration is not None:
                parts.append(f"{key};dur={duration:.1f}")
        
        header_val = ", ".join(parts)
        if header_val:
            response.headers["Server-Timing"] = header_val
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Evaluation-Time"] = f"{evaluation_time:.2f}s"
        
        # 성능 로깅을 백그라운드에서 처리
        background_tasks.add_task(
            _log_performance_metrics,
            request_id, timings, evaluation_time
        )

async def _collect_evaluation_metrics(req: EssayEvalRequest, request_id: str):
    """평가 메트릭 수집 (백그라운드 작업)"""
    try:
        metrics = {
            "request_id": request_id,
            "level": req.rubric_level,
            "text_length": len(req.submit_text),
            "word_count": len(req.submit_text.split()),
            "timestamp": time.time()
        }
        
        # 메트릭을 로깅 시스템 또는 모니터링 시스템에 전송
        logger.info(f"[METRICS] {request_id}: {metrics}")
        
        # 추가적인 분석을 위해 스레드 풀에서 처리
        task_manager = get_task_manager()
        await task_manager.run_in_thread(_analyze_text_complexity, req.submit_text, request_id)
        
    except Exception as e:
        logger.warning(f"[{request_id}] Failed to collect metrics: {e}")

def _analyze_text_complexity(text: str, request_id: str):
    """텍스트 복잡도 분석 (CPU 집약적 작업)"""
    try:
        # 간단한 복잡도 분석
        sentences = text.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        
        complexity_metrics = {
            "avg_sentence_length": avg_sentence_length,
            "sentence_count": len(sentences),
            "unique_word_ratio": len(set(text.lower().split())) / len(text.split()) if text.split() else 0
        }
        
        logger.debug(f"[{request_id}] Text complexity: {complexity_metrics}")
        
    except Exception as e:
        logger.warning(f"[{request_id}] Text complexity analysis failed: {e}")

async def _log_performance_metrics(request_id: str, timings: dict, evaluation_time: float):
    """성능 메트릭 로깅 (백그라운드 작업)"""
    try:
        pretty = " ".join([f"{k}={v:.1f}ms" for k, v in timings.items()])
        total_time = timings.get("total", 0)
        
        logger.info(f"[{request_id}] Performance: {pretty}, Total evaluation: {evaluation_time:.2f}s")
        
        # 느린 요청 감지
        if total_time > 60000:  # > 1분
            logger.warning(f"[{request_id}] Slow evaluation detected: {total_time:.1f}ms")
        
        # 모니터링 시스템에 메트릭 전송 (예: Prometheus, DataDog 등)
        # await send_to_monitoring_system(request_id, timings, evaluation_time)
        
    except Exception as e:
        logger.warning(f"[{request_id}] Failed to log performance metrics: {e}")

async def _post_evaluation_cleanup(request_id: str, metrics_task_id: str, evaluation_time: float):
    """평가 후 정리 작업 (백그라운드)"""
    try:
        # 태스크 매니저에서 완료된 작업들 정리
        task_manager = get_task_manager()
        await task_manager.cleanup_completed_tasks()
        
        # 메트릭 태스크 상태 확인
        # 메트릭 태스크 상태 확인
        metrics_status = task_manager.get_task_status(metrics_task_id)
        if metrics_status:
            logger.debug(f"[{request_id}] Metrics task status: {metrics_status}")
        
        logger.info(f"[{request_id}] Post-evaluation cleanup completed")
        
    except Exception as e:
        logger.warning(f"[{request_id}] Post-evaluation cleanup failed: {e}")


@router.get("/ping")
@async_timeout(45.0)  # 45초 타임아웃
async def ping(
    background_tasks: BackgroundTasks,
    performance_monitor: PerformanceMonitor = Depends(get_performance_monitor)
):
                "error_code": e.error_code,
                "retry_after": e.retry_after,
                "details": e.details,
                "request_id": request_id
            }
        )
    except TokenLimitException as e:
        logger.warning(f"[{request_id}] Token limit exceeded: {e.message}")
        raise HTTPException(
            status_code=413,
            detail={
                "error": "Text too long for processing",
                "type": "TokenLimitExceeded",
                "error_code": e.error_code,
                "max_tokens": e.details.get("max_tokens"),
                "actual_tokens": e.details.get("actual_tokens"),
                "suggestion": "Please shorten your essay and try again",
                "request_id": request_id
            }
        )
    except ContentFilterException as e:
        logger.warning(f"[{request_id}] Content filtered: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Content was filtered by safety systems",
                "type": "ContentFiltered",
                "error_code": e.error_code,
                "suggestion": "Please review your content and ensure it follows guidelines",
                "request_id": request_id
            }
        )
    except RateLimitException as e:
        logger.warning(f"[{request_id}] Rate limit exceeded: {e.message}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "type": "RateLimitExceeded",
                "error_code": e.error_code,
                "retry_after": e.retry_after,
                "suggestion": f"Please wait {e.retry_after} seconds before trying again",
                "request_id": request_id
            },
            headers={"Retry-After": str(e.retry_after)}
        )
    except EvaluationException as e:
        logger.error(f"[{request_id}] General evaluation error: {e.message}")
        raise HTTPException(
            status_code=422,
            detail={
                "error": e.message,
                "type": "EvaluationError",
                "error_code": e.error_code,
                "details": e.details,
                "request_id": request_id
            }
        )
    except Exception as exc:
        # Log unexpected errors with full context
        logger.error(f"[{request_id}] Unexpected error in essay evaluation: {exc}")
        logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "type": "InternalError",
                "message": "An unexpected error occurred. Please try again later.",
                "request_id": request_id,
                "support_info": "If this error persists, please contact support with the request_id"
            }
        )


@router.get("/ping")
@async_timeout(45.0)  # 45초 타임아웃
async def ping(
    background_tasks: BackgroundTasks,
    performance_monitor: PerformanceMonitor = Depends(get_performance_monitor)
):
    """Enhanced health check endpoint with comprehensive monitoring and connection pooling"""
    ping_id = f"ping_{int(time.time() * 1000)}"
    start_time = time.time()
    connection_pool = get_connection_pool()
    task_manager = get_task_manager()
    
    try:
        logger.info(f"[{ping_id}] Starting comprehensive health check")
        
        # 비동기 리소스 상태 체크
        async with connection_pool.acquire():
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
                # 백그라운드에서 상세 검증 실행
                validation_task_id = await task_manager.run_in_background(
                    _validate_all_prompts(loader, ping_id),
                    task_id=f"validation_{ping_id}",
                    timeout=15.0
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
                
            except Exception as e:
                connection_time = (time.time() - connection_start) * 1000
                logger.error(f"[{ping_id}] LLM connection test failed after {connection_time:.1f}ms: {e}")
                await _handle_ping_error(e, ping_id, connection_time)
        
        response_time = (time.time() - start_time) * 1000  # milliseconds
        
        # 시스템 상태 수집
        system_stats = {
            "connection_pool": connection_pool.get_stats(),
            "task_manager": task_manager.get_all_tasks_status(),
            "performance": performance_monitor.get_stats()
        }
        
        # 백그라운드에서 상세 시스템 모니터링
        background_tasks.add_task(
            _detailed_system_monitoring,
            ping_id, response_time, system_stats
        )
        
        logger.info(f"[{ping_id}] Health check completed successfully in {response_time:.1f}ms")
        
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
        
    except ValidationException as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"[{ping_id}] Validation error during ping: {e.message}")
        raise HTTPException(
            status_code=422,
            detail={
                "status": "unhealthy",
                "error": e.message,
                "type": "ValidationError",
                "ping_id": ping_id,
                "response_time_ms": round(response_time, 1)
            }
        )
    except PromptLoadException as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"[{ping_id}] Prompt loading error during ping: {e.message}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": "Prompt system unavailable",
                "type": "PromptLoadError",
                "version": e.version,
                "ping_id": ping_id,
                "response_time_ms": round(response_time, 1)
            }
        )
    except LLMConnectionException as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"[{ping_id}] LLM connection error during ping: {e.message}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": "AI service unavailable",
                "type": "LLMConnectionError",
                "retry_after": e.retry_after,
                "ping_id": ping_id,
                "response_time_ms": round(response_time, 1)
            },
            headers={"Retry-After": str(e.retry_after)}
        )
    except RateLimitException as e:
        response_time = (time.time() - start_time) * 1000
        logger.warning(f"[{ping_id}] Rate limit during ping: {e.message}")
        raise HTTPException(
            status_code=429,
            detail={
                "status": "rate_limited",
                "error": "Rate limit exceeded",
                "type": "RateLimitError",
                "retry_after": e.retry_after,
                "ping_id": ping_id,
                "response_time_ms": round(response_time, 1)
            },
            headers={"Retry-After": str(e.retry_after)}
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"[{ping_id}] Unexpected error during ping: {e}")
        logger.error(f"[{ping_id}] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=503, 
            detail={
                "status": "error",
                "error": "Health check failed",
                "type": "ServiceError",
                "message": str(e),
                "ping_id": ping_id,
                "response_time_ms": round(response_time, 1)
            }
        )


# Ping endpoint helper functions
async def _validate_all_prompts(loader: PromptLoader, ping_id: str):
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

async def _handle_ping_error(error: Exception, ping_id: str, connection_time: float):
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

async def _detailed_system_monitoring(ping_id: str, response_time: float, system_stats: dict):
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
