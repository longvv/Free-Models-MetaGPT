#!/usr/bin/env python
# run_free_models_metagpt.py
# Main entry point for Enhanced Free Models MetaGPT

import os
import sys
import argparse
import asyncio
from pathlib import Path
import yaml

from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_task_orchestrator import EnhancedTaskOrchestrator

async def list_models(config_path: str):
    """List available models from OpenRouter.
    
    Args:
        config_path: Path to configuration file
    """
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    # Initialize OpenRouter adapter
    adapter = EnhancedOpenRouterAdapter(config)
    
    print("Fetching available models from OpenRouter...")
    # First, get all models to see if the API connection works
    all_models = await adapter.get_available_models()
    
    # If we have model-specific keys, list those models
    model_keys = []
    for task_name, task_config in config.get("TASK_MODEL_MAPPING", {}).items():
        primary_config = task_config.get("primary", {})
        backup_config = task_config.get("backup", {})
        
        if primary_config.get("model") and primary_config.get("api_key"):
            model_keys.append((primary_config.get("model"), primary_config.get("api_key")))
            
        if backup_config.get("model") and backup_config.get("api_key"):
            model_keys.append((backup_config.get("model"), backup_config.get("api_key")))
    
    print(f"\n{'=' * 60}")
    print(f"Found {len(all_models)} total models")
    print(f"You have {len(model_keys)} models with specific API keys configured:")
    print(f"{'=' * 60}")
    
    for model_name, key in model_keys:
        key_short = f"{key[:10]}...{key[-5:]}" if key else "None"
        print(f"Model: {model_name}")
        print(f"API Key: {key_short}")
        print(f"{'-' * 40}")
        
    return all_models
    """List available free models from OpenRouter.
    
    Args:
        config_path: Path to configuration file
    """
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    # Initialize OpenRouter adapter
    adapter = EnhancedOpenRouterAdapter(config)
    
    print("Fetching available models from OpenRouter...")
    # First, get all models to see if the API connection works
    all_models = await adapter.get_available_models()
    
    # If we have model-specific keys, list those models
    model_keys = []
    for task_name, task_config in config.get("TASK_MODEL_MAPPING", {}).items():
        primary_config = task_config.get("primary", {})
        backup_config = task_config.get("backup", {})
        
        if primary_config.get("model") and primary_config.get("api_key"):
            model_keys.append((primary_config.get("model"), primary_config.get("api_key")))
            
        if backup_config.get("model") and backup_config.get("api_key"):
            model_keys.append((backup_config.get("model"), backup_config.get("api_key")))
    
    print(f"\n{'=' * 60}")
    print(f"Found {len(all_models)} total models")
    print(f"You have {len(model_keys)} models with specific API keys configured:")
    print(f"{'=' * 60}")
    
    for model_name, key in model_keys:
        key_short = f"{key[:10]}...{key[-5:]}" if key else "None"
        print(f"Model: {model_name}")
        print(f"API Key: {key_short}")
        print(f"{'-' * 40}")
    
    for i, model in enumerate(free_models, 1):
        model_id = model.get("id", "Unknown")
        context_length = model.get("context_length", "Unknown")
        print(f"{i}. {model_id}")
        print(f"   Context length: {context_length}")
        print(f"   Description: {model.get('description', 'No description')}")
        print(f"{'=' * 60}")
    
    return free_models

