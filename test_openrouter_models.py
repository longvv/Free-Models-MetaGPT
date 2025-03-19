#!/usr/bin/env python
# updated_test_openrouter_models.py
# Test script that includes the :free suffix in model names

import os
import yaml
import asyncio
import aiohttp
import json
from typing import Dict, List, Any

async def test_model(api_key: str, model_name: str) -> bool:
    """Test if a model works with your API key.
    
    Args:
        api_key: OpenRouter API key
        model_name: Model name to test
        
    Returns:
        True if model works, False otherwise
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://metagpt.com",
        "X-Title": "Model Test"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Say hello!"}
        ],
        "max_tokens": 10
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, 
                                  json=payload, 
                                  headers=headers, 
                                  timeout=30) as response:
                
                if response.status == 200:
                    result = await response.json()
                    message = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"✅ {model_name}: {message[:50]}...")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ {model_name}: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ {model_name}: {str(e)}")
        return False

async def test_free_models(api_key: str) -> List[str]:
    """Test OpenRouter models with the :free suffix.
    
    Args:
        api_key: OpenRouter API key
        
    Returns:
        List of working model names
    """
    models_to_test = [
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-7b-it:free",
        "meta-llama/llama-2-13b-chat:free",
        "meta-llama/llama-2-70b-chat:free",
        "meta-llama/llama-3-8b-instruct:free",
        "openchat/openchat-7b:free",
        "open-r1/olympiccoder-32b:free",
        "anthropic/claude-3-opus-20240229:free",
        "deepseek/deepseek-r1-distill-llama-70b:free",
        "google/gemma-3-27b-it:free"
    ]
    
    print("Testing models with :free suffix...")
    working_models = []
    
    for model in models_to_test:
        if await test_model(api_key, model):
            working_models.append(model)
    
    return working_models

async def main():
    # Load config to get API key
    config_path = "config.yml"
    
    if not os.path.exists(config_path):
        print(f"Error: Configuration file {config_path} not found.")
        return
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    api_key = config.get("OPENROUTER_API_KEY")
    
    if not api_key:
        print("Error: OpenRouter API key not found in config.yml")
        return
    
    print(f"Testing API key (first 5 chars): {api_key[:5]}...")
    
    # Test free models
    working_models = await test_free_models(api_key)
    
    if not working_models:
        print("\nNo models with :free suffix are working with your API key.")
        return
    
    print(f"\n✅ Found {len(working_models)} working models with :free suffix:")
    for model in working_models:
        print(f"  - {model}")
    
    # Create recommended config
    print("\nGenerating recommended configuration...")
    
    recommended_config = {
        "OPENROUTER_API_KEY": api_key,
        "TASK_MODEL_MAPPING": {
            "code_review": {
                "primary": {
                    "model": working_models[0] if working_models else "mistralai/mistral-7b-instruct:free",
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "context_window": 8000,
                    "system_prompt": "You are a code reviewer focused on quality and correctness."
                },
                "backup": {
                    "model": working_models[1] if len(working_models) > 1 else working_models[0] if working_models else "mistralai/mistral-7b-instruct:free",
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "context_window": 8000,
                    "system_prompt": "You are a code reviewer focused on quality and correctness."
                }
            }
        }
    }
    
    # Save recommended config
    with open("free_models_config.yml", 'w') as f:
        yaml.dump(recommended_config, f, default_flow_style=False)
    
    print(f"Recommended configuration saved to free_models_config.yml")
    print(f"To use this configuration, run:")
    print(f"python run_repo_review.py --repo /path/to/your/repository --config free_models_config.yml")

if __name__ == "__main__":
    asyncio.run(main())