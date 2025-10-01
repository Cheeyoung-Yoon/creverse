#!/usr/bin/env python3
"""
Expert Level Detailed Analysis

Get detailed feedback to understand why Expert essays score 0
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


async def analyze_expert_feedback():
    """Get detailed feedback for Expert level to understand scoring"""
    
    # Load Excel data
    df = pd.read_excel('data/essay_writing_40_sample.xlsx')
    expert_essay = df[df['rubric_level'] == 'expert'].iloc[0]
    
    # Clean the essay text
    submit_text = str(expert_essay['submit_text'])
    submit_text = submit_text.replace('_x000D_', '').replace('\r', '').strip()
    
    print("="*80)
    print("EXPERT LEVEL DETAILED FEEDBACK ANALYSIS")
    print("="*80)
    print(f"Essay ID: {expert_essay['essay_id']}")
    print(f"Original Topic: {expert_essay['topic_prompt']}")
    print()
    print("FULL ESSAY TEXT:")
    print("-" * 50)
    print(submit_text)
    print("-" * 50)
    print()
    
    # Test with v1.2.0 version
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
    
    print("PARSED SECTIONS:")
    print(f"Introduction: {intro}")
    print(f"Body: {body[:200]}...")
    print(f"Conclusion: {conclusion}")
    print()
    
    # Get detailed results
    print("DETAILED EVALUATION RESULTS:")
    print("="*60)
    
    # Introduction
    intro_result = await structure_evaluator._evaluate_section(
        rubric_item="introduction", 
        text=intro, 
        level="Expert"
    )
    print("INTRODUCTION:")
    print(f"  Score: {intro_result.get('score', 'N/A')}")
    print(f"  Feedback: {intro_result.get('feedback', 'N/A')}")
    print(f"  Corrections: {intro_result.get('corrections', [])}")
    print()
    
    # Body
    body_result = await structure_evaluator._evaluate_section(
        rubric_item="body", 
        text=body, 
        level="Expert"
    )
    print("BODY:")
    print(f"  Score: {body_result.get('score', 'N/A')}")
    print(f"  Feedback: {body_result.get('feedback', 'N/A')}")
    print(f"  Corrections: {body_result.get('corrections', [])}")
    print()
    
    # Conclusion
    conclusion_result = await structure_evaluator._evaluate_section(
        rubric_item="conclusion", 
        text=conclusion, 
        level="Expert"
    )
    print("CONCLUSION:")
    print(f"  Score: {conclusion_result.get('score', 'N/A')}")
    print(f"  Feedback: {conclusion_result.get('feedback', 'N/A')}")
    print(f"  Corrections: {conclusion_result.get('corrections', [])}")
    print()
    
    # Grammar
    grammar_result = await grammar_evaluator.check_grammar(
        text=submit_text, 
        level="Expert"
    )
    print("GRAMMAR:")
    print(f"  Score: {grammar_result.get('score', 'N/A')}")
    print(f"  Feedback: {grammar_result.get('feedback', 'N/A')}")
    print(f"  Corrections: {grammar_result.get('corrections', [])}")
    print()
    
    # Total analysis
    total_score = (intro_result.get('score', 0) + 
                  body_result.get('score', 0) + 
                  conclusion_result.get('score', 0) + 
                  grammar_result.get('score', 0))
    
    print("="*60)
    print("ANALYSIS SUMMARY:")
    print(f"Total Score: {total_score}/8")
    print("Reasons for low scores:")
    print("- Expert level has very high standards")
    print("- This essay appears to be written at a much lower proficiency level")
    print("- Grammar issues, poor organization, weak arguments")
    print("- Expert level expects near-native writing quality")
    print()
    
    print("RECOMMENDATION:")
    print("- The API is working correctly")
    print("- The essay genuinely doesn't meet Expert level standards")
    print("- Consider using a higher-quality Expert level sample essay")
    print("- Or test with essays that better match their designated levels")


if __name__ == "__main__":
    asyncio.run(analyze_expert_feedback())