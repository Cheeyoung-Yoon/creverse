# app/core/dependencies.py
import asyncio
import logging
from functools import lru_cache
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException

from app.client.bootstrap import build_llm
from app.models.request import EssayEvalRequest
from app.services.essay_evaluator import EssayEvaluator
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM
from app.core.async_manager import get_connection_pool, get_task_manager, AsyncConnectionPool, AsyncTaskManager

logger = logging.getLogger(__name__)

# 비동기 LLM 클라이언트 관리
class AsyncLLMManager:
    """비동기 LLM 클라이언트 매니저"""
    
    def __init__(self):
        self._llm_instance: Optional[LLM] = None
        self._initialization_lock = asyncio.Lock()
        self._is_initializing = False
        
    async def get_llm(self) -> LLM:
        """비동기적으로 LLM 인스턴스 획득"""
        if self._llm_instance is not None:
            return self._llm_instance
            
        async with self._initialization_lock:
            if self._llm_instance is not None:
                return self._llm_instance
                
            if self._is_initializing:
                # 다른 코루틴이 초기화 중이면 대기
                while self._is_initializing:
                    await asyncio.sleep(0.1)
                return self._llm_instance
            
            try:
                self._is_initializing = True
                logger.info("Initializing LLM client asynchronously")
                
                # CPU 집약적인 초기화 작업을 스레드 풀에서 실행
                task_manager = get_task_manager()
                self._llm_instance = await task_manager.run_in_thread(build_llm)
                
                logger.info("LLM client initialized successfully")
                return self._llm_instance
                
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Failed to initialize AI service",
                        "type": "ServiceInitializationError"
                    }
                )
            finally:
                self._is_initializing = False

# 비동기 PromptLoader 관리
class AsyncPromptManager:
    """비동기 프롬프트 매니저"""
    
    def __init__(self, fixed_version: str = "v1.5.0"):
        self.fixed_version = fixed_version
        self._loader_cache: Dict[str, PromptLoader] = {}
        self._cache_lock = asyncio.Lock()
        
    async def get_loader(self, version: Optional[str] = None) -> PromptLoader:
        """비동기적으로 PromptLoader 획득"""
        version = version or self.fixed_version
        
        if version in self._loader_cache:
            return self._loader_cache[version]
            
        async with self._cache_lock:
            if version in self._loader_cache:
                return self._loader_cache[version]
            
            try:
                logger.info(f"Loading prompts for version {version}")
                
                # 프롬프트 로딩을 스레드 풀에서 실행 (람다 함수 사용)
                task_manager = get_task_manager()
                loader = await task_manager.run_in_thread(lambda: PromptLoader(version=version))
                
                # 프롬프트 유효성 검증
                await self._validate_prompts(loader)
                
                self._loader_cache[version] = loader
                logger.info(f"Prompts loaded successfully for version {version}")
                return loader
                
            except Exception as e:
                logger.error(f"Failed to load prompts for version {version}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": f"Failed to load prompts for version {version}",
                        "type": "PromptLoadError",
                        "version": version
                    }
                )
    
    async def _validate_prompts(self, loader: PromptLoader):
        """프롬프트 유효성 검증"""
        try:
            test_sections = ["grammar", "introduction", "body", "conclusion"]
            test_level = "Basic"
            
            for section in test_sections:
                prompt = loader.load_prompt(section, test_level)
                if not prompt or len(prompt.strip()) < 10:
                    raise ValueError(f"Invalid prompt for {section}/{test_level}")
                    
        except Exception as e:
            raise ValueError(f"Prompt validation failed: {e}")

# 전역 매니저 인스턴스
_llm_manager: Optional[AsyncLLMManager] = None
_prompt_manager: Optional[AsyncPromptManager] = None

def get_llm_manager() -> AsyncLLMManager:
    """전역 LLM 매니저 인스턴스 반환"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = AsyncLLMManager()
    return _llm_manager

def get_prompt_manager() -> AsyncPromptManager:
    """전역 프롬프트 매니저 인스턴스 반환"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = AsyncPromptManager()
    return _prompt_manager

# FastAPI 의존성 함수들
async def get_async_llm() -> LLM:
    """비동기 LLM 의존성"""
    manager = get_llm_manager()
    return await manager.get_llm()

async def get_async_prompt_loader(version: Optional[str] = None) -> PromptLoader:
    """비동기 PromptLoader 의존성"""
    manager = get_prompt_manager()
    return await manager.get_loader(version)

async def get_connection_pool_dep() -> AsyncConnectionPool:
    """연결 풀 의존성"""
    return get_connection_pool()

async def get_task_manager_dep() -> AsyncTaskManager:
    """태스크 매니저 의존성"""
    return get_task_manager()

@asynccontextmanager
async def get_async_evaluator(
    llm: LLM = Depends(get_async_llm),
    loader: PromptLoader = Depends(get_async_prompt_loader)
) -> AsyncGenerator[EssayEvaluator, None]:
    """비동기 EssayEvaluator 컨텍스트 매니저"""
    pool = get_connection_pool()
    
    async with pool.acquire():
        evaluator = EssayEvaluator(llm, loader)
        try:
            yield evaluator
        except Exception as e:
            logger.error(f"Error in evaluator context: {e}")
            raise
        finally:
            # 리소스 정리 작업
            await asyncio.sleep(0)  # 다른 코루틴에게 제어권 양보

# 성능 모니터링을 위한 의존성
class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self):
        self.request_count = 0
        self.total_response_time = 0.0
        self.slow_requests = 0
        self.error_count = 0
        
    def record_request(self, response_time: float, success: bool = True):
        """요청 기록"""
        self.request_count += 1
        self.total_response_time += response_time
        
        if response_time > 5000:  # 5초 이상
            self.slow_requests += 1
            
        if not success:
            self.error_count += 1
    
    def get_stats(self) -> dict:
        """통계 반환"""
        if self.request_count == 0:
            return {
                "total_requests": 0,
                "average_response_time": 0,
                "slow_request_ratio": 0,
                "error_ratio": 0
            }
            
        return {
            "total_requests": self.request_count,
            "average_response_time": self.total_response_time / self.request_count,
            "slow_request_ratio": self.slow_requests / self.request_count,
            "error_ratio": self.error_count / self.request_count
        }

_performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """성능 모니터 인스턴스 반환"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

# 리소스 정리 함수
async def cleanup_async_resources():
    """비동기 리소스 정리"""
    logger.info("Starting async resource cleanup")
    
    # 태스크 매니저 정리
    task_manager = get_task_manager()
    await task_manager.cleanup_completed_tasks()
    await task_manager.shutdown()
    
    logger.info("Async resource cleanup completed")

from typing import Dict