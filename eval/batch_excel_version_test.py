import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import pandas as pd

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from test_prompt_versions import PromptVersionTester


class ExcelBasedVersionTester:
    """Test prompt versions using data from Excel file"""
    
    def __init__(self, excel_path: str = None):
        self.excel_path = excel_path or "data/essay_writing_40_sample.xlsx"
        self.tester = PromptVersionTester()
        self.data = None
        
    def load_excel_data(self):
        """Load and validate Excel data"""
        excel_file = Path(__file__).parent / self.excel_path
        
        if not excel_file.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_file}")
        
        try:
            self.data = pd.read_excel(excel_file)
            print(f"Loaded Excel data: {self.data.shape[0]} essays with {self.data.shape[1]} columns")
            
            # Validate required columns
            required_columns = ['essay_id', 'rubric_level', 'topic_prompt', 'submit_text']
            missing_columns = [col for col in required_columns if col not in self.data.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Show available rubric levels
            levels = self.data['rubric_level'].dropna().unique()
            print(f"Available rubric levels: {list(levels)}")
            
            return True
            
        except Exception as e:
            print(f"Error loading Excel data: {e}")
            return False
    
    def select_samples_by_level(self):
        """Select one sample essay for each rubric level"""
        if self.data is None:
            raise ValueError("Excel data not loaded")
        
        samples = {}
        levels = self.data['rubric_level'].dropna().unique()
        
        for level in levels:
            # Filter essays for this level
            level_essays = self.data[self.data['rubric_level'] == level]
            
            if len(level_essays) == 0:
                continue
            
            # Special handling for Expert level - select a better quality essay
            if level.lower() == 'expert':
                # Try to find a longer, more sophisticated essay
                level_essays_sorted = level_essays.sort_values('submit_text', key=lambda x: x.str.len(), ascending=False)
                # Select the longest essay (likely more sophisticated)
                selected_essay = level_essays_sorted.iloc[0]
                print(f"Selected longer Expert essay ID {selected_essay['essay_id']} ({len(str(selected_essay['submit_text']))} chars)")
            else:
                # Select the first essay for other levels
                selected_essay = level_essays.iloc[0]
            
            # Map rubric levels to expected format
            level_mapping = {
                'basic': 'Basic',
                'intermediate': 'Intermediate', 
                'advanced': 'Advanced',
                'expert': 'Expert'
            }
            
            formatted_level = level_mapping.get(level.lower(), level.title())
            
            # Clean the essay text to remove problematic characters
            submit_text = str(selected_essay['submit_text'])
            topic_prompt = str(selected_essay['topic_prompt'])
            
            # Remove carriage returns and other problematic characters
            submit_text = submit_text.replace('_x000D_', '').replace('\r', '').strip()
            topic_prompt = topic_prompt.replace('_x000D_', '').replace('\r', '').strip()
            
            samples[formatted_level] = {
                'essay_id': int(selected_essay['essay_id']),  # Convert to Python int
                'original_level': level,
                'topic_prompt': topic_prompt,
                'submit_text': submit_text,
                'text_length': len(submit_text)
            }
            
            print(f"Selected essay ID {selected_essay['essay_id']} for {formatted_level} level")
        
        return samples
    
    async def run_comprehensive_version_test(self, versions_to_test=None):
        """Run comprehensive testing across all rubric levels and specified versions"""
        
        if not self.load_excel_data():
            return False
        
        # Select sample essays
        samples = self.select_samples_by_level()
        
        if not samples:
            print("No valid samples found")
            return False
        
        # Use specified versions or all available
        if versions_to_test is None:
            versions_to_test = self.tester.available_versions
        else:
            # Validate versions exist
            invalid_versions = [v for v in versions_to_test if v not in self.tester.available_versions]
            if invalid_versions:
                print(f"Warning: Invalid versions specified: {invalid_versions}")
                versions_to_test = [v for v in versions_to_test if v in self.tester.available_versions]
        
        print(f"Testing versions: {versions_to_test}")
        
        # Create timestamped output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / f"version_test_results_{timestamp}"
        output_dir.mkdir(exist_ok=True)
        
        # Store all results
        all_results = {
            "test_metadata": {
                "timestamp": timestamp,
                "versions_tested": versions_to_test,
                "total_essays": len(samples),
                "excel_source": self.excel_path
            },
            "results_by_level": {}
        }
        
        # Test each rubric level
        for level, sample_data in samples.items():
            print(f"\n{'='*80}")
            print(f"TESTING LEVEL: {level}")
            print(f"Essay ID: {sample_data['essay_id']}")
            print(f"Topic: {sample_data['topic_prompt'][:100]}...")
            print(f"Text length: {sample_data['text_length']} characters")
            print(f"{'='*80}")
            
            try:
                # Run version comparison for this level using one essay (count=1)
                comparison_data = await self.tester.compare_versions(
                    versions=versions_to_test,
                    level=level.capitalize(),  # Convert 'basic' to 'Basic' to match API format
                    count=1  # Only test one essay for each level
                )
                
                # Add sample metadata
                comparison_data["sample_metadata"] = sample_data
                
                # Store results
                all_results["results_by_level"][level] = comparison_data
                
                # Print summary table
                self.tester.print_comparison_table(comparison_data)
                
                # Save individual level results
                level_output_file = output_dir / f"{level.lower()}_level_results.json"
                with open(level_output_file, 'w', encoding='utf-8') as f:
                    json.dump(comparison_data, f, indent=2, ensure_ascii=False)
                
                print(f"Level {level} results saved to: {level_output_file}")
                
            except Exception as e:
                print(f"Error testing level {level}: {e}")
                all_results["results_by_level"][level] = {
                    "error": str(e),
                    "sample_metadata": sample_data
                }
        
        # Save comprehensive results with enhanced structure
        enhanced_results = self.create_enhanced_comprehensive_results(all_results)
        comprehensive_output = output_dir / "comprehensive_results.json"
        with open(comprehensive_output, 'w', encoding='utf-8') as f:
            json.dump(enhanced_results, f, indent=2, ensure_ascii=False)
        
        # Generate and save summary report
        summary_report = self.generate_comprehensive_summary(enhanced_results)
        summary_output = output_dir / "summary_report.txt"
        with open(summary_output, 'w', encoding='utf-8') as f:
            f.write(summary_report)
        
        print(f"\n{'='*80}")
        print("COMPREHENSIVE TESTING COMPLETE")
        print(f"Results saved to directory: {output_dir}")
        print(f"Comprehensive results: {comprehensive_output}")
        print(f"Summary report: {summary_output}")
        print(f"{'='*80}")
        
        # Print summary to console
        print(summary_report)
        
        return True
    
    def create_enhanced_comprehensive_results(self, all_results):
        """Create enhanced comprehensive results with unified structure"""
        enhanced = {
            "test_metadata": all_results["test_metadata"],
            "overall_summary": {
                "versions_comparison": {},
                "rubric_levels_tested": [],
                "performance_metrics": {}
            },
            "detailed_results_by_level": {},
            "version_performance_matrix": {},
            "timing_analysis": {},
            "score_breakdown": {}
        }
        
        # Process each level's results
        successful_levels = []
        version_scores = {}
        version_times = {}
        
        for level, level_data in all_results["results_by_level"].items():
            if "error" in level_data:
                enhanced["detailed_results_by_level"][level] = {
                    "status": "error",
                    "error_message": level_data["error"],
                    "sample_metadata": level_data.get("sample_metadata", {})
                }
                continue
            
            successful_levels.append(level)
            enhanced["detailed_results_by_level"][level] = {
                "status": "success",
                "comparison_data": level_data,
                "sample_metadata": level_data.get("sample_metadata", {})
            }
            
            # Extract performance data
            scores = level_data.get("comparison_summary", {}).get("score_comparison", {})
            times = level_data.get("comparison_summary", {}).get("time_comparison", {})
            
            for version in scores:
                if version not in version_scores:
                    version_scores[version] = {}
                    version_times[version] = {}
                
                version_scores[version][level] = scores[version]
                version_times[version][level] = times.get(version, 0)
        
        # Create overall summary
        enhanced["overall_summary"]["rubric_levels_tested"] = successful_levels
        
        # Version comparison matrix
        for version in version_scores:
            enhanced["version_performance_matrix"][version] = {
                "levels": {},
                "averages": {
                    "avg_total_score": 0,
                    "avg_time": 0,
                    "avg_introduction": 0,
                    "avg_body": 0,
                    "avg_conclusion": 0,
                    "avg_grammar": 0
                }
            }
            
            total_scores = []
            total_times = []
            intro_scores = []
            body_scores = []
            conclusion_scores = []
            grammar_scores = []
            
            for level in successful_levels:
                if level in version_scores[version]:
                    level_score_data = version_scores[version][level]
                    level_time = version_times[version][level]
                    
                    enhanced["version_performance_matrix"][version]["levels"][level] = {
                        "scores": level_score_data,
                        "time": level_time
                    }
                    
                    total_scores.append(level_score_data.get("total", 0))
                    total_times.append(level_time)
                    intro_scores.append(level_score_data.get("introduction", 0))
                    body_scores.append(level_score_data.get("body", 0))
                    conclusion_scores.append(level_score_data.get("conclusion", 0))
                    grammar_scores.append(level_score_data.get("grammar", 0))
            
            # Calculate averages
            if total_scores:
                enhanced["version_performance_matrix"][version]["averages"] = {
                    "avg_total_score": round(sum(total_scores) / len(total_scores), 2),
                    "avg_time": round(sum(total_times) / len(total_times), 2),
                    "avg_introduction": round(sum(intro_scores) / len(intro_scores), 2),
                    "avg_body": round(sum(body_scores) / len(body_scores), 2),
                    "avg_conclusion": round(sum(conclusion_scores) / len(conclusion_scores), 2),
                    "avg_grammar": round(sum(grammar_scores) / len(grammar_scores), 2)
                }
        
        # Timing analysis
        enhanced["timing_analysis"] = {
            "fastest_version": None,
            "slowest_version": None,
            "time_differences": {},
            "version_timing_breakdown": version_times
        }
        
        if version_times:
            avg_times_per_version = {}
            for version, times_dict in version_times.items():
                if times_dict:
                    avg_times_per_version[version] = sum(times_dict.values()) / len(times_dict)
            
            if avg_times_per_version:
                fastest = min(avg_times_per_version, key=avg_times_per_version.get)
                slowest = max(avg_times_per_version, key=avg_times_per_version.get)
                
                enhanced["timing_analysis"]["fastest_version"] = {
                    "version": fastest,
                    "avg_time": round(avg_times_per_version[fastest], 2)
                }
                enhanced["timing_analysis"]["slowest_version"] = {
                    "version": slowest, 
                    "avg_time": round(avg_times_per_version[slowest], 2)
                }
                
                enhanced["timing_analysis"]["time_differences"] = avg_times_per_version
        
        # Score breakdown
        enhanced["score_breakdown"] = {
            "by_section": {
                "introduction": {},
                "body": {},
                "conclusion": {},
                "grammar": {}
            },
            "by_level": {}
        }
        
        for section in ["introduction", "body", "conclusion", "grammar"]:
            for version in version_scores:
                section_scores = []
                for level in successful_levels:
                    if level in version_scores[version]:
                        section_scores.append(version_scores[version][level].get(section, 0))
                
                if section_scores:
                    enhanced["score_breakdown"]["by_section"][section][version] = {
                        "average": round(sum(section_scores) / len(section_scores), 2),
                        "scores_by_level": dict(zip(successful_levels, section_scores))
                    }
        
        return enhanced
    
    def generate_comprehensive_summary(self, all_results):
        """Generate a comprehensive summary report"""
        summary_lines = []
        summary_lines.append("="*80)
        summary_lines.append("COMPREHENSIVE VERSION TESTING SUMMARY")
        summary_lines.append("="*80)
        
        metadata = all_results["test_metadata"]
        summary_lines.append(f"Test Timestamp: {metadata['timestamp']}")
        summary_lines.append(f"Versions Tested: {', '.join(metadata['versions_tested'])}")
        summary_lines.append(f"Total Essays Tested: {metadata['total_essays']}")
        summary_lines.append(f"Data Source: {metadata['excel_source']}")
        summary_lines.append("")
        
        # Overall performance by version
        version_performance = {}
        
        for level, level_data in all_results["results_by_level"].items():
            if "error" in level_data:
                continue
                
            scores = level_data.get("comparison_summary", {}).get("score_comparison", {})
            times = level_data.get("comparison_summary", {}).get("time_comparison", {})
            
            for version, score_data in scores.items():
                if version not in version_performance:
                    version_performance[version] = {
                        "total_scores": [],
                        "avg_times": [],
                        "levels_tested": []
                    }
                
                version_performance[version]["total_scores"].append(score_data["total"])
                version_performance[version]["avg_times"].append(times.get(version, 0))
                version_performance[version]["levels_tested"].append(level)
        
        # Overall version comparison
        summary_lines.append("OVERALL VERSION PERFORMANCE")
        summary_lines.append("-" * 50)
        summary_lines.append(f"{'Version':<12} {'Avg Score':<10} {'Avg Time':<10} {'Levels':<20}")
        summary_lines.append("-" * 60)
        
        for version, perf in version_performance.items():
            avg_score = sum(perf["total_scores"]) / len(perf["total_scores"]) if perf["total_scores"] else 0
            avg_time = sum(perf["avg_times"]) / len(perf["avg_times"]) if perf["avg_times"] else 0
            levels_str = ",".join(perf["levels_tested"])
            
            summary_lines.append(f"{version:<12} {avg_score:<10.2f} {avg_time:<10.2f} {levels_str:<20}")
        
        # Level-by-level breakdown
        summary_lines.append("\nLEVEL-BY-LEVEL BREAKDOWN")
        summary_lines.append("-" * 50)
        
        for level, level_data in all_results["results_by_level"].items():
            summary_lines.append(f"\n{level.upper()} LEVEL:")
            
            if "error" in level_data:
                summary_lines.append(f"  ERROR: {level_data['error']}")
                continue
            
            sample_meta = level_data.get("sample_metadata", {})
            summary_lines.append(f"  Essay ID: {sample_meta.get('essay_id', 'N/A')}")
            summary_lines.append(f"  Text Length: {sample_meta.get('text_length', 'N/A')} characters")
            
            scores = level_data.get("comparison_summary", {}).get("score_comparison", {})
            times = level_data.get("comparison_summary", {}).get("time_comparison", {})
            
            summary_lines.append(f"  {'Version':<12} {'Total Score':<12} {'Time(s)':<10}")
            summary_lines.append(f"  {'-'*35}")
            
            for version, score_data in scores.items():
                time_data = times.get(version, 0)
                summary_lines.append(f"  {version:<12} {score_data['total']:<12} {time_data:<10.2f}")
        
        # Best performing version
        if version_performance:
            best_version = max(version_performance.keys(), 
                             key=lambda v: sum(version_performance[v]["total_scores"]) / len(version_performance[v]["total_scores"]))
            best_avg_score = sum(version_performance[best_version]["total_scores"]) / len(version_performance[best_version]["total_scores"])
            
            summary_lines.append(f"\nBEST PERFORMING VERSION: {best_version} (Avg Score: {best_avg_score:.2f})")
        
        summary_lines.append("\n" + "="*80)
        
        return "\n".join(summary_lines)


async def main():
    """Main function to run Excel-based version testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test prompt versions using Excel data")
    parser.add_argument("--excel-file", "-f", 
                       default="data/essay_writing_40_sample.xlsx",
                       help="Path to Excel file with essay data")
    parser.add_argument("--versions", "-v",
                       help="Comma-separated list of versions to test (default: all)")
    
    args = parser.parse_args()
    
    # Parse versions
    versions_to_test = None
    if args.versions:
        versions_to_test = [v.strip() for v in args.versions.split(",")]
    
    # Run testing
    tester = ExcelBasedVersionTester(excel_path=args.excel_file)
    
    try:
        success = await tester.run_comprehensive_version_test(versions_to_test)
        return 0 if success else 1
        
    except Exception as e:
        print(f"Error running comprehensive test: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))