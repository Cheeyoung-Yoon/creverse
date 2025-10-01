#!/usr/bin/env python3
"""
Excel Data Explorer

Quick script to examine the structure of the essay_writing_40_sample.xlsx file
"""

import pandas as pd
import sys
from pathlib import Path

def explore_excel_data():
    """Examine the Excel file structure"""
    
    excel_path = Path(__file__).parent / "data" / "essay_writing_40_sample.xlsx"
    
    if not excel_path.exists():
        print(f"Error: Excel file not found at {excel_path}")
        return
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        print(f"Excel file loaded successfully!")
        print(f"Shape: {df.shape} (rows, columns)")
        print(f"\nColumn names:")
        for i, col in enumerate(df.columns):
            print(f"  {i+1}. {col}")
        
        print(f"\nFirst few rows:")
        print(df.head())
        
        print(f"\nData types:")
        print(df.dtypes)
        
        # Check for level/rubric columns
        level_columns = [col for col in df.columns if 'level' in col.lower() or 'rubric' in col.lower()]
        if level_columns:
            print(f"\nLevel/Rubric related columns:")
            for col in level_columns:
                print(f"  - {col}")
                if df[col].dtype == 'object':
                    unique_values = df[col].unique()
                    print(f"    Unique values: {unique_values}")
        
        # Check for essay text columns
        text_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['text', 'essay', 'content', 'writing', 'submission'])]
        if text_columns:
            print(f"\nText/Essay related columns:")
            for col in text_columns:
                print(f"  - {col}")
                if df[col].dtype == 'object':
                    # Show sample text length
                    sample_text = df[col].iloc[0] if not pd.isna(df[col].iloc[0]) else "N/A"
                    print(f"    Sample length: {len(str(sample_text)) if sample_text != 'N/A' else 'N/A'} characters")
        
        print(f"\nSample data preview:")
        print("="*50)
        for i in range(min(3, len(df))):
            print(f"Row {i+1}:")
            for col in df.columns:
                value = df.iloc[i][col]
                if pd.isna(value):
                    print(f"  {col}: N/A")
                elif isinstance(value, str) and len(value) > 100:
                    print(f"  {col}: {value[:100]}...")
                else:
                    print(f"  {col}: {value}")
            print("-" * 30)
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")

if __name__ == "__main__":
    explore_excel_data()