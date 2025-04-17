#!/usr/bin/env python
# run_free_models_metagpt.py
# Main entry point for Enhanced Free Models MetaGPT

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path
import yaml

from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_task_orchestrator import EnhancedTaskOrchestrator
from logger import ModelLogger

async def list_models(config_path: str, log_dir="./logs", log_level="INFO", no_console_log=False):
    """List available models from OpenRouter.
    
    Args:
        config_path: Path to configuration file
        log_dir: Directory to save log files
        log_level: Logging level
        no_console_log: Whether to disable console logging
    """
    # Initialize logger
    log_level_num = getattr(logging, log_level)
    logger = ModelLogger(
        log_dir=log_dir,
        log_level=log_level_num,
        console_output=not no_console_log
    )
    
    logger.log_processing_step("list_models", f"Initializing with config: {config_path}")
    
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    # Initialize OpenRouter adapter
    adapter = EnhancedOpenRouterAdapter(config)
    
    print("Fetching available models from OpenRouter...")
    logger.log_processing_step("fetch_models", "Fetching available models from OpenRouter")
    
    try:
        # Get all models
        all_models = await adapter.get_available_models()
        
        # Get free models
        free_models = await adapter.get_free_models()
        
        # Display API key info
        print(f"\n{'=' * 60}")
        print(f"Found {len(all_models)} total models")
        print(f"Found {len(free_models)} free models")
        print(f"{'=' * 60}")
        
        logger.logger.info(f"Found {len(all_models)} total models")
        logger.logger.info(f"Found {len(free_models)} free models")
        
        # Display free models
        for i, model in enumerate(free_models, 1):
            model_id = model.get("id", "Unknown")
            context_length = model.get("context_length", "Unknown")
            print(f"{i}. {model_id}")
            print(f"   Context length: {context_length}")
            print(f"   Description: {model.get('description', 'No description')}")
            print(f"{'=' * 60}")
        
        return free_models
    except Exception as e:
        error_msg = f"Error fetching models: {str(e)}"
        print(error_msg)
        logger.log_error("API", error_msg, {"exception": str(e)})
        return []

async def update_config(config_path: str, log_dir="./logs", log_level="INFO", no_console_log=False):
    """Update configuration with available free models.
    
    Args:
        config_path: Path to configuration file
        log_dir: Directory to save log files
        log_level: Logging level
        no_console_log: Whether to disable console logging
    """
    # Initialize logger
    log_level_num = getattr(logging, log_level)
    logger = ModelLogger(
        log_dir=log_dir,
        log_level=log_level_num,
        console_output=not no_console_log
    )
    
    logger.log_processing_step("update_config", f"Initializing with config: {config_path}")
    
    # First, get available models
    free_models = await list_models(config_path, log_dir, log_level, no_console_log)
    
    # Load existing config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print("\nUpdating configuration with available free models...")
    logger.log_processing_step("update_config_models", "Updating configuration with available free models")
    
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
                logger.logger.info(f"Updated {task} primary model to {new_primary}")
                mapping_updated = True
                
                # Move to next recommendation for variety
                if len(model_recommendations[rec_type]) > 1:
                    model_recommendations[rec_type] = model_recommendations[rec_type][1:] + [model_recommendations[rec_type][0]]
            
            if not backup_available and model_recommendations[rec_type]:
                # Update backup model
                new_backup = model_recommendations[rec_type][0]
                task_config["backup"]["model"] = new_backup
                print(f"Updated {task} backup model to {new_backup}")
                logger.logger.info(f"Updated {task} backup model to {new_backup}")
                mapping_updated = True
                
                # Move to next recommendation for variety
                if len(model_recommendations[rec_type]) > 1:
                    model_recommendations[rec_type] = model_recommendations[rec_type][1:] + [model_recommendations[rec_type][0]]
    
    if not mapping_updated:
        print("All models in configuration are up-to-date with available free models.")
        logger.logger.info("All models in configuration are up-to-date with available free models.")
    else:
        # Save updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"Configuration updated and saved to {config_path}")
        logger.log_processing_step("config_saved", f"Configuration updated and saved to {config_path}")
    
    return config

