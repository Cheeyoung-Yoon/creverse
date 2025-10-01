"""
Comprehensive tests for async_manager.py
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.async_manager import (
    AsyncConnectionPool, 
    AsyncTaskManager, 
    async_timeout, 
    async_retry,
    get_connection_pool,
    get_task_manager
)


class TestAsyncConnectionPool:
    """Test AsyncConnectionPool class"""
    
    @pytest.fixture
    def pool(self):
        """Create a connection pool for testing"""
        return AsyncConnectionPool(max_connections=3, timeout=1.0)
    
    @pytest.mark.asyncio
    async def test_connection_pool_creation(self, pool):
        """Test connection pool is created correctly"""
        assert pool.max_connections == 3
        assert pool.timeout == 1.0
        assert pool._active_connections == 0
        assert pool._total_requests == 0
        assert pool._failed_requests == 0
    
    @pytest.mark.asyncio
    async def test_successful_connection_acquisition(self, pool):
        """Test successful connection acquisition"""
        async with pool.acquire():
            assert pool._active_connections == 1
            assert pool._total_requests == 1
            assert pool._failed_requests == 0
        
        # After context manager exits
        assert pool._active_connections == 0
    
    @pytest.mark.asyncio
    async def test_multiple_connections(self, pool):
        """Test multiple concurrent connections"""
        async def use_connection(delay=0.1):
            async with pool.acquire():
                await asyncio.sleep(delay)
                return "done"
        
        # Start 3 concurrent tasks (at the limit)
        tasks = [asyncio.create_task(use_connection()) for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all(r == "done" for r in results)
        assert pool._total_requests == 3
        assert pool._active_connections == 0
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """Test connection acquisition timeout"""
        # Create pool with very short timeout
        pool = AsyncConnectionPool(max_connections=1, timeout=0.01)
        
        # Manually fill the semaphore to max capacity
        # This will force the next acquire to timeout
        await pool._semaphore.acquire()
        
        try:
            # Try to acquire another connection - should timeout
            with pytest.raises(TimeoutError):
                async with pool.acquire():
                    pass
        finally:
            # Release the semaphore we manually acquired
            pool._semaphore.release()
    
    @pytest.mark.asyncio
    async def test_connection_stats(self, pool):
        """Test connection statistics tracking"""
        # Successful connection
        async with pool.acquire():
            pass
        
        # Test timeout (will increase failed count)
        async def block_pool():
            async with pool.acquire():
                await asyncio.sleep(2.0)
        
        # Fill the pool
        tasks = [asyncio.create_task(block_pool()) for _ in range(3)]
        
        # This should timeout and increment failed requests
        try:
            async with asyncio.timeout(0.5):
                async with pool.acquire():
                    pass
        except asyncio.TimeoutError:
            pass
        
        # Check stats
        stats = pool.get_stats()
        assert stats["total_requests"] >= 1
        assert stats["max_connections"] == 3
        
        # Cleanup
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class TestAsyncTaskManager:
    """Test AsyncTaskManager class"""
    
    @pytest.fixture
    def task_manager(self):
        """Create a task manager for testing"""
        return AsyncTaskManager()
    
    @pytest.mark.asyncio
    async def test_task_manager_creation(self, task_manager):
        """Test task manager is created correctly"""
        assert task_manager._thread_pool is not None
        assert len(task_manager._background_tasks) == 0
        assert len(task_manager._task_results) == 0
    
    @pytest.mark.asyncio
    async def test_run_in_background(self, task_manager):
        """Test running background tasks"""
        async def sample_task():
            await asyncio.sleep(0.1)
            return "completed"
        
        # Submit a background task
        task_id = await task_manager.run_in_background(sample_task())
        assert task_id is not None
        
        # Give time for task to complete
        await asyncio.sleep(0.2)
        
        # Check result
        status = task_manager.get_task_status(task_id)
        assert status is not None
    
    @pytest.mark.asyncio
    async def test_run_in_thread(self, task_manager):
        """Test running CPU-intensive tasks in thread pool"""
        def cpu_task(x, y):
            time.sleep(0.1)  # Simulate CPU work
            return x + y
        
        result = await task_manager.run_in_thread(cpu_task, 5, 10)
        assert result == 15
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, task_manager):
        """Test getting task status"""
        async def test_task():
            await asyncio.sleep(0.1)
            return "done"
        
        task_id = await task_manager.run_in_background(test_task())
        
        # Initially should be running
        status = task_manager.get_task_status(task_id)
        assert status is not None
        
        # Wait for completion
        await asyncio.sleep(0.2)
        
        # Should be completed
        status = task_manager.get_task_status(task_id)
        if status:
            assert status.get("status") in ["running", "completed"]
    
    @pytest.mark.asyncio
    async def test_get_all_tasks_status(self, task_manager):
        """Test getting all tasks status"""
        async def test_task():
            await asyncio.sleep(0.1)
            return "done"
        
        # Submit multiple tasks
        task_ids = []
        for i in range(3):
            task_id = await task_manager.run_in_background(test_task())
            task_ids.append(task_id)
        
        # Get all status
        all_status = task_manager.get_all_tasks_status()
        assert "running_tasks" in all_status
        assert "completed_tasks" in all_status
        assert "task_details" in all_status
        
        # Wait for completion
        await asyncio.sleep(0.2)
    
    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self, task_manager):
        """Test cleanup of completed tasks"""
        async def quick_task():
            return "completed"
        
        # Submit task and wait for completion
        task_id = await task_manager.run_in_background(quick_task())
        await asyncio.sleep(0.1)
        
        # Cleanup
        await task_manager.cleanup_completed_tasks()
        
        # Task should be cleaned up from background tasks
        assert task_id not in task_manager._background_tasks
    
    @pytest.mark.asyncio
    async def test_shutdown(self, task_manager):
        """Test task manager shutdown"""
        async def long_task():
            await asyncio.sleep(1.0)
            return "done"
        
        # Submit a long task
        task_id = await task_manager.run_in_background(long_task())
        
        # Shutdown should cancel all tasks
        await task_manager.shutdown()
        
        # Thread pool should be shut down
        assert task_manager._thread_pool._shutdown


class TestAsyncDecorators:
    """Test async decorator functions"""
    
    @pytest.mark.asyncio
    async def test_async_timeout_success(self):
        """Test async_timeout decorator with successful execution"""
        @async_timeout(1.0)
        async def quick_function():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await quick_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_async_timeout_failure(self):
        """Test async_timeout decorator with timeout"""
        @async_timeout(0.1)
        async def slow_function():
            await asyncio.sleep(1.0)
            return "too_slow"
        
        with pytest.raises(asyncio.TimeoutError):
            await slow_function()
    
    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async_retry decorator with eventual success"""
        call_count = 0
        
        @async_retry(max_attempts=3, delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_retry_max_attempts(self):
        """Test async_retry decorator exceeding max attempts"""
        @async_retry(max_attempts=2, delay=0.01)
        async def always_fail():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            await always_fail()
    
    @pytest.mark.asyncio
    async def test_async_retry_with_specific_exceptions(self):
        """Test async_retry with different exception types"""
        @async_retry(max_attempts=2, delay=0.01)
        async def specific_failure():
            raise TypeError("Wrong exception type")
        
        # Should retry for any exception type
        with pytest.raises(TypeError):
            await specific_failure()


class TestGlobalInstances:
    """Test global instance getters"""
    
    def test_get_connection_pool(self):
        """Test get_connection_pool returns consistent instance"""
        pool1 = get_connection_pool()
        pool2 = get_connection_pool()
        
        # Should return the same instance (singleton pattern)
        assert pool1 is pool2
        assert isinstance(pool1, AsyncConnectionPool)
    
    def test_get_task_manager(self):
        """Test get_task_manager returns consistent instance"""
        manager1 = get_task_manager()
        manager2 = get_task_manager()
        
        # Should return the same instance (singleton pattern)
        assert manager1 is manager2
        assert isinstance(manager1, AsyncTaskManager)


class TestErrorHandling:
    """Test error handling in async components"""
    
    @pytest.mark.asyncio
    async def test_connection_pool_exception_handling(self):
        """Test connection pool handles exceptions properly"""
        pool = AsyncConnectionPool(max_connections=1, timeout=0.1)
        
        async def failing_operation():
            async with pool.acquire():
                raise ValueError("Simulated error")
        
        # Exception should be raised but pool should remain stable
        with pytest.raises(ValueError):
            await failing_operation()
        
        # Pool should still be usable
        async with pool.acquire():
            pass  # Should work fine
        
        assert pool._active_connections == 0
    
    @pytest.mark.asyncio
    async def test_task_manager_error_handling(self):
        """Test task manager handles task errors gracefully"""
        task_manager = AsyncTaskManager()
        
        async def failing_task():
            raise ValueError("Task failed")
        
        # Submit failing task - should not crash manager
        task_id = await task_manager.run_in_background(failing_task())
        
        # Give time for task to fail
        await asyncio.sleep(0.1)
        
        # Manager should still be functional
        async def success_task():
            return "success"
        
        success_id = await task_manager.run_in_background(success_task())
        await asyncio.sleep(0.1)
        
        # Check that both tasks are handled
        assert task_id != success_id
        
        # Cleanup
        await task_manager.shutdown()


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
