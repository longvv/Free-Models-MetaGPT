#!/usr/bin/env python
# config_cli.py
# Command line interface for managing dynamic configurations

import os
import sys
import argparse
import asyncio
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path

from config_manager import DynamicConfigManager, RoleManager, WorkflowManager

async def list_models(config_manager: DynamicConfigManager) -> None:
    """List available models from OpenRouter.
    
    Args:
        config_manager: Dynamic configuration manager
    """
    print("Fetching available models from OpenRouter...")
    
    try:
        # Fetch models if not already fetched
        if not config_manager.model_registry.available_models:
            await config_manager.model_registry.fetch_available_models()
            
        # Get models
        all_models = config_manager.model_registry.available_models
        free_models = config_manager.model_registry.free_models
        
        print(f"\n{'=' * 60}")
        print(f"Found {len(all_models)} total models")
        print(f"Found {len(free_models)} free models")
        print(f"{'=' * 60}")
        
        # Display free models
        print("\nFree Models:")
        for i, (model_id, model_data) in enumerate(free_models.items(), 1):
            context_length = model_data.get("context_length", "Unknown")
            description = model_data.get("description", "No description")
            
            print(f"{i}. {model_id}")
            print(f"   Context length: {context_length}")
            print(f"   Description: {description[:100]}...")
            print(f"{'=' * 60}")
        
    except Exception as e:
        print(f"Error fetching models: {str(e)}")

async def list_roles(config_manager: DynamicConfigManager) -> None:
    """List available roles.
    
    Args:
        config_manager: Dynamic configuration manager
    """
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

async def list_workflows(config_manager: DynamicConfigManager) -> None:
    """List available workflows.
    
    Args:
        config_manager: Dynamic configuration manager
    """
    workflows = config_manager.workflow_manager.list_workflows()
    
    print("\nAvailable Workflows:")
    for workflow in workflows:
        print(f"- {workflow['name']}: {workflow['display_name']}")
        print(f"  {workflow['description']}")
        print(f"  Stages: {workflow['stages']}")

async def export_role(config_manager: DynamicConfigManager, role_name: str, output_file: str) -> None:
    """Export role definition to file.
    
    Args:
        config_manager: Dynamic configuration manager
        role_name: Name of the role to export
        output_file: Path to output file
    """
    role_data = config_manager.role_manager.get_role(role_name)
    if not role_data:
        print(f"Error: Role '{role_name}' not found")
        return
    
    try:
        with open(output_file, 'w') as f:
            yaml.dump(role_data, f, default_flow_style=False)
        print(f"Role '{role_name}' exported to {output_file}")
    except Exception as e:
        print(f"Error exporting role: {str(e)}")

async def import_role(config_manager: DynamicConfigManager, role_name: str, input_file: str) -> None:
    """Import role definition from file.
    
    Args:
        config_manager: Dynamic configuration manager
        role_name: Name for the imported role
        input_file: Path to input file
    """
    try:
        with open(input_file, 'r') as f:
            role_data = yaml.safe_load(f)
            
        if config_manager.role_manager.create_role(role_name, role_data):
            print(f"Role '{role_name}' imported successfully")
        else:
            print(f"Error importing role '{role_name}'")
    except Exception as e:
        print(f"Error importing role: {str(e)}")

async def export_workflow(config_manager: DynamicConfigManager, workflow_name: str, output_file: str) -> None:
    """Export workflow definition to file.
    
    Args:
        config_manager: Dynamic configuration manager
        workflow_name: Name of the workflow to export
        output_file: Path to output file
    """
    workflow_data = config_manager.workflow_manager.get_workflow(workflow_name)
    if not workflow_data:
        print(f"Error: Workflow '{workflow_name}' not found")
        return
    
    try:
        with open(output_file, 'w') as f:
            yaml.dump(workflow_data, f, default_flow_style=False)
        print(f"Workflow '{workflow_name}' exported to {output_file}")
    except Exception as e:
        print(f"Error exporting workflow: {str(e)}")

