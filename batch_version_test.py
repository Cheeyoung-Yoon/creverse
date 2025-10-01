#!/usr/bin/env python3
"""
Batch Version Testing Script

Run multiple version comparisons across different essays and levels.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from test_prompt_versions import PromptVersionTester


async def run_batch_tests():
    """Run comprehensive batch tests across multiple scenarios"""
    
    tester = PromptVersionTester()
    
    # Test scenarios
    scenarios = [
        {
            "name": "Basic_Technology_Comparison",
            "essay_file": "sample_essays/basic_technology.txt",
            "versions": ["v1.0.0", "v1.2.0", "v1.3.0"],
            "level": "Basic"
        },
        {
            "name": "Intermediate_Technology_Comparison", 
            "essay_file": "sample_essays/intermediate_technology.txt",
            "versions": ["v1.0.0", "v1.2.0", "v1.3.0"],
            "level": "Intermediate"
        },
        {
            "name": "Advanced_Technology_Comparison",
            "essay_file": "sample_essays/advanced_technology.txt", 
            "versions": ["v1.0.0", "v1.2.0", "v1.3.0"],
            "level": "Advanced"
        },
        {
            "name": "Basic_Education_Comparison",
            "essay_file": "sample_essays/basic_education.txt",
            "versions": ["v1.0.0", "v1.2.0", "v1.3.0"], 
            "level": "Basic"
        }
    ]
    
    results = {}
    
    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"RUNNING SCENARIO: {scenario['name']}")
        print(f"{'='*80}")
        
        try:
            # Load essay
            essay_path = Path(__file__).parent / scenario["essay_file"]
            if not essay_path.exists():
                print(f"Warning: Essay file {scenario['essay_file']} not found. Skipping.")
                continue
                
            with open(essay_path, 'r', encoding='utf-8') as f:
                essay_text = f.read().strip()
            
            # Run comparison
            comparison_data = await tester.compare_versions(
                versions=scenario["versions"],
                essay_text=essay_text,
                level=scenario["level"]
            )
            
            # Store results
            results[scenario["name"]] = comparison_data
            
            # Print summary
            tester.print_comparison_table(comparison_data)
            
        except Exception as e:
            print(f"Error in scenario {scenario['name']}: {e}")
            results[scenario["name"]] = {"error": str(e)}
    
    # Save comprehensive results
    output_file = "batch_version_comparison_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*80}")
    print(f"BATCH TESTING COMPLETE")
    print(f"Comprehensive results saved to: {output_file}")
    print(f"{'='*80}")
    
    # Generate summary report
    generate_summary_report(results)


def generate_summary_report(results):
    """Generate a summary report across all scenarios"""
    print(f"\n{'='*80}")
    print("CROSS-SCENARIO SUMMARY")
    print(f"{'='*80}")
    
    version_performance = {}
    
    for scenario_name, scenario_data in results.items():
        if "error" in scenario_data:
            continue
            
        scores = scenario_data.get("comparison_summary", {}).get("score_comparison", {})
        times = scenario_data.get("comparison_summary", {}).get("time_comparison", {})
        
        for version, score_data in scores.items():
            if version not in version_performance:
                version_performance[version] = {
                    "total_scores": [],
                    "avg_times": [],
                    "scenarios": []
                }
            
            version_performance[version]["total_scores"].append(score_data["total"])
            version_performance[version]["avg_times"].append(times.get(version, 0))
            version_performance[version]["scenarios"].append(scenario_name)
    
    # Print version performance summary
    print(f"\n{'Version':<12} {'Avg Score':<10} {'Avg Time':<10} {'Scenarios Tested':<15}")
    print("-" * 60)
    
    for version, perf in version_performance.items():
        avg_score = sum(perf["total_scores"]) / len(perf["total_scores"]) if perf["total_scores"] else 0
        avg_time = sum(perf["avg_times"]) / len(perf["avg_times"]) if perf["avg_times"] else 0
        scenario_count = len(perf["scenarios"])
        
        print(f"{version:<12} {avg_score:<10.2f} {avg_time:<10.2f} {scenario_count:<15}")
    
    # Best performing version
    if version_performance:
        best_version = max(version_performance.keys(), 
                          key=lambda v: sum(version_performance[v]["total_scores"]) / len(version_performance[v]["total_scores"]))
        print(f"\nBest performing version overall: {best_version}")


if __name__ == "__main__":
    asyncio.run(run_batch_tests())