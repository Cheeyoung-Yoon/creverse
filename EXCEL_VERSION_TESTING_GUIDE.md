# Excel-Based Version Testing Guide

## Overview
The Excel-based version testing script reads essay data from `data/essay_writing_40_sample.xlsx` and runs comprehensive prompt version comparisons.

## What the Script Does

### Data Selection
- Loads essays from the Excel file (41 total essays)
- Selects **one representative essay** from each rubric level:
  - **Basic Level**: Essay ID 0 (247 characters) - Tsunami evacuation topic
  - **Intermediate Level**: Essay ID 10 (537 characters) - Mars planet visit topic  
  - **Advanced Level**: Essay ID 20 (1,793 characters) - Korean reunification topic
  - **Expert Level**: Essay ID 30 (1,405 characters) - Teenage cosmetic surgery topic

### Version Testing
- Tests all available prompt versions: `v1.0.0`, `v1.1.0`, `v1.2.0`, `v1.3.0`
- Each essay gets evaluated by each version = **16 total evaluations**
- Each evaluation includes:
  - **Structure evaluation**: Introduction, Body, Conclusion scores and feedback
  - **Grammar evaluation**: Grammar score and feedback
  - **Performance tracking**: Execution time for each LLM call
  - **Cost tracking**: Token usage logging for price monitoring

## Usage Commands

### 1. Dry Run (See what would be tested)
```bash
python dry_run_excel_test.py
```

### 2. Test All Versions (Comprehensive)
```bash
python batch_excel_version_test.py
```

### 3. Test Specific Versions Only
```bash
python batch_excel_version_test.py --versions v1.0.0,v1.2.0
```

### 4. Use Different Excel File
```bash
python batch_excel_version_test.py --excel-file path/to/other/file.xlsx
```

## Expected Output

### Console Logs
During execution, you'll see:
```
LLM execution time for introduction: 7.504 seconds
Token usage for introduction - Prompt: 150, Completion: 75, Total: 225

LLM execution time for body: 6.679 seconds  
Token usage for body - Prompt: 180, Completion: 85, Total: 265

LLM execution time for conclusion: 7.504 seconds
Token usage for conclusion - Prompt: 160, Completion: 70, Total: 230

LLM execution time for grammar: 5.234 seconds
Token usage for grammar - Prompt: 200, Completion: 90, Total: 290
```

### Generated Files
The script creates a timestamped directory with:
```
version_test_results_20251001_143022/
├── basic_level_results.json          # Detailed results for Basic level
├── intermediate_level_results.json   # Detailed results for Intermediate level  
├── advanced_level_results.json       # Detailed results for Advanced level
├── expert_level_results.json         # Detailed results for Expert level
├── comprehensive_results.json        # Complete results across all levels
└── summary_report.txt                # Human-readable summary
```

### Summary Report Contents
```
COMPREHENSIVE VERSION TESTING SUMMARY
================================================================================
Test Timestamp: 20251001_143022
Versions Tested: v1.0.0, v1.1.0, v1.2.0, v1.3.0
Total Essays Tested: 4
Data Source: data/essay_writing_40_sample.xlsx

OVERALL VERSION PERFORMANCE
--------------------------------------------------
Version      Avg Score  Avg Time   Levels              
------------------------------------------------------------
v1.0.0       6.25       15.23      Basic,Intermediate,Advanced,Expert
v1.2.0       7.50       16.45      Basic,Intermediate,Advanced,Expert
v1.3.0       7.75       14.89      Basic,Intermediate,Advanced,Expert

LEVEL-BY-LEVEL BREAKDOWN
--------------------------------------------------

BASIC LEVEL:
  Essay ID: 0
  Text Length: 247 characters
  Version      Total Score  Time(s)   
  -----------------------------------
  v1.0.0       6            15.23
  v1.2.0       8            16.45
  v1.3.0       8            14.89

[... similar for other levels ...]

BEST PERFORMING VERSION: v1.3.0 (Avg Score: 7.75)
```

## Prerequisites
- Azure OpenAI credentials configured in `.env` file
- Micromamba environment `creverse` activated
- Required packages: `pandas`, `openpyxl`

## Estimated Runtime
- **Per essay evaluation**: ~15-20 seconds
- **Total runtime**: ~4-5 minutes for all 16 evaluations
- **Token usage**: ~1,000-2,000 tokens per evaluation

## Use Cases
1. **Validate prompt improvements** - Compare new versions against previous ones
2. **Performance benchmarking** - Track evaluation speed and consistency
3. **Cost analysis** - Monitor token usage across different prompt versions
4. **Quality assessment** - Ensure prompt changes improve evaluation accuracy