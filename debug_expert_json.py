#!/usr/bin/env python3
"""
Expert Level JSON Debug Script

Test just the Expert level essay to see exact JSON parsing errors
"""

import asyncio
import json
import sys
from pathlib import Path
import pandas as pd

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.client.bootstrap import build_llm
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator
from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.utils.prompt_loader import PromptLoader


async def debug_expert_json():
    """Debug Expert level JSON parsing issues"""
    
    # Load Excel data
    df = pd.read_excel('data/essay_writing_40_sample.xlsx')
    expert_essay = df[df['rubric_level'] == 'expert'].iloc[0]
    
    # Clean the essay text
    submit_text = str(expert_essay['submit_text'])
    submit_text = submit_text.replace('_x000D_', '').replace('\r', '').strip()
    
    print("="*80)
    print("EXPERT LEVEL JSON DEBUG")
    print("="*80)
    print(f"Essay ID: {expert_essay['essay_id']}")
    print(f"Text length: {len(submit_text)} characters")
    print(f"Text preview: {submit_text[:200]}...")
    print()
    
    # Test with v1.2.0 version (known to work with other levels)
    version = "v1.2.0"
    llm_client = build_llm()
    prompt_loader = PromptLoader(version=version)
    
    # Create evaluators
    structure_evaluator = StructureEvaluator(client=llm_client, loader=prompt_loader)
    grammar_evaluator = GrammarEvaluator(client=llm_client, loader=prompt_loader)
    
    # Parse essay sections
    lines = submit_text.strip().split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    # Simple parsing for expert level
    intro_end = max(1, len(lines) // 4)
    conclusion_start = max(len(lines) - len(lines) // 4, intro_end + 1)
    
    intro = ' '.join(lines[:intro_end])
    body = ' '.join(lines[intro_end:conclusion_start])
    conclusion = ' '.join(lines[conclusion_start:])
    
    print("TESTING INDIVIDUAL COMPONENTS:")
    print("-" * 40)
    
    # Test introduction
    try:
        print("Testing Introduction...")
        intro_result = await structure_evaluator._evaluate_section(
            rubric_item="introduction", 
            text=intro, 
            level="Expert"
        )
        print("✓ Introduction: SUCCESS")
        print(f"  Score: {intro_result.get('score', 'N/A')}")
    except Exception as e:
        print("✗ Introduction: FAILED")
        print(f"  Error: {e}")
        print()
    
    # Test body  
    try:
        print("Testing Body...")
        body_result = await structure_evaluator._evaluate_section(
            rubric_item="body", 
            text=body, 
            level="Expert"
        )
        print("✓ Body: SUCCESS")
        print(f"  Score: {body_result.get('score', 'N/A')}")
    except Exception as e:
        print("✗ Body: FAILED")
        print(f"  Error: {e}")
        print()
    
    # Test conclusion
    try:
        print("Testing Conclusion...")
        conclusion_result = await structure_evaluator._evaluate_section(
            rubric_item="conclusion", 
            text=conclusion, 
            level="Expert"
        )
        print("✓ Conclusion: SUCCESS")
        print(f"  Score: {conclusion_result.get('score', 'N/A')}")
    except Exception as e:
        print("✗ Conclusion: FAILED")
        print(f"  Error: {e}")
        print()
    
    # Test grammar
    try:
        print("Testing Grammar...")
        grammar_result = await grammar_evaluator.check_grammar(
            text=submit_text, 
            level="Expert"
        )
        print("✓ Grammar: SUCCESS")
        print(f"  Score: {grammar_result.get('score', 'N/A')}")
    except Exception as e:
        print("✗ Grammar: FAILED")
        print(f"  Error: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(debug_expert_json())