import os
import json
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

import requests
from time import sleep
import subprocess
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="MetaGPT Self-hosted Chat UI Integration")

# Environment variables
CHAT_UI_URL = os.getenv("CHAT_UI_URL", "http://localhost:8088")

# Role avatar mappings
ROLE_AVATARS = {
    "Product Manager": "https://ui-avatars.com/api/?name=PM&color=fff&background=2196F3",
    "Project Manager": "https://ui-avatars.com/api/?name=PM&color=fff&background=673AB7",
    "Architect": "https://ui-avatars.com/api/?name=AR&color=fff&background=FF9800",
    "Developer": "https://ui-avatars.com/api/?name=DEV&color=fff&background=4CAF50",
    "QA Engineer": "https://ui-avatars.com/api/?name=QA&color=fff&background=E91E63",
    "Security Expert": "https://ui-avatars.com/api/?name=SEC&color=fff&background=F44336",
    "Technical Lead": "https://ui-avatars.com/api/?name=TL&color=fff&background=9C27B0",
    "User Advocate": "https://ui-avatars.com/api/?name=UX&color=fff&background=00BCD4",
    "Domain Expert": "https://ui-avatars.com/api/?name=DE&color=fff&background=795548",
    "Code Reviewer": "https://ui-avatars.com/api/?name=CR&color=fff&background=607D8B",
    "Technical Writer": "https://ui-avatars.com/api/?name=TW&color=fff&background=009688",
    "Security Auditor": "https://ui-avatars.com/api/?name=SA&color=fff&background=FF5722"
}

# Models
class Message(BaseModel):
    role: str
    content: str

class Conversation(BaseModel):
    messages: List[Message]
    channel_id: Optional[str] = None
    project_name: str

# No Rocket.Chat connection needed for self-hosted chat UI.


# No agent user creation needed for self-hosted chat UI.

# No channel creation needed for self-hosted chat UI.

# Store or forward conversation data for the self-hosted chat UI
# For demo, just save to a file (could be replaced with DB or API call)
def post_messages_to_channel(conversation: Conversation, background_tasks: BackgroundTasks):
    output_path = os.path.join(os.path.dirname(__file__), '../visualization/sample_output.json')
    try:
        with open(output_path, 'w') as f:
            json.dump(conversation.dict(), f, indent=2)
        logger.info(f"Conversation saved to {output_path}")
        return {"success": True, "path": output_path}
    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save conversation: {str(e)}")
    finally:
        pass

# API routes
# No startup event needed for self-hosted chat UI.

@app.get("/")
async def root():
    return {"message": "MetaGPT Self-hosted Chat UI Integration API"}

@app.post("/conversations")
async def create_conversation(conversation: Conversation, background_tasks: BackgroundTasks):
    """Create a new conversation and save for the self-hosted chat UI"""
    return post_messages_to_channel(conversation, background_tasks)

@app.post("/process_metagpt_output")
async def process_metagpt_output(background_tasks: BackgroundTasks, project_name: str, file_path: Optional[str] = None):
    """Process MetaGPT output from a file and save for the self-hosted chat UI"""
    try:
        # Default to workspace/output.json if no file path provided
        if file_path is None:
            file_path = "/app/workspace/output.json"
        
        # Read the file
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Convert to conversation format
        messages = []
        
        # Process different sections of the output based on roles
        for key, value in data.items():
            if key.endswith("_validation"):
                continue
            
            # Map output keys to roles
            role_mapping = {
                "requirements_analysis": "Requirements Analyst",
                "system_design": "Architect",
                "implementation_planning": "Project Manager",
                "code_generation": "Developer",
                "code_review": "Code Reviewer"
            }
            
            role = role_mapping.get(key, "Technical Lead")
            
            if isinstance(value, str) and not value.startswith("Failed"):
                messages.append(Message(role=role, content=value))
        
        if not messages:
            # If no valid messages, add a placeholder
            messages.append(Message(
                role="Technical Lead", 
                content="The team is still working on this project. Check back later for updates."
            ))
        
        # Create conversation
        conversation = Conversation(
            messages=messages,
            project_name=project_name
        )
        
        return post_messages_to_channel(conversation, background_tasks)
    
    except Exception as e:
        logger.error(f"Error processing MetaGPT output: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing output: {str(e)}")
    finally:
        pass

# Run MetaGPT via run_collaborative.py script
class PromptRequest(BaseModel):
    prompt: str
    workflow_file: Optional[str] = None
    config_file: Optional[str] = None
    api_key: Optional[str] = None

