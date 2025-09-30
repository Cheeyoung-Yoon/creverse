#!/usr/bin/env python3

import json
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.rubric import RubricItemResult

def test_schema():
    """Test if Pydantic schema generation works properly"""
    
    print("Testing RubricItemResult schema generation...")
    
    try:
        # Generate JSON schema
        schema = RubricItemResult.model_json_schema()
        print("Schema generated successfully:")
        print(json.dumps(schema, indent=2))
        
        # Test with sample data
        sample_data = {
            "rubric_item": "grammar",
            "score": 2,
            "corrections": [
                {
                    "highlight": "I want go",
                    "issue": "missing to-be",
                    "correction": "I want to go"
                }
            ],
            "feedback": "Good effort! Just need to add 'to' before verbs."
        }
        
        print("\nTesting with sample data:")
        print(json.dumps(sample_data, indent=2))
        
        # Try to create Pydantic object
        result = RubricItemResult(**sample_data)
        print("\nPydantic object created successfully:")
        print(result.model_dump())
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_schema()