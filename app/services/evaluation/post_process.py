from __future__ import annotations

from typing import Dict, Any, List, Sequence, Mapping

from app.models.rubric import RubricItemResult, ScoreCorrectionFeedback


# Level-specific weights for rubric items (must sum to 1.0)
LEVEL_WEIGHTS: Mapping[str, Mapping[str, float]] = {
    "Basic": {
        "introduction": 0.30,
        "body": 0.30,
        "conclusion": 0.20,
        "grammar": 0.20,
    },
    "Intermediate": {
        "introduction": 0.25,
        "body": 0.35,
        "conclusion": 0.20,
        "grammar": 0.20,
    },
    "Advanced": {
        "introduction": 0.20,
        "body": 0.40,
        "conclusion": 0.15,
        "grammar": 0.25,
    },
    "Expert": {
        "introduction": 0.15,
        "body": 0.40,
        "conclusion": 0.15,
        "grammar": 0.30,
    },
}


def _weighted_score(items: Sequence[RubricItemResult], level_group: str) -> int:
    weights = LEVEL_WEIGHTS.get(level_group) or LEVEL_WEIGHTS["Basic"]
    # Normalize to 0..2 scale via weighted average
    total = 0.0
    for it in items:
        w = float(weights.get(it.rubric_item, 0.0))
        total += w * it.score
    # Scores are 0..2 already; weights sum 1.0, so total in 0..2
    # Round to nearest int for final rubric scale
    if total < 0.0:
        total = 0.0
    if total > 2.0:
        total = 2.0
    return int(round(total))


def finalize_scf(
    *,
    items: Sequence[RubricItemResult] | Sequence[Dict[str, Any]],
    scf: Dict[str, Any] | ScoreCorrectionFeedback,
    level_group: str,
    max_corrections: int | None = 50,
) -> ScoreCorrectionFeedback:
    """Apply level weighting and validate the final Score/Corrections/Feedback.

    - items: per-rubric results needed to compute weighted score
    - scf: aggregated result from scor_corr_fb.aggregate_scf or aggregate_from_run_outputs
    - level_group: "Basic" | "Intermediate" | "Advanced" | "Expert"
    - max_corrections: optional cap on number of corrections included
    """
    norm_items: List[RubricItemResult] = [
        it if isinstance(it, RubricItemResult) else RubricItemResult(**it) for it in items
    ]
    current = scf if isinstance(scf, ScoreCorrectionFeedback) else ScoreCorrectionFeedback(**scf)

    # Compute weighted score from items and override
    weighted = _weighted_score(norm_items, level_group)
    current.score = weighted

    # Cap corrections if requested
    if max_corrections is not None and len(current.corrections) > max_corrections:
        current.corrections = current.corrections[:max_corrections]

    # Re-validate by re-instantiating the model (ensures bounds/types)
    return ScoreCorrectionFeedback(**current.model_dump())

