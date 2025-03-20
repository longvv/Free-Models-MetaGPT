#!/usr/bin/env python
# fix_free_models.py
# Quick fix script to update config.yml with free models and test them

import os
import sys
import yaml
import asyncio
import aiohttp
import json
from pathlib import Path

# Known working free models on OpenRouter
KNOWN_FREE_MODELS = [
    "google/gemma-3-27b-it:free",
    "deepseek/deepseek-r1-distill-llama-70b:free",
    "open-r1/olympiccoder-32b:free"
]

async def test_model(api_key, model_id):
    """Test if a model is working.
    
    Args:
        api_key: OpenRouter API key
        model_id: Model ID to test
        
    Returns:
        Tuple of (success, message)
    """
    print(f"Testing model: {model_id}")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://metagpt.com",
        "X-Title": "MetaGPT Free Models"
    }
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "Say hello! Keep it very short."}
        ],
        "max_tokens": 10
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                status = response.status
                
                if status == 200:
                    data = await response.json()
                    message = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"✅ Success! Response: {message}")
                    return True, message
                else:
                    error = await response.text()
                    print(f"❌ Error: {error}")
                    return False, error
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False, str(e)

async def find_working_models(api_key):
    """Find working free models.
    
    Args:
        api_key: OpenRouter API key
        
    Returns:
        List of working model IDs
    """
    working_models = []
    
    for model_id in KNOWN_FREE_MODELS:
        success, _ = await test_model(api_key, model_id)
        if success:
            working_models.append(model_id)
            
    return working_models

def update_config(config_path, working_models):
    """Update config.yml with working models.
    
    Args:
        config_path: Path to config.yml
        working_models: List of working model IDs
        
    Returns:
        Updated config
    """
    if not working_models:
        print("No working models found!")
        return None
        
    # Load existing config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    # Create task model mapping if it doesn't exist
    if "TASK_MODEL_MAPPING" not in config:
        config["TASK_MODEL_MAPPING"] = {}
        
    # Assign models to tasks
    tasks = [
        "requirements_analysis",
        "system_design",
        "implementation_planning",
        "code_generation",
        "code_review"
    ]
    
    for i, task in enumerate(tasks):
        primary_model = working_models[i % len(working_models)]
        backup_model = working_models[(i + 1) % len(working_models)]
        
        if task not in config["TASK_MODEL_MAPPING"]:
            config["TASK_MODEL_MAPPING"][task] = {}
            
        if "primary" not in config["TASK_MODEL_MAPPING"][task]:
            config["TASK_MODEL_MAPPING"][task]["primary"] = {}
            
        if "backup" not in config["TASK_MODEL_MAPPING"][task]:
            config["TASK_MODEL_MAPPING"][task]["backup"] = {}
            
        config["TASK_MODEL_MAPPING"][task]["primary"]["model"] = primary_model
        config["TASK_MODEL_MAPPING"][task]["backup"]["model"] = backup_model
        
    # Save updated config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
        
    print(f"Config updated with {len(working_models)} working models:")
    for model in working_models:
        print(f"- {model}")
        
    return config

async def main():
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description="Fix free models in config.yml")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    args = parser.parse_args()
    
    config_path = args.config
    
    # Check if config exists
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found")
        return
        
    # Load config to get API key
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    api_key = config.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    
    if not api_key:
        print("Error: No API key found in config or environment")
        return
        
    print(f"Using API key (first 5 chars): {api_key[:5]}...")
    
    # Find working models
    working_models = await find_working_models(api_key)
    
    if working_models:
        # Update config
        update_config(config_path, working_models)
        
        print("\nYou can now run:")
        print(f"python run_dynamic_metagpt.py run --idea \"Your project idea\"")
    else:
        print("\nNo working models found. Please check your API key and try again.")

if __name__ == "__main__":
    asyncio.run(main())
