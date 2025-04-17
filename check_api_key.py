#!/usr/bin/env python
# check_api_key.py
# Simple script to verify your OpenRouter API key

import aiohttp
import asyncio
import os
import yaml
import json
from pathlib import Path

# Load config to get default API key and potentially a default model
CONFIG_PATH = Path(__file__).parent / "config.yml"
CONFIG = {}
if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, 'r') as f:
            CONFIG = yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Could not load config.yml: {e}")

OPENROUTER_CONFIG = CONFIG.get("OPENROUTER_CONFIG", {})
DEFAULT_API_KEY = OPENROUTER_CONFIG.get("default_api_key")

async def test_api_key(api_key):
    """Test a specific API key with a simple model.
    
    Args:
        api_key: API key to test
    """
    print(f"Testing OpenRouter API key (first 5 chars): {api_key[:5]}...")

    # Use a model from env var or a common default from config's fallback list
    test_model = os.getenv("OPENROUTER_TEST_MODEL", CONFIG.get("MODEL_REGISTRY", {}).get("fallback_free_models", ["google/gemini-flash-1.5:free"])[0])
    print(f"Using model '{test_model}' for API key check.")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://metagpt.com", # Optional: Helps OpenRouter identify traffic source
        "X-Title": "MetaGPT API Test" # Optional: Helps OpenRouter identify traffic source
    }
    data = {
        "model": test_model,
        "messages": [
            {"role": "user", "content": "Check API key status."}
        ],
        "max_tokens": 10
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, 
                                  json=payload, 
                                  headers=headers, 
                                  timeout=30) as response:
                
                status = response.status
                body = await response.text()
                
                print(f"Status code: {status}")
                
                if status == 200:
                    print("✅ SUCCESS! Your API key is working correctly.")
                    try:
                        json_response = json.loads(body)
                        message = json_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        print(f"Response: {message}")
                    except:
                        print("Could not parse JSON response")
                else:
                    print(f"❌ ERROR: {body}")
                    print("\nYour API key does not appear to be working.")
                    print("Please check the following:")
                    print("1. The API key is correct and not expired")
                    print("2. You have access to the models you're trying to use")
                    print("3. Your account is in good standing")
    except Exception as e:
        print(f"❌ Request failed: {str(e)}")

async def main():
    # Check if API key is in environment variable
    env_api_key = os.getenv("OPENROUTER_API_KEY")
    
    # Check if API key is in config file
    config_path = "config.yml"
    config_api_key = None
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            config_api_key = config.get("OPENROUTER_API_KEY")
    
    # Use environment variable or default key from config
    api_key = os.getenv("OPENROUTER_API_KEY") or DEFAULT_API_KEY
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set and no default_api_key found in config.yml.")
        return
        
    await test_api_key(api_key)

if __name__ == "__main__":
    asyncio.run(main())
