# enhanced_rate_limiting_orchestrator.py
# Enhanced collaborative orchestrator with rate limit handling for multi-role conversations

import asyncio
import json
import os
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

# Import the enhanced rate limiting adapter
from enhanced_rate_limiting_adapter import EnhancedRateLimitingAdapter
from enhanced_memory import EnhancedMemorySystem
from validators import ValidationSystem
from dynamic_model.collaborative_conversation import CollaborativeConversation
from enhanced_config_manager import EnhancedConfigManager

class EnhancedRateLimitingOrchestrator:
    """Enhanced orchestrator with advanced rate limit handling for collaborative conversations."""
    
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
        
        # Conversation state tracking
        self.paused_conversations = {}
        self.conversation_states = {}
    
    async def initialize(self):
        """Initialize the orchestrator and its components."""
        # Initialize the configuration manager
        await self.config_manager.initialize()
        
        # Get API keys for the adapter
        api_keys = self.config_manager.get_api_keys()
        
        # Create configuration for the rate limiting adapter
        adapter_config = {
            "OPENROUTER_CONFIG": {
                "default_api_key": api_keys.get("default"),
                "model_keys": api_keys.get("model_specific", {}),
                "rate_limiting": {
                    "requests_per_minute": 15,  # Conservative limit
                    "bucket_capacity": 20,
                    "refill_rate": 0.25,  # Tokens per second
                    "max_parallel": 2,  # Limit parallel requests
                    "max_retries": 5,
                    "base_retry_delay": 2.0,
                    "max_retry_delay": 60.0,
                    "request_delay": 1.0,  # Delay between consecutive requests
                    "jitter_factor": 0.3  # Add randomness to prevent thundering herd
                }
            },
            "log_dir": "logs"
        }
        
        # Print API keys configuration for debugging
        print(f"Using default API key (first 5 chars): {api_keys.get('default', '')[:5]}...")
        print(f"Loaded {len(api_keys.get('model_specific', {}))} model-specific API keys")
        
        # Initialize adapter with the configuration
        self.adapter = EnhancedRateLimitingAdapter(adapter_config)
        
        # Initialize memory system
        memory_config = self.config_manager.get_system_config("memory")
        self.memory = EnhancedMemorySystem(memory_config)
        
        # Initialize validator
        validator_config = self.config_manager.get_system_config("validators")
        self.validator = ValidationSystem(validator_config)
        
        # Initialize conversation manager with custom configuration
        conversation_config = {
            "max_conversation_turns": 15,  # Increase max turns to allow for rate limit pauses
            "min_conversation_turns": 3,
            "consensus_threshold": 0.8,
            "log_api_responses": True,
            "api_log_dir": "logs"
        }
        
        self.conversation = CollaborativeConversation(
            conversation_config,
            self.adapter,
            self.memory
        )
        
        print("Enhanced rate limiting orchestrator initialized successfully")
    
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
        """Execute a workflow with role-specific configurations and rate limit handling.
        
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
            
            print(f"\n=== Executing task: {task_name} (Type: {task_type}) ===\n")
            
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
                
                # Execute collaborative conversation with rate limit handling
                print(f"Starting collaborative conversation on: {task_name}")
                print(f"Participants: {', '.join([p['role'] for p in participants_config])}")
                
                # Try to execute the conversation with rate limit handling
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        success, result = await self._execute_collaborative_conversation(
                            task_name=task_name,
                            initial_prompt=current_input,
                            participants=participants_config
                        )
                        
                        if success:
                            break
                        else:
                            print(f"Conversation attempt {attempt+1} failed. Retrying...")
                            # Add delay before retry
                            await asyncio.sleep(5 * (attempt + 1))
                    except Exception as e:
                        print(f"Error in conversation attempt {attempt+1}: {str(e)}")
                        if attempt == max_attempts - 1:
                            # Last attempt failed
                            success = False
                            result = f"Error: Failed to execute task {task_name} after {max_attempts} attempts: {str(e)}"
                        else:
                            # Add delay before retry
                            await asyncio.sleep(5 * (attempt + 1))
                
                if not success:
                    print(f"Failed to execute collaborative task: {task_name}")
                    results[task_name] = result
                    continue
                
            else:
                # For standard tasks, use the regular task execution
                role_name = stage.get("role", "default") # Get role from task config or use default
                # Pass the full task_config which might contain model overrides etc.
                success, result = await self._execute_standard_task(task_name, role_name, current_input, stage)

                if not success:
                    print(f"Failed to execute standard task: {task_name}")
                    results[task_name] = f"Error: Failed to execute task {task_name}"
                    continue
            
            # Store result
            results[task_name] = result
            
            # Use this result as input for the next task
            current_input = result
            
            # Validate result if validation is enabled
            validation_config = stage.get("validation")
            if validation_config:
                is_valid, validation_message = await self.validator.validate(
                    result,
                    task_name, 
                    validation_config
                )
                
                if not is_valid:
                    print(f"Validation failed for task {task_name}: {validation_message}")
                    # Store validation result
                    results[f"{task_name}_validation"] = validation_message
        
        print(f"\n=== Workflow {workflow_name} completed ===\n")
        return results
    
    async def _execute_collaborative_conversation(self, 
                                               task_name: str,
                                               initial_prompt: str,
                                               participants: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """Execute a collaborative conversation with rate limit handling.
        
        Args:
            task_name: Name of the task
            initial_prompt: Initial prompt for the conversation
            participants: List of participant configurations
            
        Returns:
            Tuple of (success, result)
        """
        # Check if we have a paused conversation for this task
        if task_name in self.paused_conversations:
            print(f"Resuming paused conversation for task: {task_name}")
            # Restore conversation state
            conversation_state = self.paused_conversations[task_name]
            self.conversation.conversation_history = conversation_state["history"]
            current_turn = conversation_state["turn"]
            # Remove from paused conversations
            del self.paused_conversations[task_name]
        else:
            # Start a new conversation
            current_turn = 0
        
        try:
            # Start or resume the conversation
            success, result = await self.conversation.start_conversation(
                topic=task_name,
                initial_prompt=initial_prompt,
                participants=participants
            )
            
            return success, result
            
        except Exception as e:
            error_message = str(e)
            print(f"Error in collaborative conversation: {error_message}")
            
            # Check if this is a rate limit error
            if "rate limit" in error_message.lower() or "429" in error_message:
                print(f"Rate limit detected. Pausing conversation for task: {task_name}")
                
                # Save conversation state
                self.paused_conversations[task_name] = {
                    "history": self.conversation.conversation_history,
                    "turn": current_turn,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Return failure to trigger retry
                return False, f"Rate limit reached. Conversation paused for task: {task_name}"
            
            # For other errors, propagate the exception
            raise
    
    async def _execute_standard_task(self, 
                                  task_name: str, 
                                  role_name: str, 
                                  input_data: str,
                                  task_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute a standard task with a single model.
        
        Args:
            task_name: Name of the task
            role_name: Name of the role to use
            input_data: Input data for the task
            task_config: Task configuration dictionary
            
        Returns:
            Tuple of (success, result)
        """
        # Get role configuration
        role_config = self.config_manager.get_role(role_name)
        if not role_config:
            print(f"Warning: No configuration found for role {role_name}")
            return False, f"Error: No configuration found for role {role_name}"
        
        # Get model to use (override from task config or use role default)
        model = task_config.get("model") or role_config.get("model")
        backup_models = role_config.get("backup_models", [])
        
        # Get system prompt
        system_prompt = role_config.get("system_prompt", f"You are an AI assistant playing the role of {role_name}.")
        
        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_data}
        ]
        
        # Generate completion with fallback to backup models
        try:
            response = await self.adapter.generate_completion_with_fallback(
                primary_model=model,
                backup_models=backup_models,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Log the response
            status = "success" if "error" not in response else "error"
            self.adapter.log_api_response(role_name, model, status, response)
            
            if "error" in response:
                error_message = response["error"]["message"]
                print(f"Error in standard task {task_name}: {error_message}")
                return False, f"Error: {error_message}"
            
            # Extract the generated text
            result = response["choices"][0]["message"]["content"]
            return True, result
            
        except Exception as e:
            print(f"Exception in standard task {task_name}: {str(e)}")
            return False, f"Error: {str(e)}"

# Example usage
async def main():
    orchestrator = EnhancedRateLimitingOrchestrator()
    await orchestrator.initialize()
    
    results = await orchestrator.execute_workflow(
        "collaborative_workflow",
        "Design a secure login API with JWT authentication."
    )
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())