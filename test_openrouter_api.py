#!/usr/bin/env python
# test_openrouter_api.py
# Simple test script to verify OpenRouter API access

import os
import asyncio
import yaml
import json
import aiohttp
from pathlib import Path

async def test_api_key(api_key, model_id):
    """Test a specific API key with a model.
    
    Args:
        api_key: API key to test
        model_id: Model ID to test with
    """
    print(f"Testing API key for model: {model_id}")
    print(f"API key (first 5 chars): {api_key[:5]}...")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://metagpt.com",
        "X-Title": "MetaGPT API Test"
    }
    
    payload = {
        "model": model_id,
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
                
                print(f"Status: {status}")
                
                if status == 200:
                    print("Success! API key works for this model.")
                    try:
                        json_response = json.loads(body)
                        message = json_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        print(f"Response: {message}")
                    except:
                        print("Could not parse JSON response")
                else:
                    print(f"Error: {body}")
    except Exception as e:
        print(f"Request failed: {str(e)}")
    
    print("-" * 50)

async def main():
    # Load config
    config_path = "config.yml"
    
    if not os.path.exists(config_path):
        print(f"Error: Configuration file {config_path} not found.")
        return
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Check general API key
    general_api_key = config.get("OPENROUTER_API_KEY")
    if general_api_key:
        print("\nTesting general API key...")
        await test_api_key(general_api_key, "google/gemma-3-27b-it:free")
    
    # Test each model-specific API key
    print("\nTesting model-specific API keys...")
    for task_name, task_config in config.get("TASK_MODEL_MAPPING", {}).items():
        primary_config = task_config.get("primary", {})
        model_id = primary_config.get("model")
        api_key = primary_config.get("api_key")
        
        if model_id and api_key:
            print(f"\nTask: {task_name}")
            await test_api_key(api_key, model_id)

if __name__ == "__main__":
    asyncio.run(main())
