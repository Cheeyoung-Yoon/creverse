import os
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # ★ 라우터/모듈 임포트 전에!

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.essay_eval import router as eval_router
from app.utils.prompt_loader import PromptLoader
from app.client.bootstrap import build_llm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global async resource managers
_connection_pool = None
_task_manager = None
_performance_monitor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 애플리케이션 수명주기 관리"""
    global _connection_pool, _task_manager, _performance_monitor
    
    startup_time = time.time()
    logger.info("Starting FastAPI application with enhanced async resources...")
    
    try:
        # 비동기 리소스 초기화
        from app.core.async_manager import AsyncConnectionPool, AsyncTaskManager
        from app.core.dependencies import PerformanceMonitor
        
        # Connection Pool 초기화
        _connection_pool = AsyncConnectionPool(
            max_connections=20,
            timeout=1000.0  # 1000초 타임아웃
        )
        logger.info(f"Connection pool initialized: {_connection_pool.get_stats()}")
        
        # Task Manager 초기화  
        _task_manager = AsyncTaskManager(
            max_workers=8
        )
        logger.info(f"Task manager initialized: {_task_manager.get_all_tasks_status()}")
        
        # Performance Monitor 초기화
        _performance_monitor = PerformanceMonitor()
        logger.info("Performance monitor initialized")
        
        # 사전 리소스 워밍업
        logger.info("Starting resource warm-up...")
        await _warmup_resources()
        
        startup_duration = (time.time() - startup_time) * 1000
        logger.info(f"Application startup completed in {startup_duration:.1f}ms")
        
        yield  # 애플리케이션 실행
        
    except Exception as e:
        logger.error(f"Failed to initialize async resources: {e}", exc_info=True)
        raise
    
    finally:
        # Shutdown 프로세스
        shutdown_time = time.time()
        logger.info("Shutting down FastAPI application...")
        
        try:
            # 모든 백그라운드 작업 완료 대기
            if _task_manager:
                await _task_manager.shutdown()
                logger.info("Task manager shutdown completed")
            
            # Connection Pool 정리
            if _connection_pool:
                logger.info("Connection pool shutdown completed")
            
            # Performance Monitor 정리
            if _performance_monitor:
                final_stats = _performance_monitor.get_stats()
                logger.info(f"Final performance stats: {final_stats}")
            
            shutdown_duration = (time.time() - shutdown_time) * 1000
            logger.info(f"Application shutdown completed in {shutdown_duration:.1f}ms")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

async def _warmup_resources() -> None:
    """애플리케이션 시작시 리소스 워밍업"""
    try:
        # Prompt Loader 사전 로딩
        from app.utils.prompt_loader import PromptLoader
        loader = PromptLoader(version="v1.5.0")
        
        # 주요 프롬프트 미리 로딩
        warmup_tasks = []
        sections = ["grammar", "introduction", "body", "conclusion"]
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for section in sections[:2]:  # 일부만 워밍업
            for level in levels[:2]:
                warmup_tasks.append(_warmup_prompt(loader, section, level))
        
        if warmup_tasks:
            results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
            successful_warmups = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"Prompt warmup completed: {successful_warmups}/{len(warmup_tasks)} successful")
        
        # LLM 초기화 테스트
        try:
            from app.client.bootstrap import build_llm
            llm = build_llm()
            logger.info(f"LLM warmup successful: {type(llm)}")
        except Exception as e:
            logger.warning(f"LLM warmup failed: {e}")
            
    except Exception as e:
        logger.warning(f"Resource warmup failed: {e}")

async def _warmup_prompt(loader: PromptLoader, section: str, level: str) -> str:
    """개별 프롬프트 워밍업"""
    try:
        prompt = loader.load_prompt(section, level)
        if prompt and len(prompt.strip()) > 0:
            return f"{section}/{level}: OK"
        else:
            raise ValueError(f"Empty prompt: {section}/{level}")
    except Exception as e:
        logger.warning(f"Failed to warmup prompt {section}/{level}: {e}")
        raise

# Global resource accessors
def get_connection_pool() -> 'AsyncConnectionPool':
    """전역 Connection Pool 액세스"""
    global _connection_pool
    if _connection_pool is None:
        raise RuntimeError("Connection pool not initialized")
    return _connection_pool

def get_task_manager() -> 'AsyncTaskManager':
    """전역 Task Manager 액세스"""
    global _task_manager
    if _task_manager is None:
        raise RuntimeError("Task manager not initialized")
    return _task_manager

def get_performance_monitor() -> 'PerformanceMonitor':
    """전역 Performance Monitor 액세스"""
    global _performance_monitor
    if _performance_monitor is None:
        raise RuntimeError("Performance monitor not initialized")
    return _performance_monitor


def create_app() -> FastAPI:
    app = FastAPI(
        title="Essay Evaluation API", 
        version="1.0.0",
        description="AI-powered essay evaluation system with fixed prompt version v1.5.0",
        lifespan=lifespan  # 수명주기 이벤트 추가
    )

    # Global exception handler with detailed error tracking
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = f"global_{int(time.time() * 1000)}"
        client_ip = request.client.host if request.client else "unknown"
        
        # Log detailed error information
        logger.error(f"[{request_id}] Unhandled exception from {client_ip}: {exc}", exc_info=True)
        logger.error(f"[{request_id}] Request URL: {request.url}")
        logger.error(f"[{request_id}] Request method: {request.method}")
        
        # Extract more specific error information
        error_details = {
            "request_id": request_id,
            "path": str(request.url.path),
            "method": request.method,
            "client_ip": client_ip,
            "error_type": type(exc).__name__,
            "timestamp": time.time()
        }
        
        # Check for specific error patterns
        error_str = str(exc).lower()
        if "connection" in error_str or "timeout" in error_str:
            status_code = 503
            error_message = "Service temporarily unavailable"
            error_type = "ServiceUnavailable"
        elif "permission" in error_str or "unauthorized" in error_str:
            status_code = 403
            error_message = "Access denied"
            error_type = "AccessDenied"
        elif "not found" in error_str:
            status_code = 404
            error_message = "Resource not found"
            error_type = "NotFound"
        else:
            status_code = 500
            error_message = "Internal server error"
            error_type = "InternalError"
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": error_message,
                "message": "An unexpected error occurred. Please try again later.",
                "type": error_type,
                "request_id": request_id,
                "support_info": "If this error persists, please contact support with the request_id",
                "details": error_details
            }
        )

    # CORS (open by default; tighten as needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(eval_router, prefix="/v1", tags=["evaluation"]) 

    @app.get("/health")
    async def health():
        """Enhanced health check endpoint with comprehensive status monitoring"""
        health_id = f"health_{int(time.time() * 1000)}"
        start_time = time.time()
        
        try:
            logger.info(f"[{health_id}] Starting health check")
            
            # Check basic service health
            health_status = {
                "status": "healthy",
                "version": "1.0.0",
                "prompt_version": "v1.5.0",
                "timestamp": time.time(),
                "health_id": health_id,
                "uptime_seconds": time.time() - start_time,
                "services": {}
            }
            
            # Test prompt loading
            try:
                from app.utils.prompt_loader import PromptLoader
                loader = PromptLoader(version="v1.5.0")
                test_prompt = loader.load_prompt("grammar", "Basic")
                health_status["services"]["prompts"] = "operational" if test_prompt else "degraded"
            except Exception as e:
                logger.warning(f"[{health_id}] Prompt check failed: {e}")
                health_status["services"]["prompts"] = "unavailable"
                health_status["status"] = "degraded"
            
            # Test LLM initialization (without actual API call)
            try:
                from app.client.bootstrap import build_llm
                llm = build_llm()
                health_status["services"]["llm"] = "initialized"
            except Exception as e:
                logger.warning(f"[{health_id}] LLM initialization check failed: {e}")
                health_status["services"]["llm"] = "unavailable"
                health_status["status"] = "degraded"
            
            response_time = (time.time() - start_time) * 1000
            health_status["response_time_ms"] = round(response_time, 1)
            
            logger.info(f"[{health_id}] Health check completed: {health_status['status']} in {response_time:.1f}ms")
            
            # Return appropriate status code based on health
            status_code = 200 if health_status["status"] == "healthy" else 503
            return JSONResponse(
                status_code=status_code,
                content=health_status
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"[{health_id}] Health check failed: {e}")
            
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e),
                    "health_id": health_id,
                    "response_time_ms": round(response_time, 1),
                    "timestamp": time.time()
                }
            )
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
