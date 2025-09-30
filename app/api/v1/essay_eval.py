
import os
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from app.client.azure_openai import AzureOpenAILLM
from app.utils.prompt_loader import PromptLoader
from app.services.essay_evaluator import EssayEvaluator
from app.models.request import EssayEvalRequest
from app.utils.tracer import get_tracer
# 기본 골조 작성 
async def route_timer(request: Request):
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

def get_llm():
    return AzureOpenAILLM()

def get_loader():
    return PromptLoader()

def get_evaluator(llm=Depends(get_llm), loader=Depends(get_loader)):
    return EssayEvaluator(llm, loader)

@router.post("/essay-eval")
async def essay_eval(req: EssayEvalRequest, response: Response, evaluator: EssayEvaluator = Depends(get_evaluator)):
    tracer = get_tracer()
    # Start a top-level API trace and pass its id into the evaluator so all spans line up
    with tracer.traced(name="api.essay_eval", input=req.model_dump()) as tr:
        trace_id = getattr(tr, "id", "")
        try:
            result = await evaluator.evaluate(req, trace_id=trace_id)
            # Print step timings and attach Server-Timing header
            timings = result.get("timings", {})
            if timings:
                parts = []
                for key in ("pre_process", "grammar", "structure", "aggregate", "post_process", "total"):
                    if key in timings:
                        parts.append(f"{key};dur={timings[key]:.1f}")
                header_val = ", ".join(parts)
                if header_val:
                    response.headers["Server-Timing"] = header_val
                # Print readable line
                pretty = " ".join([f"{k}={timings[k]:.1f}ms" for k in timings])
                print(f"[API][TIMING] {pretty}", flush=True)
            try:
                # Attach brief output summary to the API trace
                tr.update(output={
                    "level_group": result.get("level_group"),
                    "score": result.get("aggregated", {}).get("score"),
                })
            except Exception:
                pass
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
