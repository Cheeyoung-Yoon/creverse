# app/core/async_manager.py
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Callable, Awaitable
from concurrent.futures import ThreadPoolExecutor
import time
from functools import wraps, partial

logger = logging.getLogger(__name__)

class AsyncConnectionPool:
    """비동기 연결 풀 관리자"""
    
    def __init__(self, max_connections: int = 10, timeout: float = 30.0):
        self.max_connections = max_connections
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_connections)
        self._active_connections = 0
        self._total_requests = 0
        self._failed_requests = 0
        self._lock = asyncio.Lock()
        
    @asynccontextmanager
    async def acquire(self):
        """연결 획득 컨텍스트 매니저"""
        acquired_at = time.time()
        
        try:
            # 타임아웃과 함께 세마포어 획득
            async with asyncio.timeout(self.timeout):
                async with self._semaphore:
                    async with self._lock:
                        self._active_connections += 1
                        self._total_requests += 1
                    
                    logger.debug(f"Connection acquired. Active: {self._active_connections}/{self.max_connections}")
                    yield
                    
        except asyncio.TimeoutError:
            async with self._lock:
                self._failed_requests += 1
            logger.error(f"Connection acquisition timeout after {self.timeout}s")
            raise
        except Exception as e:
            async with self._lock:
                self._failed_requests += 1
            logger.error(f"Connection acquisition failed: {e}")
            raise
        finally:
            async with self._lock:
                self._active_connections -= 1
            
            duration = time.time() - acquired_at
            logger.debug(f"Connection released after {duration:.2f}s. Active: {self._active_connections}")
    
    def get_stats(self) -> Dict[str, Any]:
        """연결 풀 통계 반환"""
        return {
            "max_connections": self.max_connections,
            "active_connections": self._active_connections,
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "success_rate": (
                (self._total_requests - self._failed_requests) / self._total_requests 
                if self._total_requests > 0 else 0
            )
        }

class AsyncTaskManager:
    """비동기 작업 관리자"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._task_results: Dict[str, Any] = {}
        
    async def run_in_background(
        self, 
        coro: Awaitable, 
        task_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> str:
        """백그라운드에서 코루틴 실행"""
        if task_id is None:
            task_id = f"task_{int(time.time() * 1000)}"
        
        async def _wrapped_task():
            try:
                if timeout:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                else:
                    result = await coro
                self._task_results[task_id] = {"status": "completed", "result": result}
                logger.info(f"Background task {task_id} completed successfully")
            except asyncio.TimeoutError:
                self._task_results[task_id] = {"status": "timeout", "error": "Task timeout"}
                logger.error(f"Background task {task_id} timed out")
            except Exception as e:
                self._task_results[task_id] = {"status": "failed", "error": str(e)}
                logger.error(f"Background task {task_id} failed: {e}")
            finally:
                self._background_tasks.pop(task_id, None)
        
        task = asyncio.create_task(_wrapped_task())
        self._background_tasks[task_id] = task
        logger.info(f"Started background task {task_id}")
        return task_id
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """CPU 집약적 작업을 스레드 풀에서 실행"""
        loop = asyncio.get_event_loop()
        if kwargs:
            # 키워드 인수가 있는 경우 partial을 사용
            partial_func = partial(func, *args, **kwargs)
            return await loop.run_in_executor(self._thread_pool, partial_func)
        else:
            # 키워드 인수가 없는 경우 직접 전달
            return await loop.run_in_executor(self._thread_pool, func, *args)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """태스크 상태 확인"""
        if task_id in self._background_tasks:
            task = self._background_tasks[task_id]
            return {
                "status": "running",
                "done": task.done(),
                "cancelled": task.cancelled()
            }
        elif task_id in self._task_results:
            return self._task_results[task_id]
        else:
            return None
    
    def get_all_tasks_status(self) -> Dict[str, Any]:
        """모든 태스크 상태 반환"""
        return {
            "running_tasks": len(self._background_tasks),
            "completed_tasks": len(self._task_results),
            "task_details": {
                **{tid: {"status": "running"} for tid in self._background_tasks.keys()},
                **self._task_results
            }
        }
    
    async def cleanup_completed_tasks(self):
        """완료된 태스크 정리"""
        completed_tasks = [
            task_id for task_id, task in self._background_tasks.items() 
            if task.done()
        ]
        
        for task_id in completed_tasks:
            task = self._background_tasks.pop(task_id)
            try:
                await task
            except Exception as e:
                logger.error(f"Error in completed task {task_id}: {e}")
        
        logger.info(f"Cleaned up {len(completed_tasks)} completed tasks")
    
    async def shutdown(self):
        """모든 태스크 정리 및 스레드 풀 종료"""
        # 실행 중인 태스크들 취소
        for task_id, task in self._background_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled background task {task_id}")
        
        # 태스크 완료 대기
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks.values(), return_exceptions=True)
        
        # 스레드 풀 종료
        self._thread_pool.shutdown(wait=True)
        logger.info("AsyncTaskManager shutdown completed")

# 전역 인스턴스
_connection_pool: Optional[AsyncConnectionPool] = None
_task_manager: Optional[AsyncTaskManager] = None

def get_connection_pool() -> AsyncConnectionPool:
    """전역 연결 풀 인스턴스 반환"""
    global _connection_pool
    if _connection_pool is None:
        max_conn = int(os.getenv("MAX_CONNECTIONS", "10"))
        timeout = float(os.getenv("CONNECTION_TIMEOUT", "30.0"))
        _connection_pool = AsyncConnectionPool(max_conn, timeout)
    return _connection_pool

def get_task_manager() -> AsyncTaskManager:
    """전역 태스크 매니저 인스턴스 반환"""
    global _task_manager
    if _task_manager is None:
        max_workers = int(os.getenv("MAX_WORKERS", "4"))
        _task_manager = AsyncTaskManager(max_workers)
    return _task_manager

def async_timeout(timeout: float):
    """비동기 함수 타임아웃 데코레이터"""
    def decorator(func: Callable[..., Awaitable]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"Function {func.__name__} timed out after {timeout}s")
                raise
        return wrapper
    return decorator

def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """비동기 함수 재시도 데코레이터"""
    def decorator(func: Callable[..., Awaitable]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator

import os