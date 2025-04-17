import asyncio
import json
from typing import Dict, List, Tuple, Any, Optional

class CollaborativeConversation:
    """Facilitates conversations between multiple expert models to collaborate on tasks.
    
    This class enables different expert models to interact with each other in a conversation-like
    format, where each model can contribute its expertise, ask questions, and build upon the
    contributions of other models.
    """
    
    def __init__(self, config: Dict[str, Any], adapter: Any, memory_system: Any):
        """Initialize the collaborative conversation system.
        
        Args:
            config: Configuration dictionary for the conversation system
            adapter: The model adapter for generating completions
            memory_system: The memory system for storing conversation history
        """
        self.config = config
        self.adapter = adapter
        self.memory = memory_system
        self.conversation_history = []
        self.max_turns = config.get("max_conversation_turns", 10)
        self.min_turns = config.get("min_conversation_turns", 3)
        self.consensus_threshold = config.get("consensus_threshold", 0.8)
    
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
        print(f"Starting collaborative conversation on: {topic}")
        print(f"Participants: {', '.join([p['role'] for p in participants])}")
        
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
                
                # Display the model's message in real-time
                print(f"\n[{role_name}]: {response}\n")
                
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
            
            # Generate completion using the adapter
            response = await self.adapter.generate_completion(
                messages=conversation_context,
                task_config=task_config
            )
            
            result = response["choices"][0]["message"]["content"]
            return True, result
            
        except Exception as e:
            print(f"Error generating response for {role_name}: {str(e)}")
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
            
            # Display the voting response in real-time
            print(f"\n[{role_name} - Vote]: {vote_response}\n")
            
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
        
        # Generate summary
        success, summary = await self._generate_participant_response(
            "Facilitator", 
            model_name, 
            summary_context
        )
        
        if not success:
            return "Failed to compile final result due to an error."
        
        return summary