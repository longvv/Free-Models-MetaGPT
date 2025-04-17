#!/usr/bin/env python
# enhanced_task_orchestrator_dynamic.py
# Enhanced task orchestrator with dynamic configuration support

import os
import yaml
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import jsonschema
import re

from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_memory import EnhancedMemorySystem
from validators import ValidationSystem
# Import DynamicConfigManager from the correct location (assuming it's in the parent dir)
from ..config_manager import DynamicConfigManager

class DynamicTaskOrchestrator:
    """Enhanced orchestrator with dynamic configuration for tasks across multiple models."""
    
    def _init_validator(self):
        """Initialize the validation system with the enhanced validator."""
        validator_config = self.config.get("VALIDATORS", {})
        
        # Import the enhanced validator module
        import importlib
        try:
            validator_module_name = validator_config.get("module", "enhanced_validators")
            validator_module = importlib.import_module(validator_module_name)
            self.validator = validator_module.ValidationSystem(validator_config)
            print(f"Using enhanced validation system from {validator_module_name}")
        except ImportError:
            # Fall back to original validator if enhanced not found
            from validators import ValidationSystem
            self.validator = ValidationSystem(validator_config)
            print("Using standard validation system")
    
    def __init__(self, config_path: str):
        """Initialize the dynamic task orchestrator.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        
        # Initialize the dynamic configuration manager
        self.config_manager = DynamicConfigManager(config_path)
        
        # Get base configuration
        self.config = self.config_manager.config
        
        # Initialize OpenRouter adapter
        self.adapter = EnhancedOpenRouterAdapter(self.config)
        
        # Initialize memory system
        memory_config = self.config.get("MEMORY_SYSTEM", {})
        self.memory = EnhancedMemorySystem(memory_config)
        
        # Initialize validation system
        validator_config = self.config.get("VALIDATORS", {})
        self.validator = ValidationSystem(validator_config)
        
        # Flag to enable/disable validation
        self.validation_enabled = True
        
        # Task queue
        self.task_queue = asyncio.Queue()
        
    async def initialize(self) -> None:
        """Initialize the orchestrator with all components."""
        await self.config_manager.initialize()
    
    # Add these methods to your DynamicTaskOrchestrator class

    async def _execute_task(self, 
                        task_name: str, 
                        role_name: str,
                        input_data: str) -> Tuple[bool, str]:
        """Execute a single task using the appropriate model with enhanced validation.
        
        Args:
            task_name: Name of the task to execute
            role_name: Name of the role to use
            input_data: Input data for the task
            
        Returns:
            Tuple of (success, result)
        """
        # Get managers from the config manager
        role_manager = self.config_manager.get_role_manager()
        model_registry = self.config_manager.get_model_registry()
        
        role_info = role_manager.get_role(role_name)
        if not role_info:
            print(f"Warning: Role '{role_name}' not found for task '{task_name}'. Using defaults.")
            role_info = {}
        
        # Determine models
        primary_model, backup_model = model_registry.get_best_model_for_task(task_name)
        
        # Get system prompt from role
        system_prompt = role_info.get("system_prompt", f"You are an AI assistant tasked with {task_name}.")
        
        # Get model parameters from role or use defaults
        model_prefs = role_info.get("model_preferences", {})
        temperature = model_prefs.get("temperature", 0.7)
        # Max tokens/context window might come from model registry or defaults
        # For simplicity, using fixed values here, but could be dynamic
        max_tokens = 4000 
        context_window = 8000
        
        # Construct a task_config-like dictionary for the adapter
        task_config_for_adapter = {
            "primary": {
                "model": primary_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "context_window": context_window,
                "system_prompt": system_prompt # Pass the base prompt here
            },
            "backup": {
                "model": backup_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "context_window": context_window,
                "system_prompt": system_prompt
            },
            # Get validation config from role or global config
            "validation": role_info.get("output_format", {}).get("validation", self.validator.config)
        }
          
        # Get context from memory system - pass model name for context optimization
        context = self.memory.get_relevant_context(
            input_data, 
            task=task_name,
            model=primary_model
        )
          
        # Prepare input with context
        if context:
            full_input = f"Previous context:\n\n{context}\n\n===\n\nCurrent task:\n\n{input_data}"
        else:
            full_input = input_data
              
        # Enhance system prompts based on task (using the base prompt from role_info)
        # Add validation instructions to system prompt
        validation_config = task_config_for_adapter.get("validation", {})
          
        if task_name == "requirements_analysis":
            format_instructions = "\n\nIMPORTANT: Your response MUST include ALL of these section headers:\n"
            for section in validation_config.get("required_sections", []):
                format_instructions += f"- {section}\n"
            system_prompt = system_prompt + format_instructions
        
        elif task_name == "system_design":
            format_instructions = "\n\nIMPORTANT: Your response MUST include ALL of these section headers:\n"
            for section in validation_config.get("required_sections", []):
                format_instructions += f"- {section}\n"
            system_prompt = system_prompt + format_instructions
        
        elif task_name == "implementation_planning":
            format_instructions = "\n\nIMPORTANT: Your response MUST include ALL of these section headers:\n"
            for section in validation_config.get("required_sections", []):
                format_instructions += f"- {section}\n"
            system_prompt = system_prompt + format_instructions
        
        elif task_name == "code_generation":
            code_instructions = "\n\nIMPORTANT: Your response MUST include actual code (not just descriptions). Use markdown code blocks with language tags. Include function definitions, class declarations, and import statements."
            system_prompt = system_prompt + code_instructions
        
        elif task_name == "code_review":
            format_instructions = "\n\nIMPORTANT: Your response MUST include ALL of these section headers:\n"
            for section in validation_config.get("required_sections", []):
                format_instructions += f"- {section}\n"
            system_prompt = system_prompt + format_instructions
        
        # Create messages array using the potentially enhanced system_prompt
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_input}
        ]
          
        # Generate completion
        try:
            response = await self.adapter.generate_completion(
                messages=messages,
                task_config=task_config_for_adapter # Pass the constructed config
            )
              
            result = response["choices"][0]["message"]["content"]
             
            # Apply post-processing to the result if needed
            result = self._post_process_result(result, task_name, validation_config)
            
            # Validate result if validation is enabled
            if self.validation_enabled:
                is_valid, validation_message = await self.validator.validate(
                    result, 
                    task_name, 
                    validation_config
                )
                
                if not is_valid:
                    # If validation fails and retry is enabled
                    if validation_config.get("retry_on_failure", True):
                        max_retries = validation_config.get("max_retries", 3)
                        
                        for retry in range(max_retries):
                            # Update message with validation feedback
                            retry_message = f"{full_input}\n\nThe previous response failed validation: {validation_message}\n\nPlease fix the issues and try again."
                            
                            messages = [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": retry_message}
                            ]
                            
                            # Generate new completion
                            print(f"Retry {retry+1}/{max_retries} for {task_name} due to validation failure")
                            response = await self.adapter.generate_completion(
                                messages=messages,
                                task_config=task_config_for_adapter # Use the constructed config
                            )
                            
                            result = response["choices"][0]["message"]["content"]
                            
                            # Apply post-processing to the retry result
                            result = self._post_process_result(result, task_name, validation_config)
                            
                            # Validate again
                            is_valid, validation_message = await self.validator.validate(
                                result, 
                                task_name, 
                                validation_config
                            )
                            
                            if is_valid:
                                print(f"Validation successful after retry {retry+1}")
                                break
                                
                        if not is_valid:
                            print(f"Validation failed after {max_retries} retries: {validation_message}")
                            # Optionally, decide how to handle persistent failure
                            # For now, proceed with the last result but maybe log error
            
            # Add result to memory
            self.memory.add_interaction(task_name, full_input, result)
            
            return True, result
            
        except Exception as e:
            print(f"Error executing task {task_name} with role {role_name}: {str(e)}")
            # Optionally, try backup model here if adapter doesn't handle it
            return False, str(e)

    def _post_process_result(self, result: str, task_name: str, validation_config: Dict[str, Any]) -> str:
        """Apply task-specific post-processing to the model's result."""
        # Example: Ensure code blocks are correctly formatted for code_generation
        if task_name == "code_generation":
            # Simple check to ensure markdown code blocks exist if expected
            if "```" not in result and validation_config.get("required_patterns") and any(p in validation_config["required_patterns"] for p in ["def", "class"]):
                 print(f"Warning: Code generation task '{task_name}' result might be missing markdown code blocks.")
                 # Attempt to wrap if it looks like code but lacks blocks
                 lines = result.strip().split('\n')
                 if len(lines) > 1 and (lines[0].startswith("import") or lines[0].startswith("def") or lines[0].startswith("class")):
                     language = validation_config.get("language", "python") # Get language from config or default
                     result = f"```{language}\n{result.strip()}\n```"
                     print("Attempted to wrap result in markdown code block.")
        
        # Example: Ensure required sections exist for documentation tasks
        required_sections = validation_config.get("required_sections", [])
        if required_sections:
            missing_sections = []
            for section in required_sections:
                # Use regex to find section headers (case-insensitive, allows for minor variations)
                if not re.search(rf"^#+\s*{re.escape(section)}\s*$\n", result, re.MULTILINE | re.IGNORECASE):
                    missing_sections.append(section)
            if missing_sections:
                print(f"Warning: Task '{task_name}' result might be missing sections: {', '.join(missing_sections)}")
                # Optionally, attempt to add missing section headers if content seems present but lacks header

        return result

    async def _process_task_queue(self, workspace_path: Path, initial_results: Dict[str, str]) -> Dict[str, str]:
        """Process tasks from the queue.
        
        Args:
            workspace_path: Path to workspace directory
            initial_results: Initial results dictionary with user input
            
        Returns:
            Dictionary of results
        """
        results = dict(initial_results)
        
        while not self.task_queue.empty():
            task_info = await self.task_queue.get()
            task_name = task_info["task"]
            input_key = task_info["input"]
            output_key = task_info["output"]
            role_name = task_info.get("role", task_name) # Use task name as role if not specified
            
            print(f"Processing task: {task_name} (Role: {role_name})")
            print(f"  Input key: {input_key}")
            print(f"  Available keys: {list(results.keys())}")
            
            if input_key not in results:
                print(f"Error: Input '{input_key}' not found in results for task '{task_name}'")
                self.task_queue.task_done()
                continue
                
            input_data = results[input_key]
            
            # Execute task
            success, result = await self._execute_task(task_name, role_name, input_data)
            
            if success:
                results[output_key] = result
                # Save intermediate result to workspace
                output_path = workspace_path / f"{output_key}.txt"
                try:
                    with open(output_path, 'w') as f:
                        f.write(result)
                    print(f"Saved result for {task_name} to {output_path}")
                except Exception as e:
                    print(f"Error saving result for {task_name}: {str(e)}")
            else:
                print(f"Task {task_name} failed. Stopping workflow.")
                # Optionally handle failure, e.g., add error message to results
                results[output_key] = f"Error executing task {task_name}: {result}"
                # Clear the queue to stop processing further tasks on failure
                while not self.task_queue.empty():
                    await self.task_queue.get()
                    self.task_queue.task_done()
                break # Exit the processing loop

            self.task_queue.task_done()
            
        return results

    async def execute_workflow(self, 
                             workflow_name: str = "standard", 
                             input_data: str = None, 
                             workspace_dir: str = "./workspace") -> Dict[str, Any]:
        """Execute a complete workflow.
        
        Args:
            workflow_name: Name of the workflow to execute
            input_data: Initial input data for the workflow
            workspace_dir: Directory to save intermediate and final results
            
        Returns:
            Dictionary containing results of each task in the workflow
        """
        # Ensure orchestrator is initialized
        if not self.config_manager.loaded:
            await self.initialize()
            
        # Get workflow stages using dynamic config manager
        workflow_stages = self.config_manager.get_workflow_stages(workflow_name)
        if not workflow_stages:
             # Try loading standard/default if specific one not found
            print(f"Warning: Workflow '{workflow_name}' not found. Trying 'standard' workflow.")
            workflow_stages = self.config_manager.get_workflow_stages("standard")
            if not workflow_stages:
                 raise ValueError(f"No workflow configuration could be found for '{workflow_name}' or 'standard'.")

        print(f"Executing workflow: {workflow_name}")
        
        # Create workspace directory
        workspace_path = Path(workspace_dir)
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Add tasks to queue
        for stage in workflow_stages:
            await self.task_queue.put(stage)
            
        # Prepare initial results
        initial_input_key = workflow_stages[0]["input"]
        initial_results = {initial_input_key: input_data}
        
        # Process task queue
        final_results = await self._process_task_queue(workspace_path, initial_results)
        
        print(f"Workflow {workflow_name} completed.")
        return final_results

    def enable_validation(self, enable: bool = True):
        """Enable or disable result validation."""
        self.validation_enabled = enable
        print(f"Result validation {'enabled' if enable else 'disabled'}.")

# Example usage (if run directly)
async def main():
    # Use the dynamic orchestrator
    orchestrator = DynamicTaskOrchestrator("config.yml")
    await orchestrator.initialize()
    
    # Example: Execute the standard workflow
    user_idea = "Create a simple Python web server using Flask that returns 'Hello, World!' on the root path."
    results = await orchestrator.execute_workflow(
        workflow_name="standard", 
        input_data=user_idea,
        workspace_dir="./dynamic_workspace"
    )
    
    # Print final result (e.g., code review comments)
    final_output_key = orchestrator.config_manager.get_workflow_stages("standard")[-1]["output"]
    print("\n=== Final Workflow Output ===")
    print(results.get(final_output_key, "Workflow did not complete successfully."))

if __name__ == "__main__":
    asyncio.run(main())