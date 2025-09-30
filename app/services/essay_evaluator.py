
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

    async def evaluate(self, req: EssayEvalRequest) -> Dict[str, Any]:
        # No manual tracing; ObservedLLM handles generation-level tracing.
        return await self._evaluate_impl(req)

    async def _evaluate_impl(self, req: EssayEvalRequest) -> Dict[str, Any]:
        # Timings
        t0 = perf_counter()
        timeline = {"start": datetime.now(timezone.utc).isoformat()}
        timings_ms: Dict[str, float] = {}

        # Pre-process
        pre = pre_process_essay(req.submit_text, req.topic_prompt, req.level_group)
        t1 = perf_counter()
        timings_ms["pre_process"] = (t1 - t0) * 1000.0

        # Evaluators share the same client
        grammar_eval = GrammarEvaluator(client=self.llm)
        structure_eval = StructureEvaluator(client=self.llm)

        # No splitting — pass full text to each section
        intro = body = conclusion = req.submit_text

        # Run grammar + structure in parallel with individual timings
        async def _timed_grammar():
            tg0 = perf_counter()
            res = await grammar_eval.check_grammar(req.submit_text, level=req.level_group)
            timings_ms["grammar"] = (perf_counter() - tg0) * 1000.0
            return res

        async def _timed_structure():
            ts0 = perf_counter()
            res = await structure_eval.run_structure_chain(
                intro=intro, body=body, conclusion=conclusion, level=req.level_group
            )
            timings_ms["structure"] = (perf_counter() - ts0) * 1000.0
            return res

        grammar_res, structure_res = await asyncio.gather(_timed_grammar(), _timed_structure())

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


        return {
            "level_group": req.level_group,
            "pre_process": pre,
            "grammar": grammar_res,
            "structure": structure_res,
            "aggregated": final.model_dump(),
            "timings": timings_ms,
            "timeline": timeline,
        }
