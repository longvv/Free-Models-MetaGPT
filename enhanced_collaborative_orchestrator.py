#!/usr/bin/env python3
import asyncio
import json
import os
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from enhanced_config_manager import EnhancedConfigManager
from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_memory import EnhancedMemorySystem
from validators import ValidationSystem
from dynamic_model.collaborative_conversation import CollaborativeConversation

class EnhancedCollaborativeTaskOrchestrator:
    """Enhanced orchestrator that uses the modular configuration system."""
    
    def __init__(self, config_dir: str = None):
        """Initialize the enhanced orchestrator.
        
        Args:
            config_dir: Path to the configuration directory
        """
        config_path = Path(config_dir) if config_dir else None
        self.config_manager = EnhancedConfigManager(config_path)
        
        # Components initialized during initialize()
        self.adapter = None
        self.memory = None
        self.validator = None
        self.conversation = None
        
        # Workflow tracking
        self.current_workflow_config = None
        
    async def initialize(self):
        """Initialize the orchestrator and its components."""
        # Initialize the configuration manager
        await self.config_manager.initialize()
        
        # Get API keys for the adapter
        api_keys = self.config_manager.get_api_keys()
        
        # Create configuration for the OpenRouter adapter
        adapter_config = {
            "OPENROUTER_CONFIG": {
                "default_api_key": api_keys.get("default"),
                "model_keys": api_keys.get("model_specific", {})
            }
        }
        
        # Print API keys configuration for debugging
        print(f"Using default API key (first 5 chars): {api_keys.get('default', '')[:5]}...")
        print(f"Loaded {len(api_keys.get('model_specific', {}))} model-specific API keys")
        
        # Initialize adapter with the configuration
        self.adapter = EnhancedOpenRouterAdapter(adapter_config)
        
        # Initialize memory system
        memory_config = self.config_manager.get_system_config("memory")
        self.memory = EnhancedMemorySystem(memory_config)
        
        # Initialize validator
        validator_config = self.config_manager.get_system_config("validators")
        self.validator = ValidationSystem(validator_config)
        
        # Initialize conversation manager
        self.conversation = CollaborativeConversation(
            {}, # No specific conversation config needed
            self.adapter,
            self.memory
        )
        
        print("Enhanced collaborative task orchestrator initialized successfully")
    
    def _load_workflow(self, workflow_name: str) -> Optional[List[Dict[str, Any]]]:
        """Load a workflow configuration.
        
        Args:
            workflow_name: Name of the workflow or path to workflow file
            
        Returns:
            List of workflow stages or None if not found
        """
        # Check if workflow_name is a file path
        workflow_path = Path(workflow_name)
        if workflow_path.exists() and workflow_path.is_file():
            try:
                with open(workflow_path, 'r') as f:
                    workflow_config = yaml.safe_load(f)
                
                # Extract stages based on format
                if isinstance(workflow_config, list):
                    return workflow_config
                elif isinstance(workflow_config, dict) and 'stages' in workflow_config:
                    return workflow_config['stages']
                else:
                    print(f"Warning: Unexpected format in workflow file: {workflow_path}")
                    return None
            except Exception as e:
                print(f"Error loading workflow file {workflow_path}: {e}")
                return None
        
        # Otherwise, try to find workflow in standard location
        workflows_dir = Path("/Users/rian.vu/Documents/Free-Models-MetaGPT/workflows")
        workflow_file = workflows_dir / f"{workflow_name}.yml"
        
        if workflow_file.exists():
            try:
                with open(workflow_file, 'r') as f:
                    workflow_config = yaml.safe_load(f)
                
                # Extract stages based on format
                if isinstance(workflow_config, list):
                    return workflow_config
                elif isinstance(workflow_config, dict) and 'stages' in workflow_config:
                    return workflow_config['stages']
                else:
                    print(f"Warning: Unexpected format in workflow file: {workflow_file}")
                    return None
            except Exception as e:
                print(f"Error loading workflow file {workflow_file}: {e}")
                return None
        
        print(f"Warning: Workflow file not found for {workflow_name}")
        return None
    
    async def execute_workflow(self, workflow_name: str, input_data: str) -> Dict[str, Any]:
        """Execute a workflow with role-specific configurations.
        
        Args:
            workflow_name: Name of the workflow or path to workflow file
            input_data: Input data for the workflow
            
        Returns:
            Dictionary of task results
        """
        # Load the workflow stages
        workflow_stages = self._load_workflow(workflow_name)
        if not workflow_stages:
            raise ValueError(f"No workflow configuration found for {workflow_name}")
        
        # Store workflow config for access in other methods
        self.current_workflow_config = workflow_stages
        
        # Initialize results dictionary
        results = {}
        current_input = input_data
        
        # Execute each stage in the workflow
        for stage in workflow_stages:
            task_name = stage.get("name")
            task_type = stage.get("type", "standard")
            
            print(f"\n=== Executing task: {task_name} (Type: {task_type}) ===")
            
            if task_type == "collaborative":
                # Initialize participants array
                participants_config = []
                
                # Process each participant
                for participant in stage.get("participants", []):
                    role_name = participant.get("role")
                    
                    # Get explicit model override if specified in workflow
                    model_override = participant.get("primary_model")
                    
                    # Load the complete role configuration from its file
                    role_config = self.config_manager.get_role(role_name)
                    
                    if not role_config:
                        print(f"Warning: No configuration found for role {role_name}")
                        continue
                    
                    # Create enriched participant config
                    participant_config = {
                        "role": role_name,
                        "model": model_override or role_config.get("model"),
                        "backup_models": role_config.get("backup_models", []),
                        "system_prompt": role_config.get("system_prompt")
                    }
                    
                    participants_config.append(participant_config)
                
                if not participants_config:
                    print(f"Error: No valid participants found for task {task_name}")
                    results[task_name] = f"Error: No valid participants for task {task_name}"
                    continue
                
                # Execute collaborative conversation
                print(f"Starting collaborative conversation on: {task_name}")
                print(f"Participants: {', '.join([p['role'] for p in participants_config])}")
                
                success, result = await self.conversation.start_conversation(
                    topic=task_name,
                    initial_prompt=current_input,
                    participants=participants_config
                )
                
                if not success:
                    print(f"Failed to execute collaborative task: {task_name}")
                    results[task_name] = f"Error: Failed to execute task {task_name}"
                    continue
            else:
                # For standard tasks
                print(f"Warning: Standard tasks not implemented in the enhanced orchestrator")
                results[task_name] = "Standard tasks not implemented"
                continue
            
            # Store result
            results[task_name] = result
            
            # Use this result as input for the next task
            current_input = result
            
            # Validate result if applicable
            validation_config = stage.get("validation")
            if validation_config and self.validator:
                is_valid, validation_message = await self.validator.validate(
                    result,
                    task_name,
                    validation_config
                )
                
                if not is_valid:
                    print(f"Validation failed for task {task_name}: {validation_message}")
                    results[f"{task_name}_validation"] = validation_message
        
        print(f"\n=== Workflow {workflow_name} completed ===")
        return results
