#!/usr/bin/env python3
import yaml
import json
import os
from pathlib import Path

def create_config_directories():
    """Create the new configuration directory structure."""
    base_path = Path("/Users/rian.vu/Documents/Free-Models-MetaGPT/config")
    roles_path = base_path / "roles"
    
    # Create directories
    base_path.mkdir(exist_ok=True)
    roles_path.mkdir(exist_ok=True)
    
    return base_path, roles_path

def extract_roles_from_config():
    """Extract role configurations from the current config.yml."""
    config_path = Path("/Users/rian.vu/Documents/Free-Models-MetaGPT/config.yml")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Extract roles section
    roles = config.get("ROLES", {})
    
    # Create new directory structure
    base_path, roles_path = create_config_directories()
    
    # Extract models configuration
    models_config = {
        "api_keys": {
            "default": config.get("OPENROUTER_CONFIG", {}).get("default_api_key", ""),
            "model_specific": config.get("OPENROUTER_CONFIG", {}).get("model_keys", {})
        },
        "models": {
            "capabilities": config.get("MODEL_REGISTRY", {}).get("model_capabilities", {}),
            "fallback_free_models": config.get("MODEL_REGISTRY", {}).get("fallback_free_models", []),
            "context_sizes": config.get("MODEL_REGISTRY", {}).get("model_context_sizes", {})
        }
    }
    
    # Save models configuration
    with open(base_path / "models.yml", 'w') as f:
        yaml.dump(models_config, f, default_flow_style=False, sort_keys=False)
    
    # Extract system configuration
    system_config = {
        "memory": config.get("MEMORY_SYSTEM", {}),
        "rate_limiting": config.get("RATE_LIMITING", {}),
        "validators": config.get("VALIDATORS", {})
    }
    
    # Save system configuration
    with open(base_path / "system.yml", 'w') as f:
        yaml.dump(system_config, f, default_flow_style=False, sort_keys=False)
    
    # Extract and save each role configuration
    for role_name, role_config in roles.items():
        # Add model information from MODEL_REGISTRY if available
        model_registry = config.get("MODEL_REGISTRY", {})
        task_capabilities = model_registry.get("model_capabilities", {})
        
        # Find models applicable to this role (assuming role_name matches task name)
        models = []
        for task, task_models in task_capabilities.items():
            if task.lower() == role_name.lower() or role_name.lower() in task.lower():
                models = task_models
                break
        
        # If no specific models found, use default
        if not models and "default_models_by_task" in model_registry:
            default_models = model_registry["default_models_by_task"].get("default", [])
            if default_models:
                models = default_models
        
        # Create role configuration
        role_data = {
            "role": {
                "name": role_config.get("name", role_name),
                "description": role_config.get("description", ""),
                "model": models[0] if models else "",
                "backup_models": models[1:] if len(models) > 1 else [],
                "system_prompt": role_config.get("system_prompt", ""),
                "output_format": role_config.get("output_format", {}),
                "model_preferences": role_config.get("model_preferences", {})
            }
        }
        
        # Save role configuration
        with open(roles_path / f"{role_name}.yml", 'w') as f:
            yaml.dump(role_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"Extracted {len(roles)} roles to {roles_path}")
    print(f"Created models.yml and system.yml in {base_path}")

if __name__ == "__main__":
    extract_roles_from_config()
