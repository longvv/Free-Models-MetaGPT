#!/usr/bin/env python
# check_api_key.py
# Simple script to verify your OpenRouter API key

import os
import asyncio
import yaml
import json
import aiohttp
from pathlib import Path

async def test_api_key(api_key):
    """Test a specific API key with a simple model.
    
    Args:
        api_key: API key to test
    """
    print(f"Testing OpenRouter API key (first 5 chars): {api_key[:5]}...")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://metagpt.com",
        "X-Title": "MetaGPT API Test"
    }
    
    # Use a reliable model for testing
    payload = {
        "model": "google/gemma-3-27b-it:free",
        "messages": [
            {"role": "user", "content": "Say hello!"}
        ],
        "max_tokens": 50
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
    
    # Use environment variable first, then config file
    api_key = env_api_key or config_api_key
    
    if not api_key:
        print("❌ ERROR: No OpenRouter API key found.")
        print("Please set the OPENROUTER_API_KEY environment variable or add it to config.yml")
        return
        
    await test_api_key(api_key)

if __name__ == "__main__":
    asyncio.run(main())
