from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.client.azure_openai import AzureOpenAILLM
from app.utils.prompt_loader import PromptLoader
from app.models.request import EssayEvalRequest
from app.services.evaluation.pre_process import pre_process_essay
from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator
from app.services.evaluation.scor_corr_fb import aggregate_from_run_outputs
from app.services.evaluation.post_process import finalize_scf
from app.utils.tracer import get_tracer
from time import perf_counter
from datetime import datetime, timezone


class EssayEvaluator:
    """Top-level orchestration for essay evaluation.

    Flow:
      pre_process → (grammar | structure) in parallel → aggregate → post_process
    """

    def __init__(self, llm: AzureOpenAILLM, loader: PromptLoader):
        self.llm = llm
        self.loader = loader

    async def evaluate(self, req: EssayEvalRequest, trace_id: str | None = None) -> Dict[str, Any]:
        tracer = get_tracer()
        # If a parent trace is provided (e.g., from API layer), use it; otherwise create one
        _created_here = False
        if not trace_id:
            _created_here = True
            with tracer.traced(name="essay_evaluation", input={
                "level_group": req.level_group,
                "topic_prompt": req.topic_prompt,
                "text_len": len(req.submit_text),
            }) as tr:
                trace_id = getattr(tr, "id", "")
                result = await self._evaluate_impl(req, tracer, trace_id)
                return result
        else:
            # Use existing trace id; execute evaluation directly
            return await self._evaluate_impl(req, tracer, trace_id)

    async def _evaluate_impl(self, req: EssayEvalRequest, tracer, trace_id: str) -> Dict[str, Any]:
        # Timings
        t0 = perf_counter()
        timeline = {"start": datetime.now(timezone.utc).isoformat()}
        timings_ms: Dict[str, float] = {}

        # Pre-process
        pre = pre_process_essay(req.submit_text, req.topic_prompt, req.level_group)
        t1 = perf_counter()
        timings_ms["pre_process"] = (t1 - t0) * 1000.0
        # Record pre-process span
        try:
            span = tracer.start_span(trace_id=trace_id, name="pre_process", input={
                "level_group": req.level_group,
                "topic_prompt": req.topic_prompt,
            })
            span.update(output=pre)
        except Exception:
            pass

        # Evaluators share the same client
        grammar_eval = GrammarEvaluator(client=self.llm)
        structure_eval = StructureEvaluator(client=self.llm)

        # No splitting — pass full text to each section
        intro = body = conclusion = req.submit_text

        # Run grammar + structure in parallel with individual timings
        async def _timed_grammar():
            tg0 = perf_counter()
            res = await grammar_eval.check_grammar(req.submit_text, level=req.level_group, trace_id=trace_id)
            timings_ms["grammar"] = (perf_counter() - tg0) * 1000.0
            return res

        async def _timed_structure():
            ts0 = perf_counter()
            res = await structure_eval.run_structure_chain(
                intro=intro, body=body, conclusion=conclusion, level=req.level_group, trace_id=trace_id
            )
            timings_ms["structure"] = (perf_counter() - ts0) * 1000.0
            return res

        grammar_res, structure_res = await asyncio.gather(_timed_grammar(), _timed_structure())

        # Log generations
        model_name = getattr(self.llm, "deployment", None)
        try:
            tracer.log_generation(
                trace_id=trace_id,
                name="grammar_check",
                model=model_name,
                input={"text_len": len(req.submit_text), "level": req.level_group},
                output={k: v for k, v in grammar_res.items() if k != "token_usage"},
                usage=grammar_res.get("token_usage"),
                metadata={"rubric_item": "grammar"},
                tags=["grammar"],
            )
        except Exception:
            pass

        try:
            for section in ("introduction", "body", "conclusion"):
                sec = structure_res.get(section, {})
                tracer.log_generation(
                    trace_id=trace_id,
                    name=f"structure_{section}",
                    model=model_name,
                    input={"section": section, "level": req.level_group, "text_len": len(req.submit_text)},
                    output={k: v for k, v in sec.items() if k != "token_usage"},
                    usage=sec.get("token_usage"),
                    metadata={"rubric_item": section},
                    tags=["structure", section],
                )
        except Exception:
            pass

        # Aggregate score/corrections/feedback
        t2 = perf_counter()
        scf = aggregate_from_run_outputs(
            pre_process=pre, grammar_result=grammar_res, structure_result=structure_res
        )
        t3 = perf_counter()
        timings_ms["aggregate"] = (t3 - t2) * 1000.0

        # Prepare per-item list for post weighting
        items = [
            structure_res["introduction"],
            structure_res["body"],
            structure_res["conclusion"],
            grammar_res,
        ]

        # Post-process with level weighting and validation
        t4 = perf_counter()
        final = finalize_scf(items=items, scf=scf, level_group=req.level_group)
        t5 = perf_counter()
        timings_ms["post_process"] = (t5 - t4) * 1000.0
        timings_ms["total"] = (t5 - t0) * 1000.0
        timeline["end"] = datetime.now(timezone.utc).isoformat()

        # Log final score
        try:
            tracer.log_score(
                trace_id=trace_id,
                name="final_score",
                value=float(final.score),
                metadata={"level_group": req.level_group},
            )
        except Exception:
            pass

        return {
            "level_group": req.level_group,
            "pre_process": pre,
            "grammar": grammar_res,
            "structure": structure_res,
            "aggregated": final.model_dump(),
            "timings": timings_ms,
            "timeline": timeline,
        }
