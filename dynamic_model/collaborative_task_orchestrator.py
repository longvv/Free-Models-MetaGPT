import asyncio
import json
import os
import yaml
from typing import Dict, List, Tuple, Any, Optional
from .collaborative_conversation import CollaborativeConversation

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
        from .config_manager import DynamicConfigManager
        from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
        from enhanced_memory import EnhancedMemorySystem
        from validators import ValidationSystem
        
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
        
        # Initialize collaborative conversation system
        conversation_config = self.config.get("COLLABORATIVE_CONVERSATION", {})
        self.conversation = CollaborativeConversation(
            conversation_config,
            self.adapter,
            self.memory
        )
        
        # Flag to enable/disable validation
        self.validation_enabled = True
        
        # Task queue
        self.task_queue = asyncio.Queue()
        
    async def initialize(self) -> None:
        """Initialize the orchestrator with all components."""
        await self.config_manager.initialize()
    
    async def execute_workflow(self, workflow_name: str, input_data: str) -> Dict[str, Any]:
        """Execute a complete workflow using collaborative conversations between models.
        
        Args:
            workflow_name: Name of the workflow to execute or path to workflow file
            input_data: Input data for the workflow
            
        Returns:
            Dictionary containing results of each task in the workflow
        """
        # Check if workflow_name is a file path
        if os.path.isfile(workflow_name):
            try:
                with open(workflow_name, 'r') as f:
                    workflow_config = yaml.safe_load(f).get('tasks', [])
                print(f"Loaded workflow configuration from file: {workflow_name}")
            except Exception as e:
                print(f"Warning: Workflow file '{workflow_name}' could not be loaded: {str(e)}, using standard workflow")
                # Get workflow configuration from config manager
                workflow_config = self.config_manager.get_workflow_stages("collaborative")
        else:
            # Get workflow configuration from config manager
            workflow_config = self.config_manager.get_workflow_stages(workflow_name)
            if not workflow_config:
                print(f"Warning: Workflow '{workflow_name}' not found, using standard workflow")
                workflow_config = self.config_manager.get_workflow_stages("collaborative")
        
        if not workflow_config:
            raise ValueError(f"No workflow configuration could be found or loaded")
        
        print(f"Executing collaborative workflow: {workflow_name}")
        
        # Initialize results dictionary
        results = {}
        current_input = input_data
        
        # Execute each task in the workflow using collaborative conversations
        for task_config in workflow_config:
            task_name = task_config.get("name")
            task_type = task_config.get("type", "standard")
            
            print(f"\n=== Executing task: {task_name} (Type: {task_type}) ===")
            
            if task_type == "collaborative":
                # Get participant configurations for this collaborative task
                participants = self._get_task_participants(task_name)
                
                # Execute collaborative conversation for this task
                success, result = await self.conversation.start_conversation(
                    topic=task_name,
                    initial_prompt=current_input,
                    participants=participants
                )
                
                if not success:
                    print(f"Failed to execute collaborative task: {task_name}")
                    results[task_name] = f"Error: Failed to execute task {task_name}"
                    continue
                
            else:
                # For standard tasks, use the regular task execution
                role_name = task_config.get("role", "default")
                success, result = await self._execute_standard_task(task_name, role_name, current_input)
                
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
                validation_config = self._get_validation_config(task_name)
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
    
    def _get_task_participants(self, task_name: str) -> List[Dict[str, Any]]:
        """Get the participant configurations for a collaborative task.
        
        Args:
            task_name: Name of the task
            
        Returns:
            List of participant configurations
        """
        # Get task-specific participant configuration
        task_config = self.config.get("TASKS", {}).get(task_name, {})
        participants = task_config.get("participants", [])
        
        if not participants:
            # Fall back to default participants based on task type
            if task_name == "requirements_analysis":
                participants = [
                    {"role": "Requirements Analyst", "model": "deepseek/deepseek-chat-v3-0324:free", "backup_models": ["meta-llama/llama-4-maverick:free", "google/gemini-2.5-pro-exp-03-25:free"]},
                    {"role": "Domain Expert", "model": "deepseek/deepseek-chat-v3-0324:free", "backup_models": ["meta-llama/llama-4-maverick:free", "google/gemini-2.5-pro-exp-03-25:free"]},
                    {"role": "User Advocate", "model": "deepseek/deepseek-chat-v3-0324:free", "backup_models": ["meta-llama/llama-4-maverick:free", "google/gemini-2.5-pro-exp-03-25:free"]}
                ]
            elif task_name == "system_design":
                participants = [
                    {"role": "System Architect", "model": "google/gemini-2.5-pro-exp-03-25:free", "backup_models": ["meta-llama/llama-4-maverick:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "Security Expert", "model": "google/gemini-2.5-pro-exp-03-25:free", "backup_models": ["meta-llama/llama-4-maverick:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "Performance Engineer", "model": "google/gemini-2.5-pro-exp-03-25:free", "backup_models": ["meta-llama/llama-4-maverick:free", "deepseek/deepseek-chat-v3-0324:free"]}
                ]
            elif task_name == "implementation_planning":
                participants = [
                    {"role": "Technical Lead", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "Developer", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "QA Engineer", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]}
                ]
            elif task_name == "code_generation":
                participants = [
                    {"role": "Senior Developer", "model": "google/gemini-2.5-pro-exp-03-25:free", "backup_models": ["meta-llama/llama-4-maverick:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "Code Reviewer", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]}
                ]
            elif task_name == "code_review":
                participants = [
                    {"role": "Code Reviewer", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "Security Auditor", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]},
                    {"role": "Performance Analyst", "model": "meta-llama/llama-4-maverick:free", "backup_models": ["google/gemini-2.5-pro-exp-03-25:free", "deepseek/deepseek-chat-v3-0324:free"]}
                ]
            else:
                # Default participants for unknown task types
                participants = [
                    {"role": "Expert 1", "model": "meta-llama/llama-4-maverick:free"},
                    {"role": "Expert 2", "model": "google/gemini-2.5-pro-exp-03-25:free"}
                ]
        
        # Enhance each participant with system prompts if not already specified
        for participant in participants:
            if "system_prompt" not in participant:
                role = participant["role"]
                participant["system_prompt"] = self._get_role_system_prompt(role, task_name)
        
        return participants
    
    def _get_role_system_prompt(self, role: str, task_name: str) -> str:
        """Get the system prompt for a specific role and task.
        
        Args:
            role: The role name
            task_name: The task name
            
        Returns:
            The system prompt for this role and task
        """
        # Check if there's a specific prompt for this role and task
        role_config = self.config.get("ROLES", {}).get(role, {})
        task_specific_prompt = role_config.get("tasks", {}).get(task_name, "")
        
        if task_specific_prompt:
            return task_specific_prompt
        
        # Fall back to generic role prompt
        generic_prompt = role_config.get("system_prompt", "")
        if generic_prompt:
            return generic_prompt
        
        # Generate a default prompt based on role and task
        default_prompts = {
            "Requirements Analyst": "You are an expert in analyzing and clarifying requirements. Focus on understanding user needs, identifying edge cases, and ensuring requirements are complete and unambiguous.",
            "Domain Expert": "You have deep knowledge in the problem domain. Provide context, identify domain-specific challenges, and ensure solutions align with domain best practices.",
            "User Advocate": "You represent the end users. Focus on usability, accessibility, and ensuring the solution meets real user needs.",
            "System Architect": "You are an expert in designing robust software architectures. Focus on component design, interfaces, and ensuring the architecture meets all functional and non-functional requirements.",
            "Security Expert": "You specialize in security aspects of software design. Identify potential vulnerabilities and ensure the design incorporates security best practices.",
            "Performance Engineer": "You focus on system performance. Identify potential bottlenecks and ensure the design can meet performance requirements.",
            "Technical Lead": "You oversee technical implementation. Focus on technical feasibility, resource allocation, and ensuring the implementation plan is comprehensive.",
            "Developer": "You are an experienced software developer. Focus on implementation details, coding standards, and technical challenges.",
            "QA Engineer": "You specialize in quality assurance. Focus on testability, edge cases, and ensuring the implementation plan includes adequate testing.",
            "Senior Developer": "You are a senior software developer with extensive experience. Write clean, efficient, and well-documented code that follows best practices.",
            "Code Reviewer": "You are an expert in code review. Focus on code quality, adherence to standards, and identifying potential issues.",
            "Security Auditor": "You specialize in security code reviews. Identify security vulnerabilities and ensure the code follows security best practices.",
            "Performance Analyst": "You focus on code performance. Identify performance issues and suggest optimizations."
        }
        
        return default_prompts.get(role, f"You are an expert {role}. Contribute your expertise to the current task: {task_name}.")
    
    async def _execute_standard_task(self, 
                                 task_name: str, 
                                 role_name: str,
                                 input_data: str) -> Tuple[bool, str]:
        """Execute a standard (non-collaborative) task using a single model.
        
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
            
        # Get system prompt
        system_prompt = primary_config.get("system_prompt", "")
        
        # Add validation instructions to system prompt
        validation_config = task_config.get("validation", {})
        system_prompt = self._enhance_system_prompt(system_prompt, task_name, validation_config)
        
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
            return True, result
            
        except Exception as e:
            print(f"Error executing task {task_name}: {str(e)}")
            return False, f"Error: {str(e)}"
    
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