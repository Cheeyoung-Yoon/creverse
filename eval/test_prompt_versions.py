#!/usr/bin/env python3
"""
Prompt Version Testing Script

This script tests different prompt versions by making API calls to evaluate essays
from the Excel data file.

Usage:
    python test_prompt_versions.py --versions v1.0.0,v1.1.0,v1.2.0 --level Basic --count 5
    python test_prompt_versions.py --all-versions --level Advanced --count 10
    python test_prompt_versions.py --compare v1.0.0 v1.2.0 --output comparison.json --count 3
"""

import asyncio
import json
import os
import sys
import time
import pandas as pd
import requests
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


class PromptVersionTester:
    """Test and compare different prompt versions using API calls"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.available_versions = self._get_available_versions()
        self.data_file = Path(__file__).parent / "data" / "essay_writing_40_sample.xlsx"
        print(f"Available prompt versions: {', '.join(self.available_versions)}")
    
    def _get_available_versions(self) -> List[str]:
        """Get list of available prompt versions"""
        prompts_dir = Path(__file__).parent / "prompts"
        versions = []
        for item in prompts_dir.iterdir():
            if item.is_dir() and item.name.startswith("v") and item.name != "dummy":
                versions.append(item.name)
        return sorted(versions)
    
    def load_essays_from_excel(self, level: str, count: Optional[int] = None) -> List[Dict[str, str]]:
        """Load essays from Excel file for the specified level"""
        try:
            # Read Excel file
            df = pd.read_excel(self.data_file)
            
            # Convert level to lowercase to match Excel data
            level_lower = level.lower()
            
            # Filter by level
            level_essays = df[df['rubric_level'] == level_lower].copy()
            
            if level_essays.empty:
                print(f"No essays found for level: {level} (searched for: {level_lower})")
                print(f"Available levels: {df['rubric_level'].unique()}")
                return []
            
            # Limit count if specified
            if count:
                level_essays = level_essays.head(count)
            
            # Convert to list of dictionaries
            essays = []
            for _, row in level_essays.iterrows():
                essays.append({
                    "rubric_level": row['rubric_level'].capitalize(),  # Convert to capitalize for API
                    "topic_prompt": row['topic_prompt'], 
                    "submit_text": row['submit_text']
                })
            
            print(f"Loaded {len(essays)} essays for level {level}")
            return essays
            
        except Exception as e:
            print(f"Error loading essays from Excel: {e}")
            return []
    
    async def call_api_for_version(self, essay_data: Dict[str, str], version: str) -> Dict[str, Any]:
        """Make API call to evaluate essay with specific version"""
        try:
            # Prepare API request
            payload = {
                "rubric_level": essay_data["rubric_level"],
                "topic_prompt": essay_data["topic_prompt"],
                "submit_text": essay_data["submit_text"],
                "prompt_version": version  # Include version in request
            }
            
            # Make API call
            start_time = time.time()
            response = requests.post(
                f"{self.api_base_url}/v1/essay-eval",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            evaluation_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                result["evaluation_time"] = round(evaluation_time, 3)
                result["version"] = version
                return result
            else:
                print(f"API call failed for {version}: {response.status_code} - {response.text}")
                return {
                    "version": version,
                    "error": f"API call failed: {response.status_code}",
                    "evaluation_time": round(evaluation_time, 3)
                }
                
        except Exception as e:
            print(f"Error calling API for version {version}: {e}")
            return {
                "version": version, 
                "error": str(e),
                "evaluation_time": 0
            }
    
    async def compare_versions(
        self, 
        versions: List[str], 
        level: str = "Basic",
        count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compare multiple versions using essays from Excel file"""
        
        print(f"\n{'='*70}")
        print(f"COMPARING VERSIONS: {', '.join(versions)}")
        print(f"Level: {level}")
        if count:
            print(f"Testing {count} essays per version")
        print(f"{'='*70}")
        
        # Load essays from Excel
        essays = self.load_essays_from_excel(level, count)
        if not essays:
            raise ValueError(f"No essays found for level {level}")
        
        # Test each version with each essay
        all_results = []
        
        for i, essay_data in enumerate(essays, 1):
            print(f"\n--- Testing Essay {i}/{len(essays)} ---")
            print(f"Topic: {essay_data['topic_prompt'][:100]}...")
            print(f"Text preview: {essay_data['submit_text'][:100]}...")
            
            essay_results = {}
            
            for version in versions:
                print(f"\nTesting version {version}...")
                result = await self.call_api_for_version(essay_data, version)
                essay_results[version] = result
                
                # Print basic result
                if "error" in result:
                    print(f"  {version}: ERROR - {result['error']}")
                else:
                    # Extract scores from API response
                    total_score = 0
                    if "structure" in result:
                        structure = result["structure"]
                        intro_score = structure.get("introduction", {}).get("score", 0)
                        body_score = structure.get("body", {}).get("score", 0) 
                        conclusion_score = structure.get("conclusion", {}).get("score", 0)
                        total_score += intro_score + body_score + conclusion_score
                    
                    if "grammar" in result:
                        grammar_score = result["grammar"].get("score", 0)
                        total_score += grammar_score
                    
                    eval_time = result.get("evaluation_time", 0)
                    print(f"  {version}: Total Score = {total_score}, Time = {eval_time:.2f}s")
            
            all_results.append({
                "essay_index": i,
                "essay_data": essay_data,
                "results": essay_results
            })
        
        # Compile comparison summary
        summary = self._compile_comparison_summary(all_results, versions)
        
        return {
            "comparison_summary": summary,
            "detailed_results": all_results,
            "metadata": {
                "versions_tested": versions,
                "level": level,
                "essay_count": len(essays),
                "test_timestamp": time.time()
            }
        }
    
    def _compile_comparison_summary(self, all_results: List[Dict], versions: List[str]) -> Dict[str, Any]:
        """Compile comparison summary from all results"""
        summary = {
            "score_comparison": {},
            "time_comparison": {},
            "feedback_differences": {},
            "average_scores": {}
        }
        
        for version in versions:
            # Initialize accumulators
            total_scores = []
            total_times = []
            intro_scores = []
            body_scores = []
            conclusion_scores = []
            grammar_scores = []
            feedbacks = {"introduction": [], "body": [], "conclusion": [], "grammar": []}
            
            # Collect data from all essays for this version
            for essay_result in all_results:
                result = essay_result["results"].get(version, {})
                
                if "error" not in result:
                    # Extract scores
                    structure = result.get("structure", {})
                    grammar = result.get("grammar", {})
                    
                    intro_score = structure.get("introduction", {}).get("score", 0)
                    body_score = structure.get("body", {}).get("score", 0)
                    conclusion_score = structure.get("conclusion", {}).get("score", 0)
                    grammar_score = grammar.get("score", 0)
                    
                    intro_scores.append(intro_score)
                    body_scores.append(body_score)
                    conclusion_scores.append(conclusion_score)
                    grammar_scores.append(grammar_score)
                    total_scores.append(intro_score + body_score + conclusion_score + grammar_score)
                    
                    # Extract times
                    eval_time = result.get("evaluation_time", 0)
                    total_times.append(eval_time)
                    
                    # Extract feedback samples
                    feedbacks["introduction"].append(structure.get("introduction", {}).get("feedback", ""))
                    feedbacks["body"].append(structure.get("body", {}).get("feedback", ""))
                    feedbacks["conclusion"].append(structure.get("conclusion", {}).get("feedback", ""))
                    feedbacks["grammar"].append(grammar.get("feedback", ""))
            
            # Calculate averages
            if total_scores:  # If we have valid results
                summary["score_comparison"][version] = {
                    "introduction": round(sum(intro_scores) / len(intro_scores), 2),
                    "body": round(sum(body_scores) / len(body_scores), 2),
                    "conclusion": round(sum(conclusion_scores) / len(conclusion_scores), 2),
                    "grammar": round(sum(grammar_scores) / len(grammar_scores), 2),
                    "total": round(sum(total_scores) / len(total_scores), 2)
                }
                
                summary["time_comparison"][version] = round(sum(total_times) / len(total_times), 2)
                summary["average_scores"][version] = round(sum(total_scores) / len(total_scores), 2)
                
                # Sample feedback (first non-empty feedback)
                summary["feedback_differences"][version] = {
                    "introduction": next((fb for fb in feedbacks["introduction"] if fb), ""),
                    "body": next((fb for fb in feedbacks["body"] if fb), ""),
                    "conclusion": next((fb for fb in feedbacks["conclusion"] if fb), ""),
                    "grammar": next((fb for fb in feedbacks["grammar"] if fb), "")
                }
            else:
                # No valid results for this version
                summary["score_comparison"][version] = {
                    "introduction": 0, "body": 0, "conclusion": 0, "grammar": 0, "total": 0
                }
                summary["time_comparison"][version] = 0
                summary["average_scores"][version] = 0
                summary["feedback_differences"][version] = {
                    "introduction": "No valid results", "body": "No valid results",
                    "conclusion": "No valid results", "grammar": "No valid results"
                }
        
        return summary
    
    def print_comparison_table(self, comparison_data: Dict[str, Any]):
        """Print a formatted comparison table"""
        summary = comparison_data["comparison_summary"]
        metadata = comparison_data["metadata"]
        scores = summary["score_comparison"]
        times = summary["time_comparison"]
        
        print(f"\n{'='*80}")
        print("COMPARISON SUMMARY")
        print(f"{'='*80}")
        print(f"Level: {metadata['level']}, Essays tested: {metadata['essay_count']}")
        
        # Score comparison table
        print(f"\n{'Version':<12} {'Intro':<6} {'Body':<6} {'Concl':<6} {'Grammar':<8} {'Total':<6} {'Time(s)':<8}")
        print("-" * 65)
        
        for version in scores:
            score_data = scores[version]
            time_data = times.get(version, 0)
            print(f"{version:<12} {score_data['introduction']:<6} {score_data['body']:<6} "
                  f"{score_data['conclusion']:<6} {score_data['grammar']:<8} "
                  f"{score_data['total']:<6} {time_data:<8.2f}")
        
        # Feedback differences
        print(f"\n{'='*50}")
        print("SAMPLE FEEDBACK COMPARISON")
        print(f"{'='*50}")
        
        feedback = summary["feedback_differences"]
        sections = ["introduction", "body", "conclusion", "grammar"]
        
        for section in sections:
            print(f"\n{section.upper()}:")
            print("-" * 30)
            for version in feedback:
                fb = feedback[version][section]
                print(f"{version}: {fb[:100]}{'...' if len(fb) > 100 else ''}")