async def update_config(config_path: str):
    """Update configuration with available free models.
    
    Args:
        config_path: Path to configuration file
    """
    # First, get available models
    free_models = await list_models(config_path)
    
    # Load existing config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print("\nUpdating configuration with available free models...")
    
    # Create a mapping of model types for recommendation
    model_recommendations = {
        "large": [],
        "medium": [],
        "small": [],
        "code": []
    }
    
    # Categorize models based on their features
    for model in free_models:
        model_id = model.get("id", "")
        
        if any(code_term in model_id.lower() for code_term in ["code", "coder", "wizard"]):
            model_recommendations["code"].append(model_id)
        elif any(large_term in model_id.lower() for large_term in ["70b", "65b", "40b"]):
            model_recommendations["large"].append(model_id)
        elif any(medium_term in model_id.lower() for medium_term in ["13b", "20b", "30b"]):
            model_recommendations["medium"].append(model_id)
        else:
            model_recommendations["small"].append(model_id)
    
    # Update task model mapping if models are available
    mapping_updated = False
    for task, rec_type in [
        ("requirements_analysis", "large"), 
        ("system_design", "medium"),
        ("implementation_planning", "large"),
        ("code_generation", "code"),
        ("code_review", "code")
    ]:
        if task in config.get("TASK_MODEL_MAPPING", {}) and model_recommendations[rec_type]:
            # Only update if we have recommendations for this type
            task_config = config["TASK_MODEL_MAPPING"][task]
            
            # Get current models
            current_primary = task_config.get("primary", {}).get("model", "")
            current_backup = task_config.get("backup", {}).get("model", "")
            
            # Check if current models are still available
            primary_available = any(current_primary == model.get("id", "") for model in free_models)
            backup_available = any(current_backup == model.get("id", "") for model in free_models)
            
            if not primary_available and model_recommendations[rec_type]:
                # Update primary model
                new_primary = model_recommendations[rec_type][0]
                task_config["primary"]["model"] = new_primary
                print(f"Updated {task} primary model to {new_primary}")
                mapping_updated = True
                
                # Move to next recommendation for variety
                if len(model_recommendations[rec_type]) > 1:
                    model_recommendations[rec_type] = model_recommendations[rec_type][1:] + [model_recommendations[rec_type][0]]
            
            if not backup_available and model_recommendations[rec_type]:
                # Update backup model
                new_backup = model_recommendations[rec_type][0]
                task_config["backup"]["model"] = new_backup
                print(f"Updated {task} backup model to {new_backup}")
                mapping_updated = True
                
                # Move to next recommendation for variety
                if len(model_recommendations[rec_type]) > 1:
                    model_recommendations[rec_type] = model_recommendations[rec_type][1:] + [model_recommendations[rec_type][0]]
    
    if not mapping_updated:
        print("All models in configuration are up-to-date with available free models.")
    else:
        # Save updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"Configuration updated and saved to {config_path}")
    
    return config

async def run_project(config_path: str, idea: str, parallel: bool = False, workspace_dir: str = "./workspace"):
    """Run a project using the Enhanced Free Models MetaGPT.
    
    Args:
        config_path: Path to configuration file
        idea: Project idea/requirements
        parallel: Whether to run tasks in parallel where possible
        workspace_dir: Directory to save outputs
    """
    print(f"Running project with idea: {idea}")
    print(f"Parallel mode: {parallel}")
    
    # Initialize orchestrator
    orchestrator = EnhancedTaskOrchestrator(config_path)
    
    # Run workflow
    if parallel:
        print("Running in parallel mode...")
        results = await orchestrator.run_parallel_workflow(
            input_idea=idea,
            workspace_dir=workspace_dir
        )
    else:
        print("Running in sequential mode...")
        results = await orchestrator.run_workflow(
            input_idea=idea,
            workspace_dir=workspace_dir
        )
    
    print(f"\nProject completed! Results saved to {workspace_dir}")
    print("Files generated:")
    for key in results.keys():
        if key != "user_idea":
            print(f"- {key}.txt")
    print(f"- project_summary.md")
    
    return results

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Enhanced Free Models MetaGPT")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List models command
    list_parser = subparsers.add_parser("list-models", help="List available free models from OpenRouter")
    list_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # Update config command
    update_parser = subparsers.add_parser("update-config", help="Update configuration with available free models")
    update_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # Run project command
    run_parser = subparsers.add_parser("run", help="Run a project")
    run_parser.add_argument("--idea", required=True, help="Project idea/requirements")
    run_parser.add_argument("--parallel", action="store_true", help="Run tasks in parallel where possible")
    run_parser.add_argument("--workspace", default="./workspace", help="Directory to save outputs")
    run_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Ensure config file exists
    if not os.path.exists(args.config):
        print(f"Error: Configuration file {args.config} not found.")
        return
    
    # Run the appropriate command
    if args.command == "list-models":
        asyncio.run(list_models(args.config))
    elif args.command == "update-config":
        asyncio.run(update_config(args.config))
    elif args.command == "run":
        # Ensure workspace directory exists
        workspace_dir = args.workspace
        os.makedirs(workspace_dir, exist_ok=True)
        
        # Run project
        asyncio.run(run_project(args.config, args.idea, args.parallel, workspace_dir))

if __name__ == "__main__":
    main()