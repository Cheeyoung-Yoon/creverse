#!/usr/bin/env python3
"""
Dry Run Excel-Based Version Tester

Shows what essays would be tested without actually calling the LLM APIs.
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def dry_run_excel_test(excel_path="data/essay_writing_40_sample.xlsx"):
    """Show what would be tested without running actual evaluations"""
    
    print("="*80)
    print("DRY RUN: Excel-Based Version Testing")
    print("="*80)
    
    # Load Excel data
    excel_file = Path(__file__).parent / excel_path
    
    if not excel_file.exists():
        print(f"Error: Excel file not found: {excel_file}")
        return False
    
    try:
        data = pd.read_excel(excel_file)
        print(f"Loaded Excel data: {data.shape[0]} essays")
        
    except Exception as e:
        print(f"Error loading Excel data: {e}")
        return False
    
    # Show available levels
    levels = data['rubric_level'].dropna().unique()
    print(f"Available rubric levels: {list(levels)}")
    print()
    
    # Select samples for each level
    level_mapping = {
        'basic': 'Basic',
        'intermediate': 'Intermediate',
        'advanced': 'Advanced', 
        'expert': 'Expert'
    }
    
    selected_samples = {}
    
    for level in levels:
        level_essays = data[data['rubric_level'] == level]
        
        if len(level_essays) == 0:
            continue
            
        # Select first essay for this level
        selected_essay = level_essays.iloc[0]
        formatted_level = level_mapping.get(level.lower(), level.title())
        
        selected_samples[formatted_level] = selected_essay
        
        print(f"SELECTED FOR {formatted_level.upper()} LEVEL:")
        print(f"  Essay ID: {selected_essay['essay_id']}")
        print(f"  Topic: {selected_essay['topic_prompt'][:100]}...")
        print(f"  Text Length: {len(str(selected_essay['submit_text']))} characters")
        print(f"  Text Preview: {str(selected_essay['submit_text'])[:200]}...")
        print()
    
    # Show what versions would be tested
    from test_prompt_versions import PromptVersionTester
    tester = PromptVersionTester()
    
    print("AVAILABLE PROMPT VERSIONS:")
    for version in tester.available_versions:
        print(f"  - {version}")
    print()
    
    print("WHAT WOULD BE TESTED:")
    print(f"  Total Essays: {len(selected_samples)}")
    print(f"  Total Versions: {len(tester.available_versions)}")
    print(f"  Total Evaluations: {len(selected_samples) * len(tester.available_versions)}")
    print()
    
    print("EVALUATION BREAKDOWN:")
    for level in selected_samples:
        print(f"  {level} Level:")
        for version in tester.available_versions:
            print(f"    - {version}: Structure evaluation (intro/body/conclusion) + Grammar evaluation")
    print()
    
    print("OUTPUT THAT WOULD BE GENERATED:")
    print("  - Timestamped results directory")
    print("  - Individual level result files (JSON)")
    print("  - Comprehensive results file (JSON)")
    print("  - Summary report (TXT)")
    print("  - Console output with timing and token usage logs")
    print()
    
    print("TO RUN ACTUAL TEST:")
    print("  python batch_excel_version_test.py")
    print("  python batch_excel_version_test.py --versions v1.0.0,v1.2.0")
    print()
    
    return True


if __name__ == "__main__":
    dry_run_excel_test()