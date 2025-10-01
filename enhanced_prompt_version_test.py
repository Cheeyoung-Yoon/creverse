#!/usr/bin/env python3
"""
Enhanced Prompt Version Testing Script

This script tests different prompt versions with enhanced data collection and analysis.
Features:
- Tests one essay per rubric level
- Collects detailed timing, token usage, and scoring data
- Saves comprehensive results to JSON
- Generates detailed comparison tables

Usage:
    python enhanced_prompt_version_test.py --versions v1.0.0,v1.1.0 --output results.json
    python enhanced_prompt_version_test.py --all-versions --output comprehensive_test.json
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
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


class EnhancedPromptVersionTester:
    """Enhanced test and comparison of different prompt versions with detailed metrics"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.available_versions = self._get_available_versions()
        self.data_file = Path(__file__).parent / "data" / "essay_writing_40_sample.xlsx"
        self.results_dir = Path(__file__).parent / "test_results"
        self.results_dir.mkdir(exist_ok=True)
        print(f"Available prompt versions: {', '.join(self.available_versions)}")
    
    def _get_available_versions(self) -> List[str]:
        """Get list of available prompt versions"""
        prompts_dir = Path(__file__).parent / "prompts"
        versions = []
        for item in prompts_dir.iterdir():
            if item.is_dir() and item.name.startswith("v") and item.name != "dummy":
                versions.append(item.name)
        return sorted(versions)
    
    def load_essays_by_rubric_level(self) -> Dict[str, Dict[str, str]]:
        """Load one essay per rubric level from Excel file"""
        try:
            # Read Excel file
            df = pd.read_excel(self.data_file)
            
            # Remove NaN rubric levels
            df = df.dropna(subset=['rubric_level'])
            
            # Get unique rubric levels
            rubric_levels = df['rubric_level'].unique()
            
            essays_by_level = {}
            
            for level in rubric_levels:
                # Get first essay for each rubric level
                level_data = df[df['rubric_level'] == level].iloc[0]
                
                essays_by_level[level] = {
                    "essay_id": str(level_data['essay_id']),
                    "rubric_level": level.capitalize(),  # Convert to capitalize for API
                    "topic_prompt": level_data['topic_prompt'],
                    "submit_text": level_data['submit_text']
                }
            
            print(f"Loaded essays for rubric levels: {', '.join(rubric_levels)}")
            return essays_by_level
            
        except Exception as e:
            print(f"Error loading essays from Excel: {e}")
            return {}
    
    def parse_api_response_for_metrics(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse API response to extract detailed metrics"""
        metrics = {
            "timing": {},
            "tokens": {},
            "scores": {},
            "feedback": {},
            "api_timings": {}
        }
        
        # Extract API-level timing information
        if "timings" in response_data:
            api_timings = response_data["timings"]
            metrics["api_timings"] = {
                "pre_process": api_timings.get("pre_process", 0),
                "grammar": api_timings.get("grammar", 0),
                "structure": api_timings.get("structure", 0),
                "aggregate": api_timings.get("aggregate", 0),
                "post_process": api_timings.get("post_process", 0),
                "total": api_timings.get("total", 0)
            }
            
            # Convert milliseconds to seconds for display
            for key in metrics["api_timings"]:
                if metrics["api_timings"][key] > 0:
                    metrics["api_timings"][key] = round(metrics["api_timings"][key] / 1000, 3)
        
        # Extract structure-related metrics
        if "structure" in response_data:
            structure = response_data["structure"]
            
            for section in ["introduction", "body", "conclusion"]:
                if section in structure:
                    section_data = structure[section]
                    
                    # Extract scores
                    metrics["scores"][section] = section_data.get("score", 0)
                    
                    # Extract feedback
                    metrics["feedback"][section] = section_data.get("feedback", "")
                    
                    # Note: Individual section timing not available in API response
                    # Use proportional estimation based on total structure time
                    if "timings" in response_data and "structure" in response_data["timings"]:
                        structure_time = response_data["timings"]["structure"] / 1000  # Convert to seconds
                        # Rough estimation: divide structure time by 3 sections
                        metrics["timing"][section] = round(structure_time / 3, 3)
                    
                    # Token usage - typically null in current API
                    token_usage = section_data.get("token_usage")
                    metrics["tokens"][section] = token_usage if token_usage else {"prompt": 0, "completion": 0, "total": 0}
        
        # Extract grammar metrics
        if "grammar" in response_data:
            grammar = response_data["grammar"]
                
            metrics["scores"]["grammar"] = grammar.get("score", 0)
            metrics["feedback"]["grammar"] = grammar.get("feedback", "")
            
            # Grammar timing from API timings
            if "timings" in response_data and "grammar" in response_data["timings"]:
                metrics["timing"]["grammar"] = round(response_data["timings"]["grammar"] / 1000, 3)
            
            # Token usage for grammar
            token_usage = grammar.get("token_usage")
            metrics["tokens"]["grammar"] = token_usage if token_usage else {"prompt": 0, "completion": 0, "total": 0}
        
        # Calculate totals
        metrics["total_score"] = sum(metrics["scores"].values())
        
        # Use actual API total time if available
        if "timings" in response_data and "total" in response_data["timings"]:
            metrics["total_time"] = round(response_data["timings"]["total"] / 1000, 3)
        else:
            metrics["total_time"] = sum(metrics["timing"].values()) if metrics["timing"] else 0
        
        # Calculate total tokens (currently will be 0 as API doesn't provide this)
        total_tokens = {"prompt": 0, "completion": 0, "total": 0}
        for section_tokens in metrics["tokens"].values():
            if isinstance(section_tokens, dict):
                total_tokens["prompt"] += section_tokens.get("prompt", 0)
                total_tokens["completion"] += section_tokens.get("completion", 0)
                total_tokens["total"] += section_tokens.get("total", 0)
        metrics["total_tokens"] = total_tokens
        
        return metrics
    
    async def call_api_for_version_enhanced(self, essay_data: Dict[str, str], version: str) -> Dict[str, Any]:
        """Make enhanced API call to evaluate essay with detailed metrics collection"""
        try:
            # Prepare API request
            payload = {
                "rubric_level": essay_data["rubric_level"],
                "topic_prompt": essay_data["topic_prompt"],
                "submit_text": essay_data["submit_text"],
                "prompt_version": version  # Include version in request
            }
            
            # Make API call with timing
            start_time = time.time()
            response = requests.post(
                f"{self.api_base_url}/v1/essay-eval",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120  # Increased timeout for detailed analysis
            )
            total_evaluation_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                # Parse detailed metrics
                metrics = self.parse_api_response_for_metrics(result)
                
                return {
                    "version": version,
                    "essay_id": essay_data["essay_id"],
                    "rubric_level": essay_data["rubric_level"],
                    "success": True,
                    "total_evaluation_time": round(total_evaluation_time, 3),
                    "api_response": result,
                    "metrics": metrics,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                print(f"API call failed for {version}: {response.status_code} - {response.text}")
                return {
                    "version": version,
                    "essay_id": essay_data["essay_id"],
                    "rubric_level": essay_data["rubric_level"],
                    "success": False,
                    "error": f"API call failed: {response.status_code}",
                    "error_details": response.text,
                    "total_evaluation_time": round(total_evaluation_time, 3),
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"Error calling API for version {version}: {e}")
            return {
                "version": version,
                "essay_id": essay_data.get("essay_id", "unknown"),
                "rubric_level": essay_data.get("rubric_level", "unknown"),
                "success": False,
                "error": str(e),
                "total_evaluation_time": 0,
                "timestamp": datetime.now().isoformat()
            }
    
    async def compare_versions_enhanced(self, versions: List[str]) -> Dict[str, Any]:
        """Enhanced comparison of multiple versions with detailed metrics"""
        
        print(f"\n{'='*80}")
        print(f"ENHANCED PROMPT VERSION COMPARISON")
        print(f"Versions: {', '.join(versions)}")
        print(f"Testing one essay per rubric level")
        print(f"{'='*80}")
        
        # Load essays by rubric level
        essays_by_level = self.load_essays_by_rubric_level()
        if not essays_by_level:
            raise ValueError("No essays found")
        
        # Test each version with each rubric level
        all_results = []
        
        for level, essay_data in essays_by_level.items():
            print(f"\n--- Testing Rubric Level: {level} (Essay ID: {essay_data['essay_id']}) ---")
            print(f"Topic: {essay_data['topic_prompt'][:100]}...")
            print(f"Text preview: {essay_data['submit_text'][:100]}...")
            
            level_results = {}
            
            for version in versions:
                print(f"\nTesting version {version}...")
                result = await self.call_api_for_version_enhanced(essay_data, version)
                level_results[version] = result
                
                # Print basic result
                if not result["success"]:
                    print(f"  {version}: ERROR - {result['error']}")
                else:
                    metrics = result["metrics"]
                    print(f"  {version}: Total Score = {metrics['total_score']}, "
                          f"Time = {metrics['total_time']:.2f}s")
                    
                    # Print API-level timing breakdown if available
                    if metrics["api_timings"]:
                        print(f"    API Timing breakdown:")
                        print(f"      Grammar: {metrics['api_timings']['grammar']:.2f}s, "
                              f"Structure: {metrics['api_timings']['structure']:.2f}s, "
                              f"Total: {metrics['api_timings']['total']:.2f}s")
                    
                    # Print section scores
                    section_scores = []
                    for section in ["introduction", "body", "conclusion", "grammar"]:
                        score = metrics["scores"].get(section, 0)
                        section_scores.append(f"{section[:4]}: {score}")
                    print(f"    Section scores: {', '.join(section_scores)}")
            
            all_results.append({
                "rubric_level": level,
                "essay_data": essay_data,
                "results": level_results
            })
        
        # Compile enhanced comparison summary
        summary = self._compile_enhanced_summary(all_results, versions)
        
        return {
            "comparison_summary": summary,
            "detailed_results": all_results,
            "metadata": {
                "versions_tested": versions,
                "rubric_levels_tested": list(essays_by_level.keys()),
                "test_timestamp": datetime.now().isoformat(),
                "api_base_url": self.api_base_url
            }
        }
    
    def _compile_enhanced_summary(self, all_results: List[Dict], versions: List[str]) -> Dict[str, Any]:
        """Compile enhanced comparison summary with detailed metrics"""
        summary = {
            "version_comparison": {},
            "rubric_level_breakdown": {},
            "performance_metrics": {}
        }
        
        # Initialize version comparison
        for version in versions:
            summary["version_comparison"][version] = {
                "scores": {"introduction": [], "body": [], "conclusion": [], "grammar": [], "total": []},
                "timing": {"introduction": [], "body": [], "conclusion": [], "grammar": [], "total": []},
                "tokens": {"introduction": [], "body": [], "conclusion": [], "grammar": [], "total": []},
                "api_timings": {"pre_process": [], "grammar": [], "structure": [], "aggregate": [], "post_process": [], "total": []},
                "success_rate": 0,
                "total_essays": 0
            }
        
        # Initialize rubric level breakdown
        for result in all_results:
            level = result["rubric_level"]
            summary["rubric_level_breakdown"][level] = {}
        
        # Collect data from all results
        for result in all_results:
            level = result["rubric_level"]
            level_summary = {}
            
            for version in versions:
                version_result = result["results"].get(version, {})
                version_data = summary["version_comparison"][version]
                version_data["total_essays"] += 1
                
                if version_result.get("success", False):
                    version_data["success_rate"] += 1
                    metrics = version_result["metrics"]
                    
                    # Collect scores
                    for section in ["introduction", "body", "conclusion", "grammar"]:
                        score = metrics["scores"].get(section, 0)
                        version_data["scores"][section].append(score)
                        
                        # Collect timing
                        timing = metrics["timing"].get(section, 0)
                        version_data["timing"][section].append(timing)
                        
                        # Collect tokens
                        tokens = metrics["tokens"].get(section, {})
                        if isinstance(tokens, dict):
                            total_tokens = tokens.get("total", 0)
                            version_data["tokens"][section].append(total_tokens)
                    
                    # Total metrics
                    version_data["scores"]["total"].append(metrics["total_score"])
                    version_data["timing"]["total"].append(metrics["total_time"])
                    version_data["tokens"]["total"].append(metrics["total_tokens"]["total"])
                    
                    # Collect API timing data
                    api_timings = metrics.get("api_timings", {})
                    for timing_key in ["pre_process", "grammar", "structure", "aggregate", "post_process", "total"]:
                        timing_value = api_timings.get(timing_key, 0)
                        version_data["api_timings"][timing_key].append(timing_value)
                    
                    # Store level-specific data
                    level_summary[version] = {
                        "score": metrics["total_score"],
                        "time": metrics["total_time"],
                        "tokens": metrics["total_tokens"]["total"],
                        "api_timings": api_timings,
                        "success": True
                    }
                else:
                    level_summary[version] = {
                        "score": 0,
                        "time": 0,
                        "tokens": 0,
                        "success": False,
                        "error": version_result.get("error", "Unknown error")
                    }
            
            summary["rubric_level_breakdown"][level] = level_summary
        
        # Calculate averages and performance metrics
        for version in versions:
            version_data = summary["version_comparison"][version]
            
            # Calculate success rate
            if version_data["total_essays"] > 0:
                version_data["success_rate"] = version_data["success_rate"] / version_data["total_essays"]
            
            # Calculate averages for each metric
            for metric_type in ["scores", "timing", "tokens", "api_timings"]:
                sections = ["introduction", "body", "conclusion", "grammar", "total"] if metric_type != "api_timings" else ["pre_process", "grammar", "structure", "aggregate", "post_process", "total"]
                
                for section in sections:
                    values = version_data[metric_type][section]
                    if values:
                        version_data[metric_type][section] = {
                            "average": round(sum(values) / len(values), 3),
                            "min": min(values),
                            "max": max(values),
                            "count": len(values)
                        }
                    else:
                        version_data[metric_type][section] = {
                            "average": 0,
                            "min": 0,
                            "max": 0,
                            "count": 0
                        }
        
        return summary
    
    def print_enhanced_comparison_table(self, comparison_data: Dict[str, Any]):
        """Print enhanced formatted comparison tables"""
        summary = comparison_data["comparison_summary"]
        metadata = comparison_data["metadata"]
        version_comparison = summary["version_comparison"]
        rubric_breakdown = summary["rubric_level_breakdown"]
        
        print(f"\n{'='*100}")
        print("ENHANCED PROMPT VERSION COMPARISON SUMMARY")
        print(f"{'='*100}")
        print(f"Test Date: {metadata['test_timestamp']}")
        print(f"Rubric Levels: {', '.join(metadata['rubric_levels_tested'])}")
        print(f"Versions: {', '.join(metadata['versions_tested'])}")
        
        # Overall Performance Summary Table
        print(f"\n{'='*80}")
        print("OVERALL PERFORMANCE SUMMARY")
        print(f"{'='*80}")
        
        header = f"{'Version':<12} {'Success%':<8} {'Avg Score':<10} {'Grammar(s)':<10} {'Structure(s)':<12} {'Total(s)':<10}"
        print(header)
        print("-" * len(header))
        
        for version in version_comparison:
            data = version_comparison[version]
            success_rate = data["success_rate"] * 100
            avg_score = data["scores"]["total"]["average"]
            
            # Get API timing averages if available
            api_timing_data = data.get("api_timings", {})
            grammar_time = api_timing_data.get("grammar", {}).get("average", 0)
            structure_time = api_timing_data.get("structure", {}).get("average", 0)
            total_time = api_timing_data.get("total", {}).get("average", 0)
            
            print(f"{version:<12} {success_rate:<8.1f} {avg_score:<10.2f} {grammar_time:<10.2f} {structure_time:<12.2f} {total_time:<10.2f}")
        
        # Detailed Section Performance Table
        print(f"\n{'='*120}")
        print("SECTION-WISE PERFORMANCE COMPARISON")
        print(f"{'='*120}")
        
        sections = ["introduction", "body", "conclusion", "grammar"]
        
        for metric_name, metric_key in [("SCORES", "scores"), ("TIMING (seconds)", "timing"), ("TOKENS", "tokens")]:
            print(f"\n{metric_name}:")
            header = f"{'Version':<12} {'Intro':<10} {'Body':<10} {'Conclusion':<12} {'Grammar':<10} {'Total':<10}"
            print(header)
            print("-" * len(header))
            
            for version in version_comparison:
                data = version_comparison[version][metric_key]
                intro = data["introduction"]["average"]
                body = data["body"]["average"]
                conclusion = data["conclusion"]["average"]
                grammar = data["grammar"]["average"]
                total = data["total"]["average"]
                
                if metric_key == "timing":
                    print(f"{version:<12} {intro:<10.2f} {body:<10.2f} {conclusion:<12.2f} {grammar:<10.2f} {total:<10.2f}")
                else:
                    print(f"{version:<12} {intro:<10.1f} {body:<10.1f} {conclusion:<12.1f} {grammar:<10.1f} {total:<10.1f}")
        
        # Rubric Level Breakdown
        print(f"\n{'='*80}")
        print("RUBRIC LEVEL BREAKDOWN")
        print(f"{'='*80}")
        
        for level in rubric_breakdown:
            print(f"\n{level.upper()} Level:")
            header = f"{'Version':<12} {'Score':<8} {'Time(s)':<10} {'Tokens':<10} {'Status':<10}"
            print(header)
            print("-" * len(header))
            
            for version in metadata['versions_tested']:
                if version in rubric_breakdown[level]:
                    data = rubric_breakdown[level][version]
                    status = "Success" if data["success"] else "Failed"
                    print(f"{version:<12} {data['score']:<8.1f} {data['time']:<10.2f} {data['tokens']:<10.0f} {status:<10}")
    
    def save_results_to_json(self, comparison_data: Dict[str, Any], output_file: str):
        """Save comprehensive results to JSON file"""
        # Create timestamped filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"prompt_comparison_{timestamp}.json"
        
        output_path = self.results_dir / output_file
        
        # Add additional metadata
        comparison_data["metadata"]["test_configuration"] = {
            "data_source": str(self.data_file),
            "api_endpoint": f"{self.api_base_url}/v1/essay-eval",
            "test_type": "enhanced_prompt_version_comparison",
            "script_version": "1.0.0"
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(comparison_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"\nComprehensive results saved to: {output_path}")
            print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
            
            return str(output_path)
            
        except Exception as e:
            print(f"Error saving results to JSON: {e}")
            return None


async def main():
    parser = ArgumentParser(description="Enhanced test and comparison of prompt versions with detailed metrics")
    parser.add_argument("--versions", "-v", 
                       help="Comma-separated list of versions to test (e.g., v1.0.0,v1.1.0)")
    parser.add_argument("--all-versions", "-a", action="store_true",
                       help="Test all available versions")
    parser.add_argument("--output", "-o", 
                       help="Output file for detailed results (JSON format)")
    parser.add_argument("--api-url", default="http://localhost:8000",
                       help="Base URL for the API (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    tester = EnhancedPromptVersionTester(api_base_url=args.api_url)
    
    # Determine versions to test
    if args.all_versions:
        versions = tester.available_versions
    elif args.versions:
        versions = [v.strip() for v in args.versions.split(",")]
    else:
        print("Please specify versions to test using --versions or --all-versions")
        return 1
    
    # Validate versions
    invalid_versions = [v for v in versions if v not in tester.available_versions]
    if invalid_versions:
        print(f"Error: Invalid versions: {', '.join(invalid_versions)}")
        print(f"Available versions: {', '.join(tester.available_versions)}")
        return 1
    
    # Run enhanced comparison
    try:
        comparison_data = await tester.compare_versions_enhanced(versions)
        
        # Print enhanced results
        tester.print_enhanced_comparison_table(comparison_data)
        
        # Save detailed results
        output_file = args.output or f"enhanced_prompt_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        saved_path = tester.save_results_to_json(comparison_data, output_file)
        
        if saved_path:
            print(f"\n{'='*60}")
            print("TEST COMPLETED SUCCESSFULLY")
            print(f"Results saved to: {saved_path}")
            print(f"{'='*60}")
        
        return 0
        
    except Exception as e:
        print(f"Error running enhanced comparison: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))