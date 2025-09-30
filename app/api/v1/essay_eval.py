import os
import time
from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.client.bootstrap import build_llm
from app.models.request import EssayEvalRequest
from app.models.response import EssayEvalResponse
from app.services.essay_evaluator import EssayEvaluator
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM


# 기본 골조 작성 
async def route_timer(request: Request) -> AsyncIterator[None]:
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    print(f"[API] → {method} {path}", flush=True)
    try:
        yield
    finally:
        dur_ms = (time.perf_counter() - start) * 1000.0
        slow_ms = float(os.getenv("SLOW_REQUEST_MS", "2000"))
        slow_tag = " SLOW" if dur_ms > slow_ms else ""
        print(f"[API] ← {method} {path} {dur_ms:.1f} ms{slow_tag}", flush=True)


router = APIRouter(dependencies=[Depends(route_timer)])


def get_llm() -> LLM:
    # Use ObservedLLM wrapper so Langfuse traces are emitted
    return build_llm()


@lru_cache
def _get_prompt_loader() -> PromptLoader:
    return PromptLoader()


def get_loader() -> PromptLoader:
    return _get_prompt_loader()


def get_evaluator(
    llm: LLM = Depends(get_llm),
    loader: PromptLoader = Depends(get_loader),
) -> EssayEvaluator:
    return EssayEvaluator(llm, loader)


@router.post("/essay-eval", response_model=EssayEvalResponse)
async def essay_eval(
    req: EssayEvalRequest,
    response: Response,
    evaluator: EssayEvaluator = Depends(get_evaluator),
) -> EssayEvalResponse:
    # Start a top-level API trace and pass its id into the evaluator so all spans line up
    try:
        result = await evaluator.evaluate(req)
        # Print step timings and attach Server-Timing header
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
            # Print readable line
            pretty = " ".join([f"{k}={v:.1f}ms" for k, v in timings.items()])
            print(f"[API][TIMING] {pretty}", flush=True)

        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ping")
async def ping():
    llm = build_llm()
    print("LLM type:", type(llm))  # ObservedLLM 여야 함
    res = await llm.run_azure_openai(
        messages=[{"role": "user", "content": "ping"}],
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
            "title": "Ping",
        },
        name="api.ping",
    )
    return {"ok": True, "raw": bool(res)}