@app.post("/api/run_metagpt")
async def run_metagpt(prompt_request: PromptRequest):
    """Run MetaGPT with the collaborative workflow."""
    logger.info(f"Received run_metagpt request with prompt: {prompt_request.prompt[:100]}...")
    try:
        # Get project directory
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        workspace_root = os.path.join(parent_dir, "workspace")
        os.makedirs(workspace_root, exist_ok=True)
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(parent_dir, "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
            logger.info(f"Created logs directory: {logs_dir}")
        
        # Create workspace instance directory with timestamp
        timestamp = int(time.time())
        run_dir = os.path.join(workspace_root, f"workspace_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        
        # Create workflows directory inside the run_dir
        workspace_workflows_dir = os.path.join(run_dir, "workflows")
        if not os.path.exists(workspace_workflows_dir):
            os.makedirs(workspace_workflows_dir, exist_ok=True)
            logger.info(f"Created workflows directory in workspace: {workspace_workflows_dir}")
            
        # Create logs directory inside the run_dir
        workspace_logs_dir = os.path.join(run_dir, "logs")
        if not os.path.exists(workspace_logs_dir):
            os.makedirs(workspace_logs_dir, exist_ok=True)
            logger.info(f"Created logs directory in workspace: {workspace_logs_dir}")

        # Set API_LOG_DIR to include both log directories
        # This is a special format that the CollaborativeConversation class will recognize
        # to save logs in both locations
        os.environ["API_LOG_DIR"] = f"{logs_dir}:{workspace_logs_dir}"
        os.environ["WORKSPACE_DIR"] = run_dir
        logger.info(f"Set API_LOG_DIR to include both global and workspace logs: {logs_dir} and {workspace_logs_dir}")
        logger.info(f"Set WORKSPACE_DIR to: {run_dir}")
        
        # Create a copy of the config file with the API key explicitly set
        # This is more reliable than relying on environment variables in Docker
        config_path = os.path.join(parent_dir, "config.yml")
        
        # Use proper YAML parsing/writing instead of string replacement
        import yaml
        
        # Read the original config
        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                logger.error(f"Error parsing config file: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error parsing config file: {str(e)}")
            except Exception as e:
                logger.error(f"Error reading config file: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error reading config file: {str(e)}")
        
        # Get API key from request or environment
        api_key = None
        if prompt_request.api_key:
            api_key = prompt_request.api_key
            logger.info("Using API key from request")
        else:
            # Use the environment variable API key as fallback
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if api_key:
                logger.info("Using API key from environment variable")
            else:
                # Try to use the key from config.yml as last resort
                try:
                    api_key = config.get("OPENROUTER_CONFIG", {}).get("default_api_key")
                    logger.info("Using API key from config.yml")
                except:
                    logger.warning("No API key available")
        
        # Update the config with the new API key if we have one
        if api_key:
            # Ensure the OPENROUTER_CONFIG section exists
            if "OPENROUTER_CONFIG" not in config:
                config["OPENROUTER_CONFIG"] = {}
            
            # Set the default_api_key
            config["OPENROUTER_CONFIG"]["default_api_key"] = api_key
            
            # Also update all model_keys to use the same key
            if "model_keys" not in config["OPENROUTER_CONFIG"]:
                config["OPENROUTER_CONFIG"]["model_keys"] = {}
            
            # Get all model names from model_registry
            models = []
            try:
                # Extract models from the MODEL_REGISTRY section
                model_capabilities = config.get("MODEL_REGISTRY", {}).get("model_capabilities", {})
                for capability_models in model_capabilities.values():
                    models.extend(capability_models)
                
                # Add fallback models
                fallback_models = config.get("MODEL_REGISTRY", {}).get("fallback_free_models", [])
                models.extend(fallback_models)
                
                # Add default models
                default_models = config.get("MODEL_REGISTRY", {}).get("default_models_by_task", {}).values()
                for model_list in default_models:
                    if isinstance(model_list, list):
                        models.extend(model_list)
                
                # Remove duplicates
                models = list(set(models))
            except Exception as e:
                logger.warning(f"Error extracting models from config: {str(e)}")
                # Use hardcoded default models as fallback
                models = [
                    "deepseek/deepseek-chat-v3-0324:free",
                    "meta-llama/llama-4-maverick:free",
                    "google/gemini-2.5-pro-exp-03-25:free"
                ]
            
            # Set the API key for each model
            for model in models:
                config["OPENROUTER_CONFIG"]["model_keys"][model] = api_key
        
        # Create the modified config file in the workspace
        modified_config_path = os.path.join(run_dir, "modified_config.yml")
        with open(modified_config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Created modified config with API key at: {modified_config_path}")
        
        # Get workflow file path from request or use default
        workflows_dir = os.path.join(parent_dir, "workflows")
        
        if prompt_request.workflow_file:
            workflow_rel_path = prompt_request.workflow_file
            workflow_path = os.path.join(workflows_dir, workflow_rel_path)
            logger.info(f"Using requested workflow file: {workflow_path}")
        else:
            # Default to collaborative_workflow.yml
            workflow_path = os.path.join(workflows_dir, "collaborative_workflow.yml")
            logger.info(f"Using default workflow file: {workflow_path}")
        
        # Verify workflow file exists
        if not os.path.exists(workflow_path):
            logger.error(f"Workflow file not found: {workflow_path}")
            # Try to list available workflows for debugging
            try:
                available_workflows = os.listdir(workflows_dir)
                logger.info(f"Available workflows: {available_workflows}")
            except Exception as e:
                logger.error(f"Error listing workflows directory: {str(e)}")
            
            raise HTTPException(
                status_code=404, 
                detail=f"Workflow file not found: {os.path.basename(workflow_path)}"
            )
            
        # Copy the workflow file to the workspace workflows directory
        workflow_filename = os.path.basename(workflow_path)
        workspace_workflow_path = os.path.join(workspace_workflows_dir, workflow_filename)
        try:
            import shutil
            shutil.copy2(workflow_path, workspace_workflow_path)
            logger.info(f"Copied workflow file to workspace: {workspace_workflow_path}")
        except Exception as e:
            logger.error(f"Error copying workflow file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error copying workflow file: {str(e)}")
        
        # Extract workflow name from the YAML file
        try:
            import yaml
            with open(workspace_workflow_path, 'r') as f:
                workflow_data = yaml.safe_load(f)
                
            if workflow_data and isinstance(workflow_data, dict):
                # Look for a name field in the workflow file
                workflow_name = None
                if "name" in workflow_data:
                    workflow_name = workflow_data["name"]
                    logger.info(f"Found name in workflow file: {workflow_name}")
                
                # If no name field is found, use the filename without extension
                if not workflow_name:
                    workflow_name = os.path.basename(workspace_workflow_path).split('.')[0]
                    logger.info(f"No name field found in workflow file, using filename: {workflow_name}")
            else:
                # If file is empty or invalid, fall back to using the filename
                workflow_name = os.path.basename(workspace_workflow_path).split('.')[0]
                logger.warning(f"Invalid or empty workflow file, using filename: {workflow_name}")
                
        except Exception as e:
            # If file can't be read, fall back to using the filename
            workflow_name = os.path.basename(workspace_workflow_path).split('.')[0]
            logger.warning(f"Error reading workflow file, using name from filename: {workflow_name} (Error: {str(e)})")
        
        # Write prompt to file
        input_file = os.path.join(run_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write(prompt_request.prompt)
        
        # Run MetaGPT
        output_file = os.path.join(run_dir, "output.json")
        
        # Export the modified config path as an environment variable
        # This ensures the collaborative conversation module will use our config
        os.environ["METAGPT_CONFIG_PATH"] = modified_config_path
        logger.info(f"Set METAGPT_CONFIG_PATH to: {modified_config_path}")
        
        # Run the workflow directly using subprocess
        try:
            import subprocess
            import sys
            
            # Build command for executing run_collaborative.py
            cmd = [
                sys.executable, 
                os.path.join(parent_dir, "run_collaborative.py"),
                "--config", modified_config_path,
                "--workflow", workspace_workflow_path,
                "--input", input_file,
                "--output", output_file
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Execute the command with environment variables set
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=os.environ)
            
            # Log command output
            if result.stdout:
                logger.info(f"Command stdout:\n{result.stdout[:1000]}...")
            
            # Check if output file was created
            if not os.path.exists(output_file):
                raise HTTPException(status_code=500, detail="MetaGPT output.json not generated")
                
            # Load and return the result
            with open(output_file, "r") as f:
                result = json.load(f)
            return {"status": "success", "result": result}
            
        except subprocess.CalledProcessError as e:
            error_msg = f"MetaGPT execution failed with code {e.returncode}"
            logger.error(error_msg)
            if e.stdout:
                logger.error(f"Command stdout:\n{e.stdout}")
            if e.stderr:
                logger.error(f"Command stderr:\n{e.stderr}")
            raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        logger.exception(f"Unexpected error in run_metagpt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Always healthy for self-hosted chat UI
    return {"status": "healthy", "chat_ui_connected": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
