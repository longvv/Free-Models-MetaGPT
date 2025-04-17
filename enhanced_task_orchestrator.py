# enhanced_task_orchestrator.py
# Enhanced task orchestrator with validation and async processing

import os
import yaml
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import jsonschema

from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_memory import EnhancedMemorySystem
from validators import ValidationSystem
# Import DynamicConfigManager
from config_manager import DynamicConfigManager

class EnhancedTaskOrchestrator:
    """Enhanced orchestrator for tasks across multiple free models in MetaGPT."""
    
    def __init__(self, config_path: str):
        """Initialize the enhanced task orchestrator.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        # Initialize the dynamic configuration manager
        self.config_manager = DynamicConfigManager(config_path)
        # Config is loaded within config_manager now, access sections via methods
        # self.config = self._load_config() # Deprecated
        
        # Initialize OpenRouter adapter
        # Pass the config manager or specific sections if needed
        openrouter_cfg = self.config_manager.get_config_section("OPENROUTER_CONFIG") or {}
        # Assuming EnhancedOpenRouterAdapter needs the registry too
        self.adapter = EnhancedOpenRouterAdapter(openrouter_cfg, self.config_manager.get_model_registry())
        
        # Initialize memory system
        memory_config = self.config_manager.get_config_section("MEMORY_SYSTEM") or {}
        self.memory = EnhancedMemorySystem(memory_config)
        
        # Initialize validation system
        validator_config = self.config_manager.get_config_section("VALIDATORS") or {}
        self.validator = ValidationSystem(validator_config)
        
        # Task queue
        self.task_queue = asyncio.Queue()
        
    # _load_config is no longer needed as DynamicConfigManager handles it
    # def _load_config(self) -> Dict[str, Any]:
    #     """Load configuration from YAML file.
    #     
    #     Returns:
    #         Configuration dictionary
    #     """
    #     if not os.path.exists(self.config_path):
    #         raise FileNotFoundError(f"Config file not found: {self.config_path}")
    #         
    #     with open(self.config_path, 'r') as f:
    #         return yaml.safe_load(f)
            
    async def initialize(self) -> None:
        """Initialize the orchestrator by loading config through the manager."""
        await self.config_manager.initialize()

    async def _execute_task(self, 
                          task_name: str, 
                          role_name: str, # Added role_name for consistency
                          input_data: str) -> Tuple[bool, str]:
        """Execute a single task using the appropriate model.
        
        Args:
            task_name: Name of the task to execute
            role_name: Name of the role to use
            input_data: Input data for the task
            
        Returns:
            Tuple of (success, result)
        """
        # Get task configuration using dynamic config manager
        # Note: Original enhanced_task_orchestrator didn't use get_task_config
        # We adapt it to use role and model info from the manager
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
        # This mimics the structure expected by adapter.generate_completion
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
            full_input = f"Previous context:\\n\\n{context}\\n\\n===\\n\\nCurrent task:\\n\\n{input_data}"
        else:
            full_input = input_data
            
        # System prompt is already part of task_config_for_adapter
        # system_prompt = primary_config.get("system_prompt", "") # Redundant
        
        # Enhanced prompting for specific model types (can be kept or moved to config)
        if "deepseek" in primary_model:
            system_prompt = f"{system_prompt}\\n\\nPlease be thorough and detailed in your analysis."
        elif "olympiccoder" in primary_model:
            system_prompt = f"{system_prompt}\\n\\nFocus on writing clean, efficient, and well-documented code."
        elif "phi-3" in primary_model:
            system_prompt = f"{system_prompt}\\n\\nUtilize your large context window to maintain coherence across the entire task."
            
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
            
            # Validate result
            validation_config = task_config_for_adapter.get("validation", {})
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
                            task_config=task_config
                        )
                        
                        result = response["choices"][0]["message"]["content"]
                        
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
                        # Proceed anyway with the last result
                
            return True, result
            
        except Exception as e:
            print(f"Error executing task {task_name}: {str(e)}")
            return False, str(e)
            
    async def _process_task_queue(self, workspace_path: Path, initial_results: Dict[str, str]) -> Dict[str, str]:
        """Process tasks from the queue.
        
        Args:
            workspace_path: Path to workspace directory
            initial_results: Initial results dictionary with user input
            
        Returns:
            Dictionary of results
        """
        # Initialize with the provided initial results
        results = dict(initial_results)
        
        print("Initial input:", results.keys())
        
        while not self.task_queue.empty():
            # Get next task
            task_info = await self.task_queue.get()
            task_name = task_info["task"]
            input_key = task_info["input"]
            output_key = task_info["output"]
            
            print(f"Processing task: {task_name}")
            print(f"  Input key: {input_key}")
            print(f"  Available keys: {list(results.keys())}")
            
            # Get input from results
            if input_key not in results:
                print(f"Error: Input {input_key} not found in results")
                self.task_queue.task_done()
                continue
                
            input_data = results[input_key]
            
            # Execute task
            success, output = await self._execute_task(task_name, input_data)
            
            if not success:
                print(f"Error executing task {task_name}: {output}")
                self.task_queue.task_done()
                continue
                
            # Store result
            results[output_key] = output
            
            # Add to memory
            self.memory.add_document(
                document=output,
                metadata={
                    "task": task_name,
                    "source": output_key,
                    "timestamp": os.path.getmtime(workspace_path)
                }
            )
            
            # Save output to file
            output_file = workspace_path / f"{output_key}.txt"
            with open(output_file, 'w') as f:
                f.write(output)
                
            print(f"Completed task: {task_name}")
            self.task_queue.task_done()
            
        return results
    
    async def run_workflow(self, 
                      input_idea: str, 
                      workspace_dir: str = "./workspace") -> Dict[str, str]:
        """Run the entire workflow from start to finish with enhanced processing.
        
        Args:
            input_idea: Initial idea/requirements from user
            workspace_dir: Directory to save outputs
            
        Returns:
            Dictionary of workflow outputs
        """
        # Create workspace directory if it doesn't exist
        workspace_path = Path(workspace_dir)
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize results
        results = {"user_idea": input_idea}
        
        # Save the input idea to a file
        input_file = workspace_path / "user_idea.txt"
        with open(input_file, 'w') as f:
            f.write(input_idea)
        
        # Add initial idea to memory
        self.memory.add_document(
            document=input_idea,
            metadata={
                "task": "user_input",
                "source": "user_idea",
                "timestamp": os.path.getmtime(workspace_path)
            }
        )
        
        # Queue all tasks
        workflow_stages = self.config.get("WORKFLOW_STAGES", [])
        for stage in workflow_stages:
            await self.task_queue.put({
                "task": stage.get("task"),
                "input": stage.get("input"),
                "output": stage.get("output")
            })
            
        # Process tasks with initial results
        results = await self._process_task_queue(workspace_path, results)
        
        # Create summary file
        summary_file = workspace_path / "project_summary.md"
        with open(summary_file, 'w') as f:
            f.write("# Project Summary\n\n")
            f.write(f"## Original Idea\n\n{input_idea}\n\n")
            
            for stage in workflow_stages:
                output_key = stage.get("output")
                if output_key in results:
                    title = output_key.replace("_", " ").title()
                    f.write(f"## {title}\n\n{results[output_key]}\n\n")
                    
        return results
    
    async def run_parallel_workflow(self,
                                   input_idea: str,
                                   workspace_dir: str = "./workspace") -> Dict[str, str]:
        """Run workflow with parallel task execution when possible.
        
        Args:
            input_idea: Initial idea/requirements from user
            workspace_dir: Directory to save outputs
            
        Returns:
            Dictionary of workflow outputs
        """
        # Create workspace directory if it doesn't exist
        workspace_path = Path(workspace_dir)
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize results and dependency graph
        results = {"user_idea": input_idea}
        task_dependencies = {}
        tasks_ready = set()
        tasks_completed = set()
        task_configs = {}
        
        # Add initial idea to memory
        self.memory.add_document(
            document=input_idea,
            metadata={
                "task": "user_input",
                "source": "user_idea",
                "timestamp": os.path.getmtime(workspace_path)
            }
        )
        
        # Build dependency graph
        workflow_stages = self.config.get("WORKFLOW_STAGES", [])
        for stage in workflow_stages:
            task_name = f"{stage.get('task')}:{stage.get('output')}"
            input_key = stage.get("input")
            
            task_configs[task_name] = {
                "task": stage.get("task"),
                "input": input_key,
                "output": stage.get("output")
            }
            
            # Track dependencies
            if input_key == "user_idea":
                # No dependencies, ready immediately
                tasks_ready.add(task_name)
            else:
                # Find which task produces this input
                for other_stage in workflow_stages:
                    if other_stage.get("output") == input_key:
                        other_task = f"{other_stage.get('task')}:{other_stage.get('output')}"
                        if task_name not in task_dependencies:
                            task_dependencies[task_name] = set()
                        task_dependencies[task_name].add(other_task)
                
        # Process tasks until all are completed
        while tasks_ready or any(task not in tasks_completed for task in task_dependencies):
            # Get all ready tasks
            current_tasks = list(tasks_ready)
            tasks_ready.clear()
            
            if not current_tasks:
                # No tasks ready, check for deadlock
                waiting_tasks = set(task_dependencies.keys()) - tasks_completed
                if waiting_tasks:
                    print(f"Warning: Workflow deadlock detected. Waiting tasks: {waiting_tasks}")
                    break
                else:
                    # All done
                    break
                    
            # Run all ready tasks in parallel
            pending_tasks = []
            for task_name in current_tasks:
                config = task_configs[task_name]
                task_coroutine = self._execute_task(config["task"], results[config["input"]])
                pending_tasks.append(task_coroutine)
                
            if pending_tasks:
                task_results = await asyncio.gather(*pending_tasks)
                
                # Process results
                for i, (success, output) in enumerate(task_results):
                    task_name = current_tasks[i]
                    config = task_configs[task_name]
                    
                    if not success:
                        print(f"Error executing task {config['task']}: {output}")
                    else:
                        # Store result
                        results[config["output"]] = output
                        
                        # Add to memory
                        self.memory.add_document(
                            document=output,
                            metadata={
                                "task": config["task"],
                                "source": config["output"],
                                "timestamp": os.path.getmtime(workspace_path)
                            }
                        )
                        
                        # Save output to file
                        output_file = workspace_path / f"{config['output']}.txt"
                        with open(output_file, 'w') as f:
                            f.write(output)
                            
                        print(f"Completed task: {config['task']}")
                        
                    # Mark task as completed
                    tasks_completed.add(task_name)
                    
                    # Check if any waiting tasks are now ready
                    for waiting_task, dependencies in task_dependencies.items():
                        if waiting_task not in tasks_completed and dependencies.issubset(tasks_completed):
                            tasks_ready.add(waiting_task)
                            
        # Create summary file
        summary_file = workspace_path / "project_summary.md"
        with open(summary_file, 'w') as f:
            f.write("# Project Summary\n\n")
            f.write(f"## Original Idea\n\n{input_idea}\n\n")
            
            for stage in workflow_stages:
                output_key = stage.get("output")
                if output_key in results:
                    title = output_key.replace("_", " ").title()
                    f.write(f"## {title}\n\n{results[output_key]}\n\n")
                    
        return results
