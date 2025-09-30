import sys
import os
import pytest

# Add project root to path like other tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.utils.prompt_loader import PromptLoader
from app.services.essay_evaluator import EssayEvaluator
from app.models.request import EssayEvalRequest
from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator


class _DummyGrammarEvaluator:
    instances = []

    def __init__(self, client=None, loader=None):
        self.client = client
        self.loader = loader
        type(self).instances.append(self)

    async def check_grammar(self, text: str, level: str = "Basic", trace_id: str | None = None):
        return {
            "rubric_item": "grammar",
            "score": 1,
            "corrections": [],
            "feedback": "ok",
            "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "evaluation_type": "grammar_check",
        }


class _DummyStructureEvaluator:
    instances = []

    def __init__(self, client=None, loader=None):
        self.client = client
        self.loader = loader
        type(self).instances.append(self)

    async def run_structure_chain(self, *, intro: str, body: str, conclusion: str, level: str = "Basic", trace_id=None):
        def _sec(name: str):
            return {
                "rubric_item": name,
                "score": 1,
                "corrections": [],
                "feedback": f"{name} ok",
                "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "evaluation_type": "structure_chain",
            }

        return {
            "introduction": _sec("introduction"),
            "body": _sec("body"),
            "conclusion": _sec("conclusion"),
            "token_usage_total": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
            "evaluation_type": "structure_chain",
        }


@pytest.mark.asyncio
async def test_loader_reused_via_essay_evaluator(monkeypatch):
    # Patch EssayEvaluator to use our dummy evaluators
    import app.services.essay_evaluator as essay_eval_mod
    monkeypatch.setattr(essay_eval_mod, "GrammarEvaluator", _DummyGrammarEvaluator)
    monkeypatch.setattr(essay_eval_mod, "StructureEvaluator", _DummyStructureEvaluator)

    loader = PromptLoader()
    # llm is unused by dummies; can be any object
    ev = EssayEvaluator(llm=object(), loader=loader)

    req = EssayEvalRequest(level_group="Basic", topic_prompt="abc", submit_text="this is a sufficiently long essay text for test")
    result = await ev.evaluate(req)

    # Ensure exactly one instance of each was constructed
    assert len(_DummyGrammarEvaluator.instances) == 1
    assert len(_DummyStructureEvaluator.instances) == 1

    # Loader identity should match the one passed into EssayEvaluator
    assert _DummyGrammarEvaluator.instances[0].loader is loader
    assert _DummyStructureEvaluator.instances[0].loader is loader

    # Basic shape checks on evaluation result
    assert "grammar" in result and "structure" in result and "aggregated" in result


def test_loader_can_be_injected_into_evaluators_directly():
    loader = PromptLoader()
    g = GrammarEvaluator(loader=loader)
    s = StructureEvaluator(loader=loader)
    assert g.prompt_loader is loader
    assert s.prompt_loader is loader

