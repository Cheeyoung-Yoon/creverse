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


class EssayEvaluator:
    """Top-level orchestration for essay evaluation.

    Flow:
      pre_process → (grammar | structure) in parallel → aggregate → post_process
    """

    def __init__(self, llm: AzureOpenAILLM, loader: PromptLoader):
        self.llm = llm
        self.loader = loader

    async def evaluate(self, req: EssayEvalRequest) -> Dict[str, Any]:
        # Pre-process
        pre = pre_process_essay(req.submit_text, req.topic_prompt, req.level_group)

        # Evaluators share the same client
        grammar_eval = GrammarEvaluator(client=self.llm)
        structure_eval = StructureEvaluator(client=self.llm)

        # No splitting — pass full text to each section
        intro = body = conclusion = req.submit_text

        # Run grammar + structure in parallel
        grammar_task = asyncio.create_task(grammar_eval.check_grammar(req.submit_text, level=req.level_group))
        structure_task = asyncio.create_task(
            structure_eval.run_structure_chain(intro=intro, body=body, conclusion=conclusion, level=req.level_group)
        )
        grammar_res, structure_res = await asyncio.gather(grammar_task, structure_task)

        # Aggregate score/corrections/feedback
        scf = aggregate_from_run_outputs(pre_process=pre, grammar_result=grammar_res, structure_result=structure_res)

        # Prepare per-item list for post weighting
        items = [structure_res["introduction"], structure_res["body"], structure_res["conclusion"], grammar_res]

        # Post-process with level weighting and validation
        final = finalize_scf(items=items, scf=scf, level_group=req.level_group)

        return {
            "level_group": req.level_group,
            "pre_process": pre,
            "grammar": grammar_res,
            "structure": structure_res,
            "aggregated": final.model_dump(),
        }

