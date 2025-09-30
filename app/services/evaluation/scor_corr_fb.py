from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from app.models.rubric import (
    RubricItemResult,
    Correction,
    ScoreCorrectionFeedback,
    PreProcessResult,
)


def _dedup_corrections(corrections: Iterable[Correction]) -> List[Correction]:
    """Deduplicate corrections by (highlight, issue, correction)."""
    seen: set[tuple[str, str, str]] = set()
    out: List[Correction] = []
    for c in corrections:
        key = (c.highlight, c.issue, c.correction)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _compute_overall_score(items: Sequence[RubricItemResult], pre: PreProcessResult | None) -> int:
    """Compute overall 0–2 score from rubric item scores with light pre-check adjustments.

    Heuristic:
    - Base = average of item scores (0–2 range)
    - If length requirement not met: -0.5
    - If non-English text: -0.5
    - Clamp to [0, 2] and round to nearest int
    """
    if not items:
        return 0
    base = sum(i.score for i in items) / len(items)
    if pre is not None:
        if not pre.meets_length_req:
            base -= 0.5
        if not pre.is_english:
            base -= 0.5
    base = max(0.0, min(2.0, base))
    return int(round(base))


def aggregate_scf(
    *,
    items: Sequence[RubricItemResult] | Sequence[Dict[str, Any]],
    pre_process: Dict[str, Any] | PreProcessResult | None = None,
) -> ScoreCorrectionFeedback:
    """Aggregate rubric results and optional pre-process metadata to Score/Corrections/Feedback.

    - items: sequence of section results (introduction, body, conclusion, grammar)
             as dicts or RubricItemResult objects.
    - pre_process: dict or PreProcessResult with keys (word_count, meets_length_req, is_english)
    """
    # Normalize to Pydantic models
    norm_items: List[RubricItemResult] = [
        i if isinstance(i, RubricItemResult) else RubricItemResult(**i) for i in items
    ]
    pre = (
        pre_process
        if isinstance(pre_process, PreProcessResult)
        else (PreProcessResult(**pre_process) if pre_process else None)
    )

    # Score
    score = _compute_overall_score(norm_items, pre)

    # Corrections: merge and dedup across all items
    merged_corrections = _dedup_corrections(
        c for it in norm_items for c in it.corrections
    )

    # Feedback: include brief pre-check and per-item feedback snippets
    pre_prefix = ""
    if pre is not None:
        pre_prefix = (
            f"[Pre-check] words={pre.word_count}, "
            f"meets_length={pre.meets_length_req}, english={pre.is_english}.\n"
        )
    joined_feedback = pre_prefix + "\n".join(
        f"[{it.rubric_item}] {it.feedback}" for it in norm_items
    )

    return ScoreCorrectionFeedback(
        score=score,
        corrections=merged_corrections,
        feedback=joined_feedback,
    )


def aggregate_from_run_outputs(
    *,
    pre_process: Dict[str, Any] | PreProcessResult | None,
    grammar_result: Dict[str, Any],
    structure_result: Dict[str, Any],
) -> ScoreCorrectionFeedback:
    """Convenience: convert GrammarEvaluator + StructureEvaluator outputs into SCF."""
    items = [
        structure_result.get("introduction", {}),
        structure_result.get("body", {}),
        structure_result.get("conclusion", {}),
        grammar_result,
    ]
    return aggregate_scf(items=items, pre_process=pre_process)