async def import_workflow(config_manager: DynamicConfigManager, workflow_name: str, input_file: str) -> None:
    """Import workflow definition from file.
    
    Args:
        config_manager: Dynamic configuration manager
        workflow_name: Name for the imported workflow
        input_file: Path to input file
    """
    try:
        with open(input_file, 'r') as f:
            workflow_data = yaml.safe_load(f)
            
        if config_manager.workflow_manager.create_workflow(workflow_name, workflow_data):
            print(f"Workflow '{workflow_name}' imported successfully")
        else:
            print(f"Error importing workflow '{workflow_name}'")
    except Exception as e:
        print(f"Error importing workflow: {str(e)}")

async def update_config_from_models(config_manager: DynamicConfigManager) -> None:
    """Update configuration with available models.
    
    Args:
        config_manager: Dynamic configuration manager
    """
    print("Updating configuration with available models...")
    
    try:
        new_config = await config_manager.generate_config_from_available_models()
        
        # Save new config
        with open(config_manager.config_path, 'w') as f:
            yaml.dump(new_config, f, default_flow_style=False)
            
        print(f"Configuration updated and saved to {config_manager.config_path}")
        
        # Show updated model assignments
        print("\nUpdated Task-Model Assignments:")
        for task, task_config in new_config.get("TASK_MODEL_MAPPING", {}).items():
            primary_model = task_config.get("primary", {}).get("model", "N/A")
            backup_model = task_config.get("backup", {}).get("model", "N/A")
            print(f"- {task}:")
            print(f"  Primary: {primary_model}")
            print(f"  Backup: {backup_model}")
            
    except Exception as e:
        print(f"Error updating configuration: {str(e)}")

async def set_workflow(config_manager: DynamicConfigManager, workflow_name: str) -> None:
    """Set the active workflow in configuration.
    
    Args:
        config_manager: Dynamic configuration manager
        workflow_name: Name of the workflow to set
    """
    if config_manager.update_config_with_workflow(workflow_name):
        print(f"Workflow set to '{workflow_name}'")
        
        # Show workflow stages
        workflow_stages = config_manager.get_workflow_stages(workflow_name)
        print("\nWorkflow Stages:")
        for i, stage in enumerate(workflow_stages, 1):
            print(f"{i}. {stage.get('task')} → {stage.get('output')}")
    else:
        print(f"Error: Could not set workflow to '{workflow_name}'")

async def create_custom_role(config_manager: DynamicConfigManager, 
                           role_name: str,
                           display_name: str,
                           description: str,
                           system_prompt_file: str) -> None:
    """Create a new custom role.
    
    Args:
        config_manager: Dynamic configuration manager
        role_name: Name for the new role
        display_name: Display name for the role
        description: Description of the role
        system_prompt_file: Path to file containing system prompt
    """
    try:
        # Read system prompt from file
        with open(system_prompt_file, 'r') as f:
            system_prompt = f.read()
            
        role_data = {
            "name": display_name,
            "description": description,
            "system_prompt": system_prompt,
            "output_format": {
                "sections": ["Summary", "Analysis", "Recommendations"],
                "validation": {
                    "required_patterns": []
                }
            },
            "model_preferences": {
                "context_size": "large",
                "temperature": 0.1
            }
        }
        
        if config_manager.role_manager.create_role(role_name, role_data):
            print(f"Custom role '{role_name}' created successfully")
        else:
            print(f"Error creating custom role '{role_name}'")
    except Exception as e:
        print(f"Error creating custom role: {str(e)}")

async def create_custom_workflow(config_manager: DynamicConfigManager,
                                workflow_name: str,
                                display_name: str,
                                description: str,
                                stages_file: str) -> None:
    """Create a new custom workflow.
    
    Args:
        config_manager: Dynamic configuration manager
        workflow_name: Name for the new workflow
        display_name: Display name for the workflow
        description: Description of the workflow
        stages_file: Path to file containing workflow stages
    """
    try:
        # Read stages from file
        with open(stages_file, 'r') as f:
            stages_data = yaml.safe_load(f)
            
        if not isinstance(stages_data, list):
            print("Error: Stages file must contain a list of stage dictionaries")
            return
            
        workflow_data = {
            "name": display_name,
            "description": description,
            "stages": stages_data
        }
        
        if config_manager.workflow_manager.create_workflow(workflow_name, workflow_data):
            print(f"Custom workflow '{workflow_name}' created successfully")
        else:
            print(f"Error creating custom workflow '{workflow_name}'")
    except Exception as e:
        print(f"Error creating custom workflow: {str(e)}")

