import asyncio
import json
import os
import yaml
from typing import Dict, List, Tuple, Any, Optional
from .collaborative_conversation import CollaborativeConversation
# Import DynamicConfigManager and other components from the parent directory
from config_manager import DynamicConfigManager, RoleManager, ModelRegistry
from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_memory import EnhancedMemorySystem
from validators import ValidationSystem

class CollaborativeTaskOrchestrator:
    """Orchestrates tasks using a collaborative conversation between multiple expert models.
    
    This orchestrator extends the dynamic task orchestrator by enabling models to interact
    with each other in a conversation-based workflow, where they can discuss requirements,
    design solutions, plan implementation, and review code together.
    """
    
    def __init__(self, config_path: str):
        """Initialize the collaborative task orchestrator.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        
        # Initialize the dynamic configuration manager
        self.config_manager = DynamicConfigManager(config_path)
        
        # Defer initialization of components requiring config until initialize() is called
        self.adapter = None
        self.memory = None
        self.validator = None
        self.conversation = None
        
        # Flag to enable/disable validation
        self.validation_enabled = True
        
        # Task queue
        self.task_queue = asyncio.Queue()
        
    async def initialize(self) -> None:
        """Initialize the orchestrator with all components."""
        await self.config_manager.initialize()
        
        # Now that config is loaded, initialize components
        # Get the full config to pass to the adapter instead of just the OPENROUTER_CONFIG section
        full_config = self.config_manager.config
        # Print the OpenRouter config for debugging
        openrouter_cfg = full_config.get("OPENROUTER_CONFIG", {})
        print("OpenRouter Config:", json.dumps(openrouter_cfg, indent=2))
        # Pass the full config to the adapter so it can access all necessary sections
        self.adapter = EnhancedOpenRouterAdapter(full_config)
        
        memory_config = self.config_manager.get_config_section("MEMORY_SYSTEM") or {}
        self.memory = EnhancedMemorySystem(memory_config)
        
        validator_config = self.config_manager.get_config_section("VALIDATORS") or {}
        self.validator = ValidationSystem(validator_config)
        
        conversation_config = self.config_manager.get_config_section("COLLABORATIVE_CONVERSATION") or {}
        self.conversation = CollaborativeConversation(
            conversation_config,
            self.adapter,
            self.memory
        )
    
    async def execute_workflow(self, workflow_name: str, input_data: str) -> Dict[str, Any]:
        """Execute a complete workflow using collaborative conversations between models.
        
        Args:
            workflow_name: Name of the workflow to execute or path to workflow file
            input_data: Input data for the workflow
            
        Returns:
             Dictionary containing results of each task in the workflow
        """
        # Load workflow configuration using the config manager
        workflow_config = self.config_manager.get_workflow_stages(workflow_name)

        if not workflow_config:
            # Try loading standard/default if specific one isn't found
            print(f"Warning: Workflow '{workflow_name}' not found. Trying a default workflow name.")
            # Use a default workflow name (e.g., 'standard_collaborative' or just 'collaborative')
            default_workflow_name = "collaborative" # Adjust if your default has a different name
            workflow_config = self.config_manager.get_workflow_stages(default_workflow_name)
            if not workflow_config:
                 raise ValueError(f"No workflow configuration could be found for '{workflow_name}' or the default '{default_workflow_name}'.")
        
        print(f"Executing collaborative workflow: {workflow_name}")
        
        # Initialize results dictionary
        results = {}
        current_input = input_data

        # Store the loaded workflow config for access in other methods
        self.current_workflow_config = workflow_config
        
        # Get managers once
        role_manager = self.config_manager.get_role_manager()
        model_registry = self.config_manager.get_model_registry()

        # Execute each task in the workflow using collaborative conversations
        for task_config in workflow_config:
            task_name = task_config.get("name")
            task_type = task_config.get("type", "standard")
            
            print(f"\n=== Executing task: {task_name} (Type: {task_type}) ===")
            
            if task_type == "collaborative":
                # Participants are just role names from the workflow file now
                participant_roles_config = task_config.get("participants", [])
                if not participant_roles_config:
                    print(f"Warning: No participants defined for collaborative task '{task_name}' in workflow config.")
                    results[task_name] = f"Error: No participants defined for task {task_name}"
                    continue # Skip this task if no participants are defined

                # Enrich participant data with details from config.yml
                enriched_participants = []
                for participant_cfg in participant_roles_config:
                    role_name = participant_cfg.get("role")
                    if not role_name:
                        print(f"Warning: Participant config missing 'role' in task '{task_name}'. Skipping.")
                        continue
                    
                    role_info = role_manager.get_role(role_name)
                    if not role_info:
                        print(f"Warning: Role '{role_name}' not found in config.yml for task '{task_name}'. Using defaults.")
                        role_info = {}

                    # Determine models based on task name using the model registry
                    # Role preferences from config.yml might influence future model selection logic, but currently, get_best_model_for_task primarily uses task_name.
                    primary_model, backup_model = model_registry.get_best_model_for_task(
                        task_name, 
                        free_only=True # Assuming we prioritize free models for collaboration
                    )
                    # Ensure backup_models_list is always a list, even if only one backup model is returned
                    backup_models_list = [backup_model]

                    system_prompt = role_info.get("system_prompt", f"You are an AI assistant playing the role of {role_info.get('name', role_name)} for the task: {task_name}.")

                    enriched_participants.append({
                        "role": role_name,
                        "model": primary_model,
                        "backup_models": backup_models_list, # Ensure this is a list
                        "system_prompt": system_prompt
                    })

                if not enriched_participants:
                    print(f"Error: Could not prepare any valid participants for task '{task_name}'.")
                    results[task_name] = f"Error: No valid participants for task {task_name}"
                    continue

                # Execute collaborative conversation for this task
                success, result = await self.conversation.start_conversation(
                    topic=task_name,
                    initial_prompt=current_input,
                    participants=enriched_participants # Pass enriched list
                )
                
                if not success:
                    print(f"Failed to execute collaborative task: {task_name}")
                    results[task_name] = f"Error: Failed to execute task {task_name}"
                    continue
                
            else:
                # For standard tasks, use the regular task execution
                role_name = task_config.get("role", "default") # Get role from task config or use default
                # Pass the full task_config which might contain model overrides etc.
                success, result = await self._execute_standard_task(task_name, role_name, current_input, task_config)

                if not success:
                    print(f"Failed to execute standard task: {task_name}")
                    results[task_name] = f"Error: Failed to execute task {task_name}"
                    continue
            
            # Store result
            results[task_name] = result
            
            # Use this result as input for the next task
            current_input = result
            
            # Validate result if validation is enabled
            if self.validation_enabled:
                # Validation config might be part of task_config or global
                validation_config = task_config.get("validation", self.validator.config)
                is_valid, validation_message = await self.validator.validate(
                    result,
                    task_name, 
                    validation_config
                )
                
                if not is_valid:
                    print(f"Validation failed for task {task_name}: {validation_message}")
                    # Store validation result
                    results[f"{task_name}_validation"] = validation_message
        
        print(f"\n=== Workflow {workflow_name} completed ===")
        return results

    # Removed _get_task_participants as it's now handled inline

    async def _execute_standard_task(self, 
                                   task_name: str, 
                                   role_name: str, 
                                   input_data: str, 
                                   task_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute a standard, non-collaborative task using a single model.
        
        Args:
            task_name: Name of the task
            role_name: Name of the role to perform the task
            input_data: Input data for the task
            task_config: Configuration specific to this task instance from the workflow
            
        Returns:
            Tuple of (success, result)
        """
        try:
            # Get managers from the config manager
            role_manager = self.config_manager.get_role_manager()
            model_registry = self.config_manager.get_model_registry()
            
            role_info = role_manager.get_role(role_name)
            if not role_info:
                print(f"Warning: Role '{role_name}' not found for task '{task_name}'. Using defaults.")
                role_info = {}
            
            # Determine models - allow overrides from task_config
            primary_model_override = task_config.get("primary_model")
            backup_model_override = task_config.get("backup_model")
            
            primary_model, backup_model = model_registry.get_best_model_for_task(
                task_name,
                primary_override=primary_model_override,
                backup_override=backup_model_override
            )
            
            # Get system prompt from role, allow override from task_config
            system_prompt = task_config.get("system_prompt", role_info.get("system_prompt", f"You are an AI assistant tasked with {task_name}."))
            
            # Get model parameters from role or task_config, or use defaults
            model_prefs = role_info.get("model_preferences", {})
            temperature = task_config.get("temperature", model_prefs.get("temperature", 0.7))
            # Max tokens/context window might come from model registry, role, task_config or defaults
            max_tokens = task_config.get("max_tokens", model_prefs.get("max_tokens", 4000))
            context_window = task_config.get("context_window", model_prefs.get("context_window", 8000))
            
            # Construct a task_config-like dictionary for the adapter
            adapter_task_config = {
                "primary": {
                    "model": primary_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "context_window": context_window,
                    "system_prompt": system_prompt # Pass the potentially overridden prompt
                },
                "backup": {
                    "model": backup_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "context_window": context_window,
                    "system_prompt": system_prompt
                },
                # Get validation config from task_config, role, or global config
                "validation": task_config.get("validation", role_info.get("output_format", {}).get("validation", self.validator.config))
            }
            
            # Get context from memory system
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
                
            # Enhance system prompt if needed (e.g., add validation instructions)
            enhanced_system_prompt = self._enhance_system_prompt(system_prompt, task_name, adapter_task_config["validation"])

            # Prepare messages
            messages = [
                {"role": "system", "content": enhanced_system_prompt},
                {"role": "user", "content": full_input}
            ]
            
            # Generate completion using the adapter
            response = await self.adapter.generate_completion(
                messages=messages,
                task_config=adapter_task_config # Pass the constructed config
            )
            
            result = response["choices"][0]["message"]["content"]
            
            # Add to memory using add_document method
            metadata = {"task": task_name, "source": "standard_task"}
            self.memory.add_document(f"Input: {full_input}\n\nOutput: {result}", metadata)
            
            return True, result
            
        except Exception as e:
            print(f"Error executing standard task {task_name} with role {role_name}: {str(e)}")
            # Optionally, try backup model here if adapter doesn't handle it
            return False, str(e)
    
    def _enhance_system_prompt(self, system_prompt: str, task_name: str, validation_config: Dict[str, Any]) -> str:
        """Enhance the system prompt with task-specific instructions.
        
        Args:
            system_prompt: The base system prompt
            task_name: The name of the task
            validation_config: The validation configuration
            
        Returns:
            The enhanced system prompt
        """
        if task_name in ["requirements_analysis", "system_design", "implementation_planning", "code_review"]:
            format_instructions = "\n\nIMPORTANT: Your response MUST include ALL of these section headers:\n"
            for section in validation_config.get("required_sections", []):
                format_instructions += f"- {section}\n"
            system_prompt = system_prompt + format_instructions
        
        elif task_name == "code_generation":
            code_instructions = "\n\nIMPORTANT: Your response MUST include actual code (not just descriptions). Use markdown code blocks with language tags. Include function definitions, class declarations, and import statements."
            system_prompt = system_prompt + code_instructions
        
        return system_prompt
    
    def _get_validation_config(self, task_name: str) -> Dict[str, Any]:
        """Get the validation configuration for a specific task.
        
        Args:
            task_name: The name of the task
            
        Returns:
            The validation configuration
        """
        task_config = self.config.get("TASKS", {}).get(task_name, {})
        return task_config.get("validation", {})

# Example usage (if run directly)
async def main():
    # Assume config.yml and workflows/collaborative_workflow.yml exist
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yml')
    orchestrator = CollaborativeTaskOrchestrator(config_path)
    await orchestrator.initialize()
    
    # Example input
    initial_requirements = "Create a simple web application for managing tasks."
    
    # Execute the collaborative workflow defined in the workflow file
    # The workflow name 'collaborative' should match the key in config.yml or the filename
    results = await orchestrator.execute_workflow("collaborative", initial_requirements)
    
    print("\n=== Final Workflow Results ===")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())