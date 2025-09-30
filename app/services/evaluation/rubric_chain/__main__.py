
import argparse
import asyncio
import json
import logging
import sys

from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator
from app.services.evaluation.rubric_chain.section_splitter import SectionSplitter

logger = logging.getLogger(__name__)


async def _amain(text: str, level: str) -> int:
    grammar = GrammarEvaluator()
    structure = StructureEvaluator()
    splitter = SectionSplitter(client=structure.client, loader=structure.prompt_loader)

    try:
        sections = await splitter.split(text, level)
        intro = sections.introduction
        body = sections.body
        conclusion = sections.conclusion
    except Exception:  # noqa: BLE001
        logger.exception("Section splitting failed; falling back to full text")
        intro = body = conclusion = text

    grammar_task = asyncio.create_task(grammar.check_grammar(text, level=level))
    structure_task = asyncio.create_task(
        structure.run_structure_chain(intro=intro, body=body, conclusion=conclusion, level=level)
    )

    grammar_res, structure_res = await asyncio.gather(grammar_task, structure_task)

    output = {
        "level": level,
        "intro_sample": intro[:120],
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
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to read file: {exc}", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("No text provided. Use --text, --file, or pipe input.", file=sys.stderr)
        return 2

    return asyncio.run(_amain(text=text, level=args.level))


if __name__ == "__main__":
    raise SystemExit(main())
