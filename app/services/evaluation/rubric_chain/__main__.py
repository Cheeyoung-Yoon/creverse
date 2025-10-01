import argparse
import asyncio
import json
import sys

from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator


async def _amain(text: str, level: str) -> int:


    # Prepare evaluators
    grammar = GrammarEvaluator()
    structure = StructureEvaluator()

    # Use full text for each section (no splitting)
    intro = body = conclusion = text

    # Run in parallel
    grammar_task = asyncio.create_task(grammar.check_grammar(text, level=level))
    structure_task = asyncio.create_task(
        structure.run_structure_chain(intro=intro, body=body, conclusion=conclusion, level=level)
    )
    
    grammar_res, structure_res = await asyncio.gather(grammar_task, structure_task)

    # We only create a parent trace and pass trace_id to client calls.
    # Client logs the generations; avoid duplicate logging here

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

