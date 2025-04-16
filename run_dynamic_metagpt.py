#!/usr/bin/env python
# run_dynamic_metagpt.py
# Main entry point for Enhanced Free Models MetaGPT with dynamic configuration

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path
import yaml

from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_task_orchestrator_dynamic import DynamicTaskOrchestrator
from config_manager import DynamicConfigManager
from logger import ModelLogger

async def list_models(config_path: str):
    """List available models from OpenRouter.
    
    Args:
        config_path: Path to configuration file
    """
    # Initialize logger
    logger = ModelLogger(log_dir="./logs", log_level=logging.INFO)
    logger.log_processing_step("list_models", f"Initializing with config: {config_path}")
    
    # Initialize dynamic config manager
    config_manager = DynamicConfigManager(config_path)
    await config_manager.initialize()
    
    # Print API key info
    api_key = config_manager.config.get("OPENROUTER_API_KEY", "")
    if api_key:
        print(f"Using API key (first 5 chars): {api_key[:5]}...")
        logger.logger.info(f"Using API key (first 5 chars): {api_key[:5]}...")
    else:
        print("No API key found in configuration.")
        logger.log_error("Configuration", "No API key found in configuration")
        return []
    
    print("Fetching available models from OpenRouter...")
    
    try:
        # Fetch models
        logger.log_processing_step("fetch_models", "Fetching available models from OpenRouter")
        await config_manager.model_registry.fetch_available_models()
        
        # Get all models
        all_models = config_manager.model_registry.available_models
        
        # Get free models
        free_models = config_manager.model_registry.free_models
        
        # Display API key info
        print(f"\n{'=' * 60}")
        print(f"Found {len(all_models)} total models")
        print(f"Found {len(free_models)} free models")
        print(f"{'=' * 60}")
        
        # Display free models
        for i, (model_id, model_data) in enumerate(free_models.items(), 1):
            context_length = model_data.get("context_length", "Unknown")
            print(f"{i}. {model_id}")
            print(f"   Context length: {context_length}")
            print(f"   Description: {model_data.get('description', 'No description')}")
            print(f"{'=' * 60}")
        
        return list(free_models.keys())
    except Exception as e:
        error_msg = f"Error fetching models: {str(e)}"
        print(error_msg)
        logger.log_error("API", error_msg, {"exception": str(e)})
        return []

async def list_roles(config_path: str):
    """List available roles.
    
    Args:
        config_path: Path to configuration file
    """
    # Initialize logger
    logger = ModelLogger(log_dir="./logs", log_level=logging.INFO)
    logger.log_processing_step("list_roles", f"Initializing with config: {config_path}")
    
    # Initialize dynamic config manager
    config_manager = DynamicConfigManager(config_path)
    await config_manager.initialize()
    
    # List roles
    roles = config_manager.role_manager.list_roles()
    
    print("\nBuilt-in Roles:")
    for role in roles["builtin"]:
        role_data = config_manager.role_manager.get_role(role)
        print(f"- {role}: {role_data.get('name', role)}")
        print(f"  {role_data.get('description', '')}")
    
    if roles["custom"]:
        print("\nCustom Roles:")
        for role in roles["custom"]:
            role_data = config_manager.role_manager.get_role(role)
            print(f"- {role}: {role_data.get('name', role)}")
            print(f"  {role_data.get('description', '')}")
    else:
        print("\nNo custom roles defined.")
        
    return roles

async def list_workflows(config_path: str):
    """List available workflows.
    
    Args:
        config_path: Path to configuration file
    """
    # Initialize logger
    logger = ModelLogger(log_dir="./logs", log_level=logging.INFO)
    logger.log_processing_step("list_workflows", f"Initializing with config: {config_path}")
    
    # Initialize dynamic config manager
    config_manager = DynamicConfigManager(config_path)
    await config_manager.initialize()
    
    # List workflows
    workflows = config_manager.workflow_manager.list_workflows()
    
    print("\nAvailable Workflows:")
    for workflow in workflows:
        print(f"- {workflow['name']}: {workflow['display_name']}")
        print(f"  {workflow['description']}")
        print(f"  Stages: {workflow['stages']}")
        
    return workflows

async def update_config(config_path: str):
    """Update configuration with available free models.
    
    Args:
        config_path: Path to configuration file
    """
    # Initialize logger
    logger = ModelLogger(log_dir="./logs", log_level=logging.INFO)
    logger.log_processing_step("update_config", f"Initializing with config: {config_path}")
    
    # Initialize dynamic config manager
    config_manager = DynamicConfigManager(config_path)
    await config_manager.initialize()
    
    print("Updating configuration with available models...")
    
    try:
        # Generate updated config
        logger.log_processing_step("generate_config", "Generating updated configuration from available models")
        new_config = await config_manager.generate_config_from_available_models()
        
        # Save new config
        with open(config_path, 'w') as f:
            yaml.dump(new_config, f, default_flow_style=False)
            
        print(f"Configuration updated and saved to {config_path}")
        
        # Show updated model assignments
        print("\nUpdated Task-Model Assignments:")
        for task, task_config in new_config.get("TASK_MODEL_MAPPING", {}).items():
            primary_model = task_config.get("primary", {}).get("model", "N/A")
            backup_model = task_config.get("backup", {}).get("model", "N/A")
            print(f"- {task}:")
            print(f"  Primary: {primary_model}")
            print(f"  Backup: {backup_model}")
            
        return new_config
    except Exception as e:
        error_msg = f"Error updating configuration: {str(e)}"
        print(error_msg)
        logger.log_error("Configuration", error_msg, {"exception": str(e)})
        return None

