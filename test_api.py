#!/usr/bin/env python3
"""
Local API testing logic
"""

import requests
import json
import os
from pathlib import Path

def test_api_call():
    """Test API call"""

    # Simulate logic in GitHub Actions
    api_key = os.getenv('UPSTREAM_API_KEY')
    if not api_key:
        # Load from config file for local testing
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                api_key = config.get('openai', {}).get('api_key')
            if not api_key:
                print("ERROR: API key not set")
                return False
            print("INFO: Using API key from config.json")
        except Exception as e:
            print(f"ERROR: Failed to load API key from config: {e}")
            return False

    # Get Python files in current directory
    current_dir = Path(".")
    python_files = list(current_dir.glob("**/*.py"))
    print(f"Found Python files: {[str(f) for f in python_files]}")

    if not python_files:
        print("ERROR: No code files found")
        return True

    # Build file list string
    files_str = " ".join([str(f) for f in python_files])
    print(f"Files string: {files_str}")

    # Test API call
    url = "https://apis.iflow.cn/v1/chat/completions"

    # Simulate request body from GitHub Actions
    request_data = {
        "model": "glm-4.6",
        "max_tokens": 300,
        "messages": [
            {
                "role": "user",
                "content": f"Review these files: {files_str}"
            }
        ]
    }

    print(f"Sending API request to: {url}")
    print(f"Request body: {json.dumps(request_data, ensure_ascii=False, indent=2)}")

    try:
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json=request_data,
            timeout=30
        )

        print(f"HTTP status code: {response.status_code}")
        print(f"Response content: {response.text}")

        if response.status_code == 200:
            print("SUCCESS: API call successful")

            # Parse response
            try:
                resp_json = response.json()
                if 'choices' in resp_json and resp_json['choices']:
                    content = resp_json['choices'][0].get('message', {}).get('content', '')
                    print(f"AI Response: {content}")
                    return True
                else:
                    print("ERROR: Invalid response format")
                    return False
            except json.JSONDecodeError as e:
                print(f"ERROR: JSON parsing failed: {e}")
                return False
        else:
            print(f"ERROR: API call failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request exception: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unknown error: {e}")
        return False

if __name__ == "__main__":
    print("Starting local API test...")
    success = test_api_call()
    print(f"Test result: {'SUCCESS' if success else 'FAILED'}")