async def main():
    parser = argparse.ArgumentParser(description="Dynamic Configuration Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Global arguments
    parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    
    # List models command
    subparsers.add_parser("list-models", help="List available models from OpenRouter")
    
    # List roles command
    subparsers.add_parser("list-roles", help="List available roles")
    
    # List workflows command
    subparsers.add_parser("list-workflows", help="List available workflows")
    
    # Export role command
    export_role_parser = subparsers.add_parser("export-role", help="Export role definition to file")
    export_role_parser.add_argument("role", help="Name of the role to export")
    export_role_parser.add_argument("--output", required=True, help="Output file path")
    
    # Import role command
    import_role_parser = subparsers.add_parser("import-role", help="Import role definition from file")
    import_role_parser.add_argument("role", help="Name for the imported role")
    import_role_parser.add_argument("--input", required=True, help="Input file path")
    
    # Export workflow command
    export_workflow_parser = subparsers.add_parser("export-workflow", help="Export workflow definition to file")
    export_workflow_parser.add_argument("workflow", help="Name of the workflow to export")
    export_workflow_parser.add_argument("--output", required=True, help="Output file path")
    
    # Import workflow command
    import_workflow_parser = subparsers.add_parser("import-workflow", help="Import workflow definition from file")
    import_workflow_parser.add_argument("workflow", help="Name for the imported workflow")
    import_workflow_parser.add_argument("--input", required=True, help="Input file path")
    
    # Update config command
    subparsers.add_parser("update-config", help="Update configuration with available models")
    
    # Set workflow command
    set_workflow_parser = subparsers.add_parser("set-workflow", help="Set the active workflow in configuration")
    set_workflow_parser.add_argument("workflow", help="Name of the workflow to set")
    
    # Create custom role command
    create_role_parser = subparsers.add_parser("create-role", help="Create a new custom role")
    create_role_parser.add_argument("name", help="Name for the new role")
    create_role_parser.add_argument("--display-name", required=True, help="Display name for the role")
    create_role_parser.add_argument("--description", required=True, help="Description of the role")
    create_role_parser.add_argument("--prompt-file", required=True, help="Path to file containing system prompt")
    
    # Create custom workflow command
    create_workflow_parser = subparsers.add_parser("create-workflow", help="Create a new custom workflow")
    create_workflow_parser.add_argument("name", help="Name for the new workflow")
    create_workflow_parser.add_argument("--display-name", required=True, help="Display name for the workflow")
    create_workflow_parser.add_argument("--description", required=True, help="Description of the workflow")
    create_workflow_parser.add_argument("--stages-file", required=True, help="Path to file containing workflow stages")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize configuration manager
    config_manager = DynamicConfigManager(args.config)
    await config_manager.initialize()
    
    # Run the appropriate command
    if args.command == "list-models":
        await list_models(config_manager)
    elif args.command == "list-roles":
        await list_roles(config_manager)
    elif args.command == "list-workflows":
        await list_workflows(config_manager)
    elif args.command == "export-role":
        await export_role(config_manager, args.role, args.output)
    elif args.command == "import-role":
        await import_role(config_manager, args.role, args.input)
    elif args.command == "export-workflow":
        await export_workflow(config_manager, args.workflow, args.output)
    elif args.command == "import-workflow":
        await import_workflow(config_manager, args.workflow, args.input)
    elif args.command == "update-config":
        await update_config_from_models(config_manager)
    elif args.command == "set-workflow":
        await set_workflow(config_manager, args.workflow)
    elif args.command == "create-role":
        await create_custom_role(config_manager, args.name, args.display_name, args.description, args.prompt_file)
    elif args.command == "create-workflow":
        await create_custom_workflow(config_manager, args.name, args.display_name, args.description, args.stages_file)

if __name__ == "__main__":
    asyncio.run(main())