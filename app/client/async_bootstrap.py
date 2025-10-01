# app/client/async_bootstrap.py
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from app.client.azure_openai import AzureOpenAILLM
from app.utils.tracer import ObservedLLM, LLM

class AsyncLLMManager:
    """Async LLM connection pool manager"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._semaphore = asyncio.Semaphore(max_connections)
        self._llm_instance: Optional[LLM] = None
        self._lock = asyncio.Lock()
    
    async def get_llm(self) -> LLM:
        """Get LLM instance with connection pooling"""
        if self._llm_instance is None:
            async with self._lock:
                if self._llm_instance is None:
                    base = AzureOpenAILLM()
                    self._llm_instance = ObservedLLM(base)
        
        return self._llm_instance
    
    @asynccontextmanager
    async def acquire_llm(self):
        """Context manager for LLM with semaphore control"""
        async with self._semaphore:
            llm = await self.get_llm()
            try:
                yield llm
            finally:
                # Cleanup if needed
                pass
    
    async def health_check(self) -> bool:
        """Check if LLM service is healthy"""
        try:
            async with self.acquire_llm() as llm:
                await asyncio.wait_for(
                    llm.run_azure_openai(
                        messages=[{"role": "user", "content": "ping"}],
                        json_schema={
                            "type": "object",
                            "properties": {"ok": {"type": "boolean"}},
                            "required": ["ok"]
                        }
                    ),
                    timeout=10.0
                )
            return True
        except Exception:
            return False

# Global instance
_llm_manager: Optional[AsyncLLMManager] = None

async def get_llm_manager() -> AsyncLLMManager:
    """Get global LLM manager instance"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = AsyncLLMManager()
    return _llm_manager

async def build_llm() -> LLM:
    """Build LLM with async manager"""
    manager = await get_llm_manager()
    return await manager.get_llm()