async def main():
    parser = ArgumentParser(description="Test and compare different prompt versions using API calls")
    parser.add_argument("--versions", "-v", 
                       help="Comma-separated list of versions to test (e.g., v1.0.0,v1.1.0)")
    parser.add_argument("--all-versions", "-a", action="store_true",
                       help="Test all available versions")
    parser.add_argument("--level", "-l", default="Basic",
                       choices=["Basic", "Intermediate", "Advanced", "Expert"],
                       help="Evaluation level")
    parser.add_argument("--count", "-c", type=int,
                       help="Number of essays to test per version (default: all essays for the level)")
    parser.add_argument("--output", "-o",
                       help="Output file for detailed results (JSON format)")
    parser.add_argument("--compare", nargs=2, metavar=("V1", "V2"),
                       help="Compare two specific versions")
    parser.add_argument("--api-url", default="http://localhost:8000",
                       help="Base URL for the API (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    tester = PromptVersionTester(api_base_url=args.api_url)
    
    # Determine versions to test
    if args.compare:
        versions = args.compare
    elif args.all_versions:
        versions = tester.available_versions
    elif args.versions:
        versions = [v.strip() for v in args.versions.split(",")]
    else:
        print("Please specify versions to test using --versions, --all-versions, or --compare")
        return 1
    
    # Validate versions
    invalid_versions = [v for v in versions if v not in tester.available_versions]
    if invalid_versions:
        print(f"Error: Invalid versions: {', '.join(invalid_versions)}")
        print(f"Available versions: {', '.join(tester.available_versions)}")
        return 1
    
    # Run comparison
    try:
        comparison_data = await tester.compare_versions(versions, args.level, args.count)
        
        # Print results
        tester.print_comparison_table(comparison_data)
        
        # Save detailed results if requested
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(comparison_data, f, indent=2, ensure_ascii=False)
            print(f"\nDetailed results saved to: {args.output}")
        
        return 0
        
    except Exception as e:
        print(f"Error running comparison: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))