import os
import time
import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, Request, Response, BackgroundTasks
from fastapi.concurrency import run_in_threadpool

from app.client.bootstrap import build_llm
from app.models.request import EssayEvalRequest
from app.models.response import EssayEvalResponse
from app.services.essay_evaluator import EssayEvaluator
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM
from app.core.exceptions import (
    EvaluationException, 
    LLMConnectionException, 
    TokenLimitException,
    ValidationException
)

# Request timeout configuration
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
SLOW_REQUEST_MS = float(os.getenv("SLOW_REQUEST_MS", "2000"))

# Enhanced route timer with timeout
@asynccontextmanager
async def route_timer_with_timeout(request: Request) -> AsyncIterator[None]:
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    print(f"[API] → {method} {path}", flush=True)
    
    try:
        # Set timeout for the request
        yield
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408, 
            detail="Request timeout - evaluation took too long"
        )
    finally:
        dur_ms = (time.perf_counter() - start) * 1000.0
        slow_tag = " SLOW" if dur_ms > SLOW_REQUEST_MS else ""
        print(f"[API] ← {method} {path} {dur_ms:.1f} ms{slow_tag}", flush=True)

router = APIRouter()

# Async dependency for LLM
async def get_llm() -> LLM:
    """Get LLM instance asynchronously"""
    # Move LLM initialization to thread pool if needed
    return await run_in_threadpool(build_llm)

# Async dependency for PromptLoader
@lru_cache(maxsize=10)
def _cached_prompt_loader(version: str = "v1.0.0") -> PromptLoader:
    return PromptLoader(version=version)

async def get_loader(version: str = "v1.0.0") -> PromptLoader:
    """Get PromptLoader instance asynchronously"""
    return await run_in_threadpool(_cached_prompt_loader, version)

async def get_evaluator(
    llm: LLM = Depends(get_llm),
    loader: PromptLoader = Depends(get_loader),
) -> EssayEvaluator:
    """Get EssayEvaluator instance"""
    return EssayEvaluator(llm, loader)

@router.post("/essay-eval", response_model=EssayEvalResponse)
async def essay_eval(
    req: EssayEvalRequest,
    response: Response,
    background_tasks: BackgroundTasks,
) -> EssayEvalResponse:
    """Evaluate essay with enhanced error handling and timeout"""
    
    try:
        # Validate request early
        if len(req.submit_text.strip()) < 10:
            raise ValidationException(
                "Essay text too short", 
                {"min_length": 10, "actual_length": len(req.submit_text.strip())}
            )
        
        # Create evaluator with specified version
        llm = await get_llm()
        loader = await get_loader(req.prompt_version or "v1.0.0")
        evaluator = EssayEvaluator(llm, loader)
        
        # Run evaluation with timeout
        result = await asyncio.wait_for(
            evaluator.evaluate(req), 
            timeout=REQUEST_TIMEOUT
        )
        
        # Add timing headers
        timings = result.timings
        if timings:
            timing_parts = []
            for key in ("pre_process", "grammar", "structure", "aggregate", "post_process", "total"):
                duration = timings.get(key)
                if duration is not None:
                    timing_parts.append(f"{key};dur={duration:.1f}")
            
            if timing_parts:
                response.headers["Server-Timing"] = ", ".join(timing_parts)
            
            # Log performance metrics in background
            background_tasks.add_task(
                log_performance_metrics, 
                req.rubric_level, 
                timings
            )
        
        return result
        
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail="Evaluation timeout - please try with shorter text"
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": e.message,
                "details": e.details
            }
        )
    except LLMConnectionException as e:
        raise HTTPException(
            status_code=503,
            detail="External AI service temporarily unavailable"
        )
    except TokenLimitException as e:
        raise HTTPException(
            status_code=413,
            detail="Text too long - please shorten your essay"
        )
    except EvaluationException as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": e.message,
                "type": e.__class__.__name__
            }
        )
    except Exception as exc:
        # Log unexpected errors with more context
        import traceback
        print(f"[ERROR] Unexpected error in essay evaluation: {exc}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error - please try again later"
        )

@router.get("/ping")
async def ping():
    """Health check endpoint with timeout"""
    try:
        llm = await asyncio.wait_for(get_llm(), timeout=10.0)
        
        res = await asyncio.wait_for(
            llm.run_azure_openai(
                messages=[{"role": "user", "content": "ping"}],
                json_schema={
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                    "title": "Ping",
                },
                name="api.ping",
            ),
            timeout=30.0
        )
        return {"ok": True, "raw": bool(res)}
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Ping timeout")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

async def log_performance_metrics(level: str, timings: dict):
    """Background task to log performance metrics"""
    try:
        # Log to monitoring system, metrics DB, etc.
        print(f"[METRICS] Level: {level}, Timings: {timings}")
        # Could send to Langfuse, DataDog, etc.
    except Exception as e:
        print(f"[WARNING] Failed to log metrics: {e}")