async def run_project(config_path: str, idea: str, workflow: str = "standard", parallel: bool = False, 
                     workspace_dir: str = "./workspace", disable_validation: bool = False,
                     log_dir: str = "./logs", log_level: str = "INFO", no_console_log: bool = False):
    """Run a project using the Enhanced Free Models MetaGPT with dynamic configuration.
    
    Args:
        config_path: Path to configuration file
        idea: Project idea/requirements
        workflow: Name of the workflow to use
        parallel: Whether to run tasks in parallel where possible
        workspace_dir: Directory to save outputs
        disable_validation: Whether to disable validation of outputs
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
    logger.logger.info(f"Using workflow: {workflow}")
    logger.logger.info(f"Parallel mode: {parallel}")
    logger.logger.info(f"Validation: {'Disabled' if disable_validation else 'Enabled'}")
    
    print(f"Running project with idea: {idea}")
    print(f"Using workflow: {workflow}")
    print(f"Parallel mode: {parallel}")
    print(f"Validation: {'Disabled' if disable_validation else 'Enabled'}")
    print(f"Logs will be saved to: {os.path.abspath(log_dir)}")
    
    # Initialize orchestrator
    logger.log_processing_step("initialize_orchestrator", f"Initializing with config: {config_path}")
    orchestrator = DynamicTaskOrchestrator(config_path)
    await orchestrator.initialize()
    
    # Set validation flag in orchestrator
    if disable_validation and hasattr(orchestrator, 'validator'):
        # Temporarily disable validation
        orchestrator.validation_enabled = not disable_validation
    
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
                workflow_name=workflow,
                workspace_dir=workspace_dir
            )
        else:
            print("Running in sequential mode...")
            logger.log_processing_step("run_workflow", "Starting sequential workflow execution")
            results = await orchestrator.run_workflow(
                input_idea=idea,
                workflow_name=workflow,
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

async def check_workflow_exists(config_path: str, workflow_name: str):
    """Check if a workflow exists in the configuration.
    
    Args:
        config_path: Path to configuration file
        workflow_name: Name of the workflow to check
        
    Returns:
        True if workflow exists, False otherwise
    """
    # Initialize logger
    logger = ModelLogger(log_dir="./logs", log_level=logging.INFO)
    logger.log_processing_step("check_workflow_exists", f"Checking if workflow '{workflow_name}' exists")
    
    # Initialize dynamic config manager
    config_manager = DynamicConfigManager(config_path)
    await config_manager.initialize()
    
    # Check if workflow exists
    workflow = config_manager.workflow_manager.get_workflow(workflow_name)
    return workflow is not None

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Enhanced Free Models MetaGPT with Dynamic Configuration")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List models command
    list_parser = subparsers.add_parser("list-models", help="List available free models from OpenRouter")
    list_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # List roles command
    list_roles_parser = subparsers.add_parser("list-roles", help="List available roles")
    list_roles_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # List workflows command
    list_workflows_parser = subparsers.add_parser("list-workflows", help="List available workflows")
    list_workflows_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # Update config command
    update_parser = subparsers.add_parser("update-config", help="Update configuration with available free models")
    update_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # Run project command
    run_parser = subparsers.add_parser("run", help="Run a project")
    run_parser.add_argument("--idea", required=True, help="Project idea/requirements")
    run_parser.add_argument("--workflow", default="standard", help="Workflow to use (e.g., standard, quick, design_only)")
    run_parser.add_argument("--parallel", action="store_true", help="Run tasks in parallel where possible")
    run_parser.add_argument("--workspace", default="./workspace", help="Directory to save outputs")
    run_parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    # Add the disable-validation flag
    run_parser.add_argument("--disable-validation", action="store_true", help="Disable validation of outputs")
    
    # Add logging options to all parsers
    for parser_name, parser_obj in [
        ("list-models", list_parser),
        ("list-roles", list_roles_parser),
        ("list-workflows", list_workflows_parser),
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
    
    # Ensure config file exists
    if not os.path.exists(args.config):
        print(f"Configuration file {args.config} not found.")
        print("Creating a new configuration file with default settings...")
        
        # Create default config
        default_config = {
            "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
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
            print("Warning: No OPENROUTER_API_KEY environment variable found.")
            print("Please set your API key in the configuration file or as an environment variable.")
    
    # Run the appropriate command
    if args.command == "list-models":
        asyncio.run(list_models(args.config))
    elif args.command == "list-roles":
        asyncio.run(list_roles(args.config))
    elif args.command == "list-workflows":
        asyncio.run(list_workflows(args.config))
    elif args.command == "update-config":
        asyncio.run(update_config(args.config))
    elif args.command == "run":
        # Check if workflow exists
        if not asyncio.run(check_workflow_exists(args.config, args.workflow)):
            error_msg = f"Workflow '{args.workflow}' not found"
            print(f"Error: {error_msg}")
            logger.log_error("Workflow", error_msg)
            print("Available workflows:")
            workflows = asyncio.run(list_workflows(args.config))
            for workflow in workflows:
                print(f"- {workflow['name']}")
            return
        
        # Ensure workspace directory exists
        workspace_dir = args.workspace
        os.makedirs(workspace_dir, exist_ok=True)
        
        # Run project
        asyncio.run(run_project(
            args.config, 
            args.idea, 
            args.workflow, 
            args.parallel, 
            workspace_dir,
            args.disable_validation,
            args.log_dir,
            args.log_level,
            args.no_console_log
        ))

if __name__ == "__main__":
    main()