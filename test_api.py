#!/usr/bin/env python3

import json
import requests

def test_essay_eval():
    """Test the essay evaluation API"""
    
    # Test payload
    payload = {
        "essay_text": "I am going to school. I like my teacher.",
        "student_level": "Basic"
    }
    
    try:
        # Make request to local API
        response = requests.post(
            "http://localhost:8000/v1/essay-eval",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
    except requests.exceptions.ConnectionError:
        print("API server is not running. Start the server first with: python main.py")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_essay_eval()