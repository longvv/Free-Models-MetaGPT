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

# Run MetaGPT via run_collaborative.py script
class PromptRequest(BaseModel):
    prompt: str
    workflow_file: Optional[str] = None
    config_file: Optional[str] = None

@app.post("/api/run_metagpt")
async def run_metagpt(prompt_request: PromptRequest):
    # Determine paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    workspace_root = os.path.join(parent_dir, "workspace")
    os.makedirs(workspace_root, exist_ok=True)
    # Locate run_collaborative script
    run_script = os.path.join(parent_dir, "run_collaborative.py")
    if not os.path.exists(run_script):
        raise HTTPException(status_code=500, detail="MetaGPT script not found")
    # Prepare run directory
    timestamp = int(time.time())
    run_dir = os.path.join(workspace_root, f"workspace_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    # Write prompt to file
    input_file = os.path.join(run_dir, "input.txt")
    with open(input_file, "w") as f:
        f.write(prompt_request.prompt)
    # Get workflow file path from request or use default
    workflows_dir = os.path.join(parent_dir, "workflows")
    if prompt_request.workflow_file:
        workflow_path = os.path.join(workflows_dir, prompt_request.workflow_file)
        logger.info(f"Using requested workflow file: {workflow_path}")
    else:
        # Default to metagpt_workflow.yml
        workflow_path = os.path.join(workflows_dir, "metagpt_workflow.yml")
        
        # If default doesn't exist, find any workflow file
        if not os.path.exists(workflow_path):
            logger.warning(f"Default workflow file not found at {workflow_path}")
            yml_files = [f for f in os.listdir(workflows_dir) if f.endswith(('.yml', '.yaml'))]
            if yml_files:
                workflow_path = os.path.join(workflows_dir, yml_files[0])
                logger.info(f"Using fallback workflow file: {workflow_path}")
            else:
                raise HTTPException(status_code=500, detail="No workflow file found")
    
    # Verify workflow file exists
    if not os.path.exists(workflow_path):
        logger.error(f"Workflow file not found: {workflow_path}")
        raise HTTPException(status_code=404, detail=f"Workflow file not found: {os.path.basename(workflow_path)}")
    # Run MetaGPT
    output_file = os.path.join(run_dir, "output.json")
    
    # Get config file path from request or use default
    if prompt_request.config_file:
        config_path = os.path.join(parent_dir, "config", prompt_request.config_file)
        logger.info(f"Using requested config file: {config_path}")
    else:
        config_path = os.path.join(parent_dir, "config.yml")
        logger.info(f"Using default config file: {config_path}")
    
    # Verify config file exists
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        raise HTTPException(status_code=404, detail=f"Config file not found: {os.path.basename(config_path)}")
    cmd = [sys.executable, run_script, 
           "--config", config_path,
           "--workflow", workflow_path,
           "--input", input_file, 
           "--output", output_file]
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        # Capture output for debugging
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Command completed successfully")
        if result.stdout:
            logger.info(f"Command stdout:\n{result.stdout[:500]}...")
    except subprocess.CalledProcessError as e:
        error_msg = f"MetaGPT execution failed with code {e.returncode}"
        if e.stdout:
            logger.error(f"Command stdout:\n{e.stdout}")
        if e.stderr:
            logger.error(f"Command stderr:\n{e.stderr}")
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    # Load and return result
    if not os.path.exists(output_file):
        raise HTTPException(status_code=500, detail="MetaGPT output.json not generated")
    with open(output_file, "r") as f:
        result = json.load(f)
    return {"status": "success", "result": result}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Always healthy for self-hosted chat UI
    return {"status": "healthy", "chat_ui_connected": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
