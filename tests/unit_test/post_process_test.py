import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.evaluation.post_process import finalize_scf


def _item(name: str, score: int):
    return {
        "rubric_item": name,
        "score": score,
        "corrections": [
            {"highlight": "h", "issue": "i", "correction": "c"}
        ],
        "feedback": f"{name} fb"
    }


def _scf(score: int, n_corr: int = 1):
    return {
        "score": score,
        "corrections": [
            {"highlight": f"h{k}", "issue": "i", "correction": "c"} for k in range(n_corr)
        ],
        "feedback": "joined"
    }


def test_finalize_scf_weighting_and_cap():
    items = [
        _item("introduction", 2),
        _item("body", 1),
        _item("conclusion", 2),
        _item("grammar", 0),
    ]
    scf = _scf(score=2, n_corr=100)

    out = finalize_scf(items=items, scf=scf, level_group="Basic", max_corrections=10)
    assert out.score in (1, 2)
    assert len(out.corrections) == 10
    assert isinstance(out.feedback, str)

