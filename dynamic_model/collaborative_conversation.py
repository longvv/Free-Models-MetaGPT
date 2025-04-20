import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import yaml
import logging

logger = logging.getLogger(__name__)

class CollaborativeConversation:
    """Facilitates conversations between multiple expert models to collaborate on tasks.
    
    This class enables different expert models to interact with each other in a conversation-like
    format, where each model can contribute its expertise, ask questions, and build upon the
    contributions of other models.
    """
    
    def __init__(self, config_path=None, adapter: Any = None, memory_system: Any = None, workspace_dir=None):
        """Initialize the collaborative conversation system.
        
        Args:
            config_path (str, optional): Path to the config file. If not provided, will use environment variable or default.
            adapter: The model adapter for generating completions
            memory_system: The memory system for storing conversation history
            workspace_dir (str, optional): Path to the workspace directory. 
        """
        self.workspace_dir = workspace_dir
        
        # Use the provided config path or try to get it from environment
        if config_path:
            self.config_path = config_path
        else:
            # Try to get from environment variable first
            self.config_path = os.environ.get("METAGPT_CONFIG_PATH")
            if not self.config_path:
                # Fall back to default path
                self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yml")
        
        logger.info(f"Initializing CollaborativeConversation with config_path: {self.config_path}")
        
        # Load the config
        self._load_config()
        
        self.adapter = adapter
        self.memory = memory_system
        self.conversation_history = []
        self.max_turns = self.config.get("max_conversation_turns", 10)
        self.min_turns = self.config.get("min_conversation_turns", 3)
        self.consensus_threshold = self.config.get("consensus_threshold", 0.8)
        
        # Setup API response logging
        self.log_api_responses = self.config.get("log_api_responses", True)
        
        # Use API_LOG_DIR environment variable if set, otherwise use config or default
        api_log_env = os.environ.get("API_LOG_DIR") or self.config.get("api_log_dir", "logs")
        
        # Check if API_LOG_DIR contains multiple paths (separated by :)
        if ":" in api_log_env:
            self.api_log_dirs = api_log_env.split(":")
            print(f"Using multiple API log directories: {self.api_log_dirs}")
        else:
            self.api_log_dirs = [api_log_env]
            print(f"Using API log directory: {api_log_env}")
        
        # Get workspace directory from environment or config
        self.workspace_dir = os.environ.get("WORKSPACE_DIR") or self.config.get("workspace_dir")
        if self.workspace_dir:
            print(f"Using workspace directory: {self.workspace_dir}")
            # Ensure workspace logs directory exists
            self.workspace_logs_dir = os.path.join(self.workspace_dir, "logs")
            if not os.path.exists(self.workspace_logs_dir):
                os.makedirs(self.workspace_logs_dir, exist_ok=True)
                print(f"Created logs directory in workspace: {self.workspace_logs_dir}")
        
            # Add workspace logs directory to the list if not already included
            if self.workspace_logs_dir not in self.api_log_dirs:
                self.api_log_dirs.append(self.workspace_logs_dir)
        
        # Create all log directories if they don't exist
        if self.log_api_responses:
            for log_dir in self.api_log_dirs:
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
                    print(f"Created API log directory: {log_dir}")
    
    def _load_config(self):
        """Load configuration from the config file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
                
            # Extract API key configuration
            self.api_key = None
            if "OPENROUTER_CONFIG" in self.config:
                self.api_key = self.config["OPENROUTER_CONFIG"].get("default_api_key")
                
            if self.api_key:
                logger.info("Successfully loaded API key from config")
            else:
                logger.warning("No API key found in config")
                
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            self.config = {}
    
    async def start_conversation(self, 
                               topic: str, 
                               initial_prompt: str,
                               participants: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """Start a collaborative conversation between multiple expert models.
        
        Args:
            topic: The topic or task for the conversation
            initial_prompt: The initial prompt to start the conversation
            participants: List of participant configurations including roles and models
            
        Returns:
            Tuple of (success, final_result)
        """
        print(f"\n=== Executing task: {topic} (Type: collaborative) ===")
        print(f"Starting collaborative conversation on: {topic}")
        print(f"Participants: {', '.join([p['role'] for p in participants])}")
        
        # Log the initial prompt for debugging
        print(f"\n--- INITIAL PROMPT ---")
        print(initial_prompt)
        print(f"--- END OF INITIAL PROMPT ---\n")
        
        # Initialize conversation with the initial prompt
        self.conversation_history = [
            {"role": "system", "content": f"This is a collaborative conversation on: {topic}"},
            {"role": "user", "content": initial_prompt}
        ]
        
        # Track consensus and contributions
        consensus_reached = False
        turn_count = 0
        final_result = ""
        
        # Main conversation loop
        while turn_count < self.max_turns and (turn_count < self.min_turns or not consensus_reached):
            for participant in participants:
                # Get participant details
                role_name = participant["role"]
                model_name = participant.get("model")
                system_prompt = participant.get("system_prompt", "")
                
                # Prepare the full conversation history for this participant
                full_history = self._prepare_conversation_context(role_name, system_prompt)
                
                # Generate response from this participant
                success, response = await self._generate_participant_response(
                    role_name, 
                    model_name, 
                    full_history
                )
                
                if not success:
                    print(f"Failed to get response from {role_name}")
                    continue
                
                # Add response to conversation history
                self.conversation_history.append({"role": "assistant", "content": response, "name": role_name})
                
                # Display the model's message in real-time with timestamp
                timestamp = datetime.now().strftime('%H:%M:%S,%f')[:-3]
                print(f"\n2025-04-18 {timestamp} - INFO - [{role_name}]:")
                print(response)
                print("\n")
                
                # Check if this participant is proposing a final solution
                if "FINAL SOLUTION:" in response or "CONSENSUS:" in response:
                    # Extract the proposed solution
                    final_result = self._extract_final_solution(response)
                    
                    # Ask other participants to vote on this solution
                    consensus_reached, agreement_ratio = await self._check_consensus(
                        final_result, 
                        participants, 
                        role_name
                    )
                    
                    if consensus_reached:
                        print(f"Consensus reached with {agreement_ratio:.0%} agreement after {turn_count + 1} turns")
                        break
            
            # Increment turn counter
            turn_count += 1
            
            if consensus_reached:
                break
                
            print(f"Completed conversation turn {turn_count}/{self.max_turns}")
        
        # If we reached max turns without consensus, use the last proposed solution or compile a summary
        if not consensus_reached and turn_count >= self.max_turns:
            print(f"Max turns ({self.max_turns}) reached without consensus. Compiling final result.")
            final_result = await self._compile_final_result(participants)
        
        # Store the full conversation in memory for future reference
        conversation_text = json.dumps({"history": self.conversation_history, "result": final_result})
        # Use add_document instead which is a method available in EnhancedMemorySystem
        metadata = {"source": "collaborative_conversation", "topic": topic, "type": "conversation_summary"}
        self.memory.add_document(conversation_text, metadata)
        
        # Log the final result for debugging
        print(f"\n--- FINAL RESULT ---")
        print(final_result)
        print(f"--- END OF FINAL RESULT ---\n")
        
        return True, final_result
    
    def _prepare_conversation_context(self, role_name: str, system_prompt: str) -> List[Dict[str, str]]:
        """Prepare the conversation context for a specific participant.
        
        Args:
            role_name: The name of the participant role
            system_prompt: The system prompt for this participant
            
        Returns:
            List of message dictionaries representing the conversation context
        """
        # Start with a system message specific to this participant
        role_specific_prompt = f"{system_prompt}\n\nYou are the {role_name} in this collaborative conversation. "
        role_specific_prompt += f"Review the conversation history and contribute your expertise. "
        role_specific_prompt += f"You can ask questions to other participants, build upon their ideas, or propose solutions."
        
        context = [{"role": "system", "content": role_specific_prompt}]
        
        # Add the conversation history
        for message in self.conversation_history:
            # Skip the original system message as we've replaced it with a role-specific one
            if message["role"] == "system":
                continue
                
            # For assistant messages, include who said it
            if message["role"] == "assistant" and "name" in message:
                speaker = message["name"]
                content = f"{speaker}: {message['content']}"
                context.append({"role": "user", "content": content})
            else:
                context.append(message)
        
        return context
    
    def _get_participant_config(self, role_name: str) -> Dict[str, Any]:
        """Get the configuration for a specific participant.
        
        Args:
            role_name: The name of the participant role
            
        Returns:
            Participant configuration dictionary
        """
        # Look for the participant in the configuration
        participants_config = self.config.get("participants", [])
        for participant in participants_config:
            if participant.get("role") == role_name:
                return participant
        
        # Return empty config if not found
        return {}
    
    async def _generate_participant_response(self, 
                                          role_name: str, 
                                          model_name: str, 
                                          conversation_context: List[Dict[str, str]]) -> Tuple[bool, str]:
        """Generate a response from a specific participant.
        
        Args:
            role_name: The name of the participant role
            model_name: The name of the model to use
            conversation_context: The conversation context for this participant
            
        Returns:
            Tuple of (success, response)
        """
        try:
            # Get backup models for this participant from config
            participant_config = self._get_participant_config(role_name)
            backup_models = participant_config.get("backup_models", [])
            
            # Create a task config for this specific participant with backup models
            task_config = {
                "primary": {
                    "model": model_name,
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
            }
            
            # Add backup model configuration if available
            if backup_models:
                task_config["backup"] = {
                    "model": backup_models[0] if isinstance(backup_models, list) and backup_models else backup_models,
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
            
            # Log the full model request with messages and configuration
            print(f"\n2025-04-18 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - Model request to {model_name}")
            print(f"2025-04-18 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - Messages: {len(conversation_context)}, Approx tokens: {sum(len(msg.get('content', '')) for msg in conversation_context) // 4}")
            print(f"2025-04-18 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - Processing step: generate_completion")
            print(f"Found exact API key match for {model_name}")
            print(f"Making request to model: {model_name}")
            
            # Generate completion using the adapter
            response = await self.adapter.generate_completion(
                messages=conversation_context,
                task_config=task_config
            )
            
            # Log the full model response
            print(f"2025-04-18 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - Processing step: API Response")
            print(f"2025-04-18 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - Received response from {model_name}")
            print(f"2025-04-18 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - Response contains {len(response.get('choices', []))} choices")
            
            # Log the full API response to a file for debugging empty responses
            if self.log_api_responses:
                self._log_api_response(model_name, role_name, response)
            
            # Log the full content of the response for debugging
            if response.get('choices') and len(response['choices']) > 0:
                # Handle different response formats based on model provider
                choice = response["choices"][0]
                message = choice.get("message", {})
                
                # Extract content from message - handle nested structure for models like deepseek
                if isinstance(message, dict):
                    if "content" in message:
                        content = message["content"]
                    else:
                        print(f"Warning: Couldn't find content in message structure: {json.dumps(message, indent=2)}")
                        return False, f"Error: Could not extract content from {model_name} response"
                else:
                    content = str(message)
                
                # Special handling for deepseek model response format
                # Check if this is a response object with nested structure in the API response logs
                if not content and isinstance(response.get("response"), dict):
                    deepseek_choices = response.get("response", {}).get("choices", [])
                    if deepseek_choices and len(deepseek_choices) > 0:
                        deepseek_message = deepseek_choices[0].get("message", {})
                        if isinstance(deepseek_message, dict) and "content" in deepseek_message:
                            content = deepseek_message["content"]
                
                print(f"\n--- FULL RESPONSE CONTENT FROM {role_name.upper()} ---")
                print(content)
                print(f"--- END OF RESPONSE CONTENT ---\n")
                
                # Store the result
                result = content
                return True, result
            else:
                # Handle case where response doesn't contain expected content
                print(f"Warning: Response from {role_name} doesn't contain expected content structure")
                print(f"Response structure: {json.dumps(response, indent=2)}")
                
                # Log empty response error to file
                if self.log_api_responses:
                    self._log_api_response(model_name, role_name, response, is_error=True)
                    
                return False, f"Error: Invalid response structure from {model_name}"
            
        except Exception as e:
            print(f"Error generating response for {role_name}: {str(e)}")
            # Log more detailed error information for debugging
            import traceback
            print(f"Detailed error traceback: {traceback.format_exc()}")
            # Log exception to file
            if self.log_api_responses:
                error_response = {"error": str(e), "traceback": traceback.format_exc()}
                self._log_api_response(model_name, role_name, error_response, is_error=True)
                
            return False, f"Error: {str(e)}"
    
    def _extract_final_solution(self, response: str) -> str:
        """Extract the final solution from a participant's response.
        
        Args:
            response: The participant's response
            
        Returns:
            The extracted final solution
        """
        if "FINAL SOLUTION:" in response:
            parts = response.split("FINAL SOLUTION:")
            return parts[1].strip()
        elif "CONSENSUS:" in response:
            parts = response.split("CONSENSUS:")
            return parts[1].strip()
        else:
            return response
    
    async def _check_consensus(self, 
                            proposed_solution: str, 
                            participants: List[Dict[str, Any]], 
                            proposer: str) -> Tuple[bool, float]:
        """Check if there is consensus among participants on the proposed solution.
        
        Args:
            proposed_solution: The proposed solution to check consensus on
            participants: List of participant configurations
            proposer: The name of the participant who proposed the solution
            
        Returns:
            Tuple of (consensus_reached, agreement_ratio)
        """
        # Skip the proposer in the voting
        voters = [p for p in participants if p["role"] != proposer]
        
        if not voters:
            # If there are no other participants, consider it consensus
            return True, 1.0
        
        agreements = 0
        disagreements = 0
        
        for voter in voters:
            role_name = voter["role"]
            model_name = voter.get("model")
            system_prompt = voter.get("system_prompt", "")
            
            # Prepare voting prompt
            voting_prompt = f"A solution has been proposed by {proposer}:\n\n"
            voting_prompt += f"{proposed_solution}\n\n"
            voting_prompt += f"As the {role_name}, do you agree with this solution? "
            voting_prompt += f"Respond with 'AGREE' or 'DISAGREE' followed by your reasoning."
            
            # Create voting context
            voting_context = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": voting_prompt}
            ]
            
            # Get vote
            success, vote_response = await self._generate_participant_response(
                role_name, 
                model_name, 
                voting_context
            )
            
            if not success:
                # Count as disagreement if we couldn't get a response
                disagreements += 1
                continue
            
            # Add vote to conversation history
            self.conversation_history.append({
                "role": "assistant", 
                "content": vote_response, 
                "name": role_name
            })
            
            # Display the voting response in real-time with timestamp
            timestamp = datetime.now().strftime('%H:%M:%S,%f')[:-3]
            print(f"\n2025-04-18 {timestamp} - INFO - [{role_name} - Vote]:")
            print(vote_response)
            print("\n")
            
            # Count the vote
            if vote_response.strip().startswith("AGREE"):
                agreements += 1
            else:
                disagreements += 1
        
        # Calculate agreement ratio
        total_votes = agreements + disagreements
        agreement_ratio = agreements / total_votes if total_votes > 0 else 0
        
        # Check if consensus threshold is reached
        consensus_reached = agreement_ratio >= self.consensus_threshold
        
        return consensus_reached, agreement_ratio
    
    async def _compile_final_result(self, participants: List[Dict[str, Any]]) -> str:
        """Compile a final result from the conversation when no consensus is reached.
        
        Args:
            participants: List of participant configurations
            
        Returns:
            The compiled final result
        """
        try:
            # Use a designated summarizer (e.g., the first participant) to compile the result
            summarizer = participants[0]
            role_name = summarizer["role"]
            model_name = summarizer.get("model")
            
            # Prepare summarization prompt
            summary_prompt = "The conversation has reached the maximum number of turns without consensus. "
            summary_prompt += "Please compile a final result that incorporates the most valuable insights "
            summary_prompt += "and contributions from all participants. Focus on areas of agreement "
            summary_prompt += "and resolve conflicts where possible.\n\n"
            summary_prompt += "Conversation history:\n"
            
            # Add condensed conversation history
            for message in self.conversation_history:
                if message["role"] == "assistant" and "name" in message:
                    speaker = message["name"]
                    # Add just the first 200 characters of each message to avoid token limits
                    content = message["content"][:200] + "..." if len(message["content"]) > 200 else message["content"]
                    summary_prompt += f"\n{speaker}: {content}"
            
            # Create summarization context
            summary_context = [
                {"role": "system", "content": "You are a neutral facilitator tasked with compiling a final result from a collaborative conversation."},
                {"role": "user", "content": summary_prompt}
            ]
            
            # Log the summarization attempt
            print(f"\n--- ATTEMPTING TO COMPILE FINAL RESULT ---")
            print(f"Using {role_name} with model {model_name} as summarizer")
            
            # Generate summary
            success, summary = await self._generate_participant_response(
                "Facilitator", 
                model_name, 
                summary_context
            )
            
            if not success:
                print(f"Failed to compile final result: Summarization attempt unsuccessful")
                return "Failed to compile final result due to an error."
            
            # Log successful compilation
            print(f"\n--- SUCCESSFULLY COMPILED FINAL RESULT ---")
            return summary
            
        except Exception as e:
            import traceback
            print(f"Error compiling final result: {str(e)}")
            print(f"Detailed error traceback: {traceback.format_exc()}")
            return "Failed to compile final result due to an error."
            
    def _log_api_response(self, model_name: str, role_name: str, response: Dict[str, Any], is_error: bool = False) -> None:
        """Log the full API response to a file for debugging purposes.
        
        Args:
            model_name: The name of the model used
            role_name: The name of the participant role
            response: The full API response object
            is_error: Whether this is an error response
        """
        try:
            # Create a timestamp for the log filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            status = "error" if is_error else "success"
            base_filename = f"api_response_{model_name.replace('/', '_')}_{role_name}_{status}_{timestamp}.json"
            
            # Add metadata to the logged response
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "model": model_name,
                "role": role_name,
                "status": status,
                "response": response
            }
            
            # Save logs to all directories
            saved_locations = []
            
            for log_dir in self.api_log_dirs:
                try:
                    log_path = os.path.join(log_dir, base_filename)
                    with open(log_path, 'w') as f:
                        json.dump(log_data, f, indent=2)
                    saved_locations.append(log_path)
                    print(f"Saved API response log to: {log_path}")
                except Exception as e:
                    print(f"Error saving log to {log_dir}: {str(e)}")
            
            # Log where files were saved
            if saved_locations:
                log_locations = ', '.join(saved_locations)
                print(f"2025-04-20 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - INFO - API response logged to: {log_locations}")
            else:
                print(f"2025-04-20 {datetime.now().strftime('%H:%M:%S,%f')[:-3]} - ERROR - Failed to log API response to any location")
        
        except Exception as e:
            print(f"Error in log_api_response: {str(e)}")
            # Don't let logging errors affect the main process

    def process_prompt(self, prompt, workflow_file, output_file=None):
        """Process a prompt using the specified workflow.
        
        Args:
            prompt (str): The user prompt to process
            workflow_file (str): Path to the workflow YAML file
            output_file (str, optional): Path to save the output JSON
            
        Returns:
            dict: The result of processing the prompt
        """
        logger.info(f"Processing prompt: {prompt[:100]}...")
        logger.info(f"Using workflow file: {workflow_file}")
        logger.info(f"Using config file: {self.config_path}")
        
        if not output_file and self.workspace_dir:
            output_file = os.path.join(self.workspace_dir, "output.json")
            
        try:
            # Set necessary environment variables
            if self.api_key:
                os.environ["OPENROUTER_API_KEY"] = self.api_key
                logger.info("Set OPENROUTER_API_KEY environment variable from config")
            
            # Run the workflow
            import subprocess
            import sys
            
            # Get the parent directory for run_collaborative.py
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Prepare the input file if prompt contains newlines
            input_path = prompt
            if "\n" in prompt and self.workspace_dir:
                input_file = os.path.join(self.workspace_dir, "input.txt")
                with open(input_file, "w") as f:
                    f.write(prompt)
                input_path = input_file
            
            # Build command to run the workflow
            cmd = [
                sys.executable, 
                os.path.join(parent_dir, "run_collaborative.py"),
                "--config", self.config_path,
                "--workflow", workflow_file,
                "--input", input_path,
                "--output", output_file
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Run the command and capture output
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=os.environ)
            
            # Log the output
            if result.stdout:
                logger.info(f"Command stdout:\n{result.stdout[:1000]}...")
            
            # Check if output file was created
            if output_file and os.path.exists(output_file):
                import json
                with open(output_file, "r") as f:
                    return json.load(f)
            else:
                return {"status": "success", "message": "Workflow completed but no output file was created"}
                
        except subprocess.CalledProcessError as e:
            error_msg = f"MetaGPT execution failed with code {e.returncode}"
            if e.stdout:
                logger.error(f"Command stdout:\n{e.stdout}")
            if e.stderr:
                logger.error(f"Command stderr:\n{e.stderr}")
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.exception(f"Error processing prompt: {str(e)}")
            raise e