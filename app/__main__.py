import argparse
import asyncio
import json
import sys
from typing import Tuple

from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator


def _split_into_sections(text: str) -> Tuple[str, str, str]:
    """Split essay text into introduction, body, conclusion heuristically.

    Priority:
    1) Paragraph-based split (blank lines as separators): first → intro, last → conclusion, middle → body.
    2) Sentence-based split: roughly 20/60/20 by sentence count.
    3) Fallback: first sentence intro, last sentence conclusion, rest body.
    """
    # Normalize newlines
    raw = text.strip()
    if not raw:
        return "", "", ""

    # Paragraph split by blank line
    paragraphs = [p.strip() for p in raw.splitlines()]
    # Collapse consecutive blanks to single separators
    blocks = []
    buf = []
    for line in paragraphs:
        if line:
            buf.append(line)
        else:
            if buf:
                blocks.append(" ".join(buf))
                buf = []
    if buf:
        blocks.append(" ".join(buf))

    if len(blocks) >= 3:
        intro = blocks[0]
        conclusion = blocks[-1]
        body = "\n\n".join(blocks[1:-1]).strip()
        return intro, body, conclusion

    # Sentence-based split
    import re
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()]
    n = len(sentences)
    if n == 0:
        return raw, "", ""
    if n <= 2:
        # Minimal split
        if n == 1:
            return sentences[0], "", ""
        return sentences[0], "", sentences[-1]

    intro_count = max(1, int(round(n * 0.2)))
    concl_count = max(1, int(round(n * 0.2)))
    # Ensure at least one sentence remains for body
    if intro_count + concl_count >= n:
        intro_count = 1
        concl_count = 1
    intro = " ".join(sentences[:intro_count])
    body = " ".join(sentences[intro_count : n - concl_count])
    conclusion = " ".join(sentences[n - concl_count :])
    return intro, body, conclusion


async def _amain(text: str, level: str) -> int:
    # Prepare evaluators
    grammar = GrammarEvaluator()
    structure = StructureEvaluator()

    intro, body, conclusion = _split_into_sections(text)

    # Run in parallel
    grammar_task = asyncio.create_task(grammar.check_grammar(text, level=level))
    structure_task = asyncio.create_task(
        structure.run_structure_chain(intro=intro, body=body, conclusion=conclusion, level=level)
    )

    grammar_res, structure_res = await asyncio.gather(grammar_task, structure_task)

    output = {
        "level": level,
        "grammar": grammar_res,
        "structure": structure_res,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run grammar and structure evaluations in parallel")
    parser.add_argument("--level", default="Basic", choices=["Basic", "Intermediate", "Advanced", "Expert"], help="Student level group")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--text", help="Essay text to evaluate")
    group.add_argument("--file", help="Path to a file containing the essay text")
    args = parser.parse_args(argv)

    if args.text:
        text = args.text
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            print(f"Failed to read file: {e}", file=sys.stderr)
            return 2
    else:
        # Read from stdin
        text = sys.stdin.read()

    if not text.strip():
        print("No text provided. Use --text, --file, or pipe input.", file=sys.stderr)
        return 2

    return asyncio.run(_amain(text=text, level=args.level))


if __name__ == "__main__":
    raise SystemExit(main())
