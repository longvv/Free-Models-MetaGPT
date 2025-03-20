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

from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_memory import EnhancedMemorySystem
from validators import ValidationSystem
from config_manager import DynamicConfigManager

class DynamicTaskOrchestrator:
    """Enhanced orchestrator with dynamic configuration for tasks across multiple models."""
    
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
    
    async def _execute_task(self, 
                          task_name: str, 
                          role_name: str,
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
        task_config = self.config_manager.get_task_config(task_name, role_name)
        if not task_config:
            return False, f"Task not found in configuration: {task_name}"
            
        # Get primary configs
        primary_config = task_config.get("primary", {})
        primary_model = primary_config.get("model")
        
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
            
        system_prompt = primary_config.get("system_prompt", "")
        
        # Enhanced prompting for specific model types
        if "deepseek" in primary_model:
            # Enhance system prompt for DeepSeek model
            system_prompt = f"{system_prompt}\n\nPlease be thorough and detailed in your analysis."
        elif "olympiccoder" in primary_model:
            # Enhance system prompt for code-specific model
            system_prompt = f"{system_prompt}\n\nFocus on writing clean, efficient, and well-documented code."
        elif "gemma" in primary_model:
            # Enhance system prompt for Gemma
            system_prompt = f"{system_prompt}\n\nProvide a thorough, well-structured response."
            
        # Create messages array
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_input}
        ]
        
        # Generate completion
        try:
            response = await self.adapter.generate_completion(
                messages=messages,
                task_config=task_config
            )
            
            result = response["choices"][0]["message"]["content"]
            
            # Validate result if validation is enabled
            if self.validation_enabled:
                validation_config = task_config.get("validation", {})
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
            else:
                print(f"Validation skipped for task: {task_name}")
                
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
            role_name = task_info.get("role", task_name)  # Use task name as role if not specified
            input_key = task_info["input"]
            output_key = task_info["output"]
            
            print(f"Processing task: {task_name} with role: {role_name}")
            print(f"  Input key: {input_key}")
            print(f"  Available keys: {list(results.keys())}")
            
            # Get input from results
            if input_key not in results:
                print(f"Error: Input {input_key} not found in results")
                self.task_queue.task_done()
                continue
                
            input_data = results[input_key]
            
            # Execute task
            success, output = await self._execute_task(task_name, role_name, input_data)
            
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
                    "role": role_name,
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
                      workflow_name: str = "standard", 
                      workspace_dir: str = "./workspace") -> Dict[str, str]:
        """Run the workflow with dynamic configuration.
        
        Args:
            input_idea: Initial idea/requirements from user
            workflow_name: Name of the workflow to use
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
        
        # Get workflow stages from dynamic configuration
        workflow_stages = self.config_manager.get_workflow_stages(workflow_name)
        
        # Queue tasks from workflow
        for stage in workflow_stages:
            await self.task_queue.put({
                "task": stage.get("task"),
                "role": stage.get("role", stage.get("task")),  # Use task as role if not specified
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
                                   workflow_name: str = "standard",
                                   workspace_dir: str = "./workspace") -> Dict[str, str]:
        """Run workflow with parallel task execution when possible.
        
        Args:
            input_idea: Initial idea/requirements from user
            workflow_name: Name of the workflow to use
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
        
        # Get workflow stages from dynamic configuration
        workflow_stages = self.config_manager.get_workflow_stages(workflow_name)
        
        # Build dependency graph
        for stage in workflow_stages:
            task_name = f"{stage.get('task')}:{stage.get('output')}"
            input_key = stage.get("input")
            
            task_configs[task_name] = {
                "task": stage.get("task"),
                "role": stage.get("role", stage.get("task")),  # Use task as role if not specified
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
            pending_task_names = []
            for task_name in current_tasks:
                config = task_configs[task_name]
                task_coroutine = self._execute_task(
                    config["task"], 
                    config["role"], 
                    results[config["input"]]
                )
                pending_tasks.append(task_coroutine)
                pending_task_names.append(task_name)
                
            if pending_tasks:
                task_results = await asyncio.gather(*pending_tasks)
                
                # Process results
                for i, (success, output) in enumerate(task_results):
                    task_name = pending_task_names[i]
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
                                "role": config["role"],
                                "source": config["output"],
                                "timestamp": os.path.getmtime(workspace_path)
                            }
                        )
                        
                        # Save output to file
                        output_file = workspace_path / f"{config['output']}.txt"
                        with open(output_file, 'w') as f:
                            f.write(output)
                            
                        print(f"Completed task: {config['task']} with role: {config['role']}")
                        
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