import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.evaluation.scor_corr_fb import aggregate_scf, aggregate_from_run_outputs
from app.models.rubric import RubricItemResult, Correction, ScoreCorrectionFeedback


def _mk_item(name: str, score: int, fb: str):
    return {
        "rubric_item": name,
        "score": score,
        "corrections": [
            {"highlight": "I want go", "issue": "missing to-be", "correction": "I want to go"}
        ],
        "feedback": fb,
    }


def test_aggregate_scf_basic():
    items = [
        _mk_item("introduction", 2, "Good intro"),
        _mk_item("body", 1, "Body ok"),
        _mk_item("conclusion", 2, "Nice close"),
        _mk_item("grammar", 0, "Needs grammar work"),
    ]
    pre = {"word_count": 120, "meets_length_req": True, "is_english": True}

    scf = aggregate_scf(items=items, pre_process=pre)
    assert isinstance(scf, ScoreCorrectionFeedback)
    assert scf.score in (1, 2)  # average rounds to a valid 0-2
    assert isinstance(scf.corrections, list) and len(scf.corrections) == 1
    assert isinstance(scf.feedback, str) and "[Pre-check]" in scf.feedback


def test_aggregate_from_run_outputs():
    structure = {
        "introduction": _mk_item("introduction", 1, "intro fb"),
        "body": _mk_item("body", 1, "body fb"),
        "conclusion": _mk_item("conclusion", 1, "concl fb"),
        "token_usage_total": {"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45},
        "evaluation_type": "structure_chain",
    }
    grammar = _mk_item("grammar", 1, "grammar fb")
    pre = {"word_count": 30, "meets_length_req": False, "is_english": True}

    scf = aggregate_from_run_outputs(pre_process=pre, grammar_result=grammar, structure_result=structure)
    assert scf.score in (0, 1, 2)
    assert len(scf.corrections) == 1
    assert "[introduction]" in scf.feedback and "[grammar]" in scf.feedback

