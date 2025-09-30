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


class EssayEvaluator:
    """Top-level orchestration for essay evaluation.

    Flow:
      pre_process → (grammar | structure) in parallel → aggregate → post_process
    """

    def __init__(self, llm: AzureOpenAILLM, loader: PromptLoader):
        self.llm = llm
        self.loader = loader

    async def evaluate(self, req: EssayEvalRequest) -> Dict[str, Any]:
        tracer = get_tracer()
        with tracer.traced(name="essay_evaluation", input={
            "level_group": req.level_group,
            "topic_prompt": req.topic_prompt,
            "text_len": len(req.submit_text),
        }) as tr:
            trace_id = getattr(tr, "id", "")

            # Pre-process
            pre = pre_process_essay(req.submit_text, req.topic_prompt, req.level_group)
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

            # Run grammar + structure in parallel
            grammar_task = asyncio.create_task(
                grammar_eval.check_grammar(req.submit_text, level=req.level_group)
            )
            structure_task = asyncio.create_task(
                structure_eval.run_structure_chain(
                    intro=intro, body=body, conclusion=conclusion, level=req.level_group
                )
            )
            grammar_res, structure_res = await asyncio.gather(grammar_task, structure_task)

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
            scf = aggregate_from_run_outputs(
                pre_process=pre, grammar_result=grammar_res, structure_result=structure_res
            )

            # Prepare per-item list for post weighting
            items = [
                structure_res["introduction"],
                structure_res["body"],
                structure_res["conclusion"],
                grammar_res,
            ]

            # Post-process with level weighting and validation
            final = finalize_scf(items=items, scf=scf, level_group=req.level_group)

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
            }
