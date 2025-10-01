# Prompt Version Testing Configuration

## Overview
This directory contains tools for testing and comparing different prompt versions to understand how changes affect evaluation outcomes.

## Main Script: test_prompt_versions.py

### Basic Usage Examples

1. **Compare two specific versions:**
   ```bash
   python test_prompt_versions.py --compare v1.0.0 v1.2.0 --level Basic
   ```

2. **Test multiple versions:**
   ```bash
   python test_prompt_versions.py --versions v1.0.0,v1.1.0,v1.2.0 --level Intermediate
   ```

3. **Test all available versions:**
   ```bash
   python test_prompt_versions.py --all-versions --level Advanced
   ```

4. **Use custom essay:**
   ```bash
   python test_prompt_versions.py --all-versions --essay-file my_essay.txt --level Expert
   ```

5. **Save detailed results:**
   ```bash
   python test_prompt_versions.py --compare v1.0.0 v1.3.0 --output comparison_results.json
   ```

### Command Line Options

- `--versions, -v`: Comma-separated list of versions to test
- `--all-versions, -a`: Test all available versions
- `--level, -l`: Evaluation level (Basic, Intermediate, Advanced, Expert)
- `--essay-file, -f`: Path to custom essay file
- `--output, -o`: Save detailed results to JSON file
- `--compare`: Compare exactly two versions

### Output Features

The script provides:
- **Execution time tracking** for each LLM call (introduction, body, conclusion, grammar)
- **Token usage logging** for cost tracking
- **Score comparison table** showing scores across all sections
- **Feedback comparison** showing how different versions provide different feedback
- **Detailed JSON export** for further analysis

### What Gets Compared

For each version, the script evaluates:
- **Structure evaluation**: Introduction, Body, Conclusion scores and feedback
- **Grammar evaluation**: Grammar score and feedback
- **Performance metrics**: Total evaluation time
- **Token usage**: For cost analysis

## Sample Essays

The script includes a built-in sample essay about climate change. You can also create custom essays in the `sample_essays/` directory.

## Understanding Results

### Score Comparison Table
```
Version      Intro  Body   Concl  Grammar  Total  Time(s)
v1.0.0       2      1      2      1        6      15.23
v1.2.0       2      2      2      2        8      16.45
```

### Feedback Comparison
Shows how different prompt versions provide different feedback for the same content, helping you understand the impact of prompt changes.

## Best Practices

1. **Test with multiple essay types**: Use essays of different quality levels and topics
2. **Test across proficiency levels**: Run comparisons at Basic, Intermediate, Advanced, and Expert levels
3. **Document changes**: Keep notes about what changed between versions
4. **Regular testing**: Test major prompt changes against a standardized set of essays
5. **Cost monitoring**: Use token usage logs to track evaluation costs

## Integration with Development

Use this tool during prompt development to:
- Validate that prompt changes improve evaluation quality
- Ensure consistency across different essay types
- Monitor performance and cost implications
- Document the impact of prompt iterations