async def run_project(config_path: str, idea: str, parallel: bool = False, workspace_dir: str = "./workspace",
                     log_dir: str = "./logs", log_level: str = "INFO", no_console_log: bool = False):
    """Run a project using the Enhanced Free Models MetaGPT.
    
    Args:
        config_path: Path to configuration file
        idea: Project idea/requirements
        parallel: Whether to run tasks in parallel where possible
        workspace_dir: Directory to save outputs
        log_dir: Directory to save log files
        log_level: Logging level
        no_console_log: Whether to disable console logging
    """
    # Initialize logger
    log_level_num = getattr(logging, log_level)
    logger = ModelLogger(
        log_dir=log_dir,
        log_level=log_level_num,
        console_output=not no_console_log
    )
    
    logger.log_processing_step("run_project", f"Starting project with idea: {idea}")
    logger.logger.info(f"Parallel mode: {parallel}")
    
    print(f"Running project with idea: {idea}")
    print(f"Parallel mode: {parallel}")
    print(f"Logs will be saved to: {os.path.abspath(log_dir)}")
    
    # Check model availability before starting
    logger.log_processing_step("check_models", "Checking model availability")
    all_available, unavailable_models = await check_model_availability(config_path, logger)
    if not all_available:
        warning_msg = "Some configured models are not available"
        print("WARNING: " + warning_msg)
        logger.logger.warning(warning_msg)
        for model in unavailable_models:
            print(f"  - {model}")
            logger.logger.warning(f"Unavailable model: {model}")
        print("The system will attempt to use backup models, but you may want to update your configuration.")
        confirm = input("Continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            logger.log_processing_step("operation_cancelled", "User cancelled operation due to unavailable models")
            return None
    
    # Initialize orchestrator
    logger.log_processing_step("initialize_orchestrator", f"Initializing with config: {config_path}")
    orchestrator = EnhancedTaskOrchestrator(config_path)
    
    # Attach logger to orchestrator if it has a logger attribute
    if hasattr(orchestrator, 'logger'):
        orchestrator.logger = logger
    
    # Run workflow
    try:
        if parallel:
            print("Running in parallel mode...")
            logger.log_processing_step("run_workflow", "Starting parallel workflow execution")
            results = await orchestrator.run_parallel_workflow(
                input_idea=idea,
                workspace_dir=workspace_dir
            )
        else:
            print("Running in sequential mode...")
            logger.log_processing_step("run_workflow", "Starting sequential workflow execution")
            results = await orchestrator.run_workflow(
                input_idea=idea,
                workspace_dir=workspace_dir
            )
        
        logger.log_processing_step("workflow_completed", "Workflow completed successfully")
    except Exception as e:
        error_msg = f"Error during workflow execution: {str(e)}"
        print(error_msg)
        logger.log_error("Workflow", error_msg, {"exception": str(e)})
        raise
    
    print(f"\nProject completed! Results saved to {workspace_dir}")
    print("Files generated:")
    for key in results.keys():
        if key != "user_idea":
            print(f"- {key}.txt")
    print(f"- project_summary.md")
    
    return results

async def check_model_availability(config_path: str, logger=None):
    """Check if configured models are available.
    
    Args:
        config_path: Path to configuration file
        logger: Logger instance
    
    Returns:
        Tuple of (all_available, unavailable_models)
    """
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if logger:
        logger.log_processing_step("check_model_availability", "Checking if configured models are available")
    
    # Get all configured models
    configured_models = set()
    for task, task_config in config.get("TASK_MODEL_MAPPING", {}).items():
        primary_model = task_config.get("primary", {}).get("model")
        backup_model = task_config.get("backup", {}).get("model")
        
        if primary_model:
            configured_models.add(primary_model)
        if backup_model:
            configured_models.add(backup_model)
    
    # Get available models
    adapter = EnhancedOpenRouterAdapter(config)
    try:
        available_models = await adapter.get_available_models()
        available_model_ids = [model.get("id") for model in available_models]
        
        # Check which configured models are not available
        unavailable_models = [model for model in configured_models if model not in available_model_ids]
        
        return (len(unavailable_models) == 0, unavailable_models)
    except Exception as e:
        if logger:
            logger.log_error("API", f"Error checking model availability: {str(e)}", {"exception": str(e)})
        print(f"Error checking model availability: {str(e)}")
        # Assume all models are available if we can't check
        return (True, [])

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
    
    # Add logging options to all parsers
    for parser_name, parser_obj in [
        ("list-models", list_parser),
        ("update-config", update_parser),
        ("run", run_parser)
    ]:
        parser_obj.add_argument("--log-dir", default="./logs", help="Directory to save log files")
        parser_obj.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                              default="INFO", help="Logging level")
        parser_obj.add_argument("--no-console-log", action="store_true", 
                              help="Disable logging to console")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize logger
    log_level = getattr(logging, args.log_level if hasattr(args, 'log_level') else "INFO")
    log_dir = args.log_dir if hasattr(args, 'log_dir') else "./logs"
    no_console_log = args.no_console_log if hasattr(args, 'no_console_log') else False
    
    logger = ModelLogger(
        log_dir=log_dir,
        log_level=log_level,
        console_output=not no_console_log
    )
    
    logger.log_processing_step("main", f"Starting command: {args.command}")
    
    # Ensure config file exists
    if not os.path.exists(args.config):
        print(f"Configuration file {args.config} not found.")
        print("Creating a new configuration file with default settings...")
        logger.log_processing_step("create_config", f"Creating new configuration file: {args.config}")
        
        # Create default config
        default_config = {
            "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
            "TASK_MODEL_MAPPING": {
                "requirements_analysis": {
                    "primary": {"model": "gpt-3.5-turbo"},
                    "backup": {"model": "claude-instant-1"}
                },
                "system_design": {
                    "primary": {"model": "gpt-3.5-turbo"},
                    "backup": {"model": "claude-instant-1"}
                },
                "implementation_planning": {
                    "primary": {"model": "gpt-3.5-turbo"},
                    "backup": {"model": "claude-instant-1"}
                },
                "code_generation": {
                    "primary": {"model": "gpt-3.5-turbo"},
                    "backup": {"model": "claude-instant-1"}
                },
                "code_review": {
                    "primary": {"model": "gpt-3.5-turbo"},
                    "backup": {"model": "claude-instant-1"}
                }
            },
            "MEMORY_SYSTEM": {
                "chunk_size": 1000,
                "overlap": 100,
                "vector_db": {
                    "embedding_model": "all-MiniLM-L6-v2",
                    "similarity_threshold": 0.75
                },
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 3600
                },
                "context_strategy": "smart_selection"
            },
            "RATE_LIMITING": {
                "requests_per_minute": 10,
                "max_parallel_requests": 2,
                "backoff_strategy": "exponential",
                "initial_backoff_seconds": 1,
                "max_backoff_seconds": 60
            }
        }
        
        # Save default config
        with open(args.config, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
            
        if not os.getenv("OPENROUTER_API_KEY"):
            warning_msg = "No OPENROUTER_API_KEY environment variable found"
            print(f"Warning: {warning_msg}")
            logger.log_error("Configuration", warning_msg, None)
            print("Please set your API key in the configuration file or as an environment variable.")
    
    try:
        # Run the appropriate command
        if args.command == "list-models":
            asyncio.run(list_models(args.config, args.log_dir, args.log_level, args.no_console_log))
        elif args.command == "update-config":
            asyncio.run(update_config(args.config, args.log_dir, args.log_level, args.no_console_log))
        elif args.command == "run":
            # Ensure workspace directory exists
            workspace_dir = args.workspace
            os.makedirs(workspace_dir, exist_ok=True)
            logger.log_processing_step("create_workspace", f"Creating workspace directory: {workspace_dir}")
            
            # Run project
            asyncio.run(run_project(
                args.config, 
                args.idea, 
                args.parallel, 
                workspace_dir,
                args.log_dir,
                args.log_level,
                args.no_console_log
            ))
    except Exception as e:
        error_msg = f"Unhandled exception: {str(e)}"
        print(f"Error: {error_msg}")
        logger.log_error("Main", error_msg, {"exception": str(e)})
        raise

if __name__ == "__main__":
    main()