import os
import uvicorn
import subprocess
import sys
import glob
import asyncio
import traceback
import yaml
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, List, Optional, Any
import json
from pathlib import Path
from pydantic import BaseModel
import shutil
import time
from datetime import datetime
import aiofiles
import aiofiles.os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Define request models
class PromptRequest(BaseModel):
    prompt: str
    workflow_file: Optional[str] = None
    config_file: Optional[str] = None

# Create FastAPI app
app = FastAPI(title="MetaGPT Chat Visualization")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        print("==DEBUG== ConnectionManager initialized")
        
    async def connect(self, websocket: WebSocket, job_id: str):
        print(f"==DEBUG== ConnectionManager.connect called for job_id: {job_id}")
        await websocket.accept()
        self.active_connections[job_id] = websocket
        print(f"==DEBUG== WebSocket accepted and stored for job_id: {job_id}")
        print(f"==DEBUG== Active connections: {list(self.active_connections.keys())}")
        
    def disconnect(self, job_id: str):
        if job_id in self.active_connections:
            print(f"==DEBUG== Removing connection for job_id: {job_id}")
            self.active_connections.pop(job_id)
            print(f"==DEBUG== Remaining connections: {list(self.active_connections.keys())}")
        
    async def send_update(self, job_id: str, message: Dict):
        print(f"==DEBUG== send_update called for job_id: {job_id}")
        print(f"==DEBUG== Update status: {message.get('status')}")
        if job_id in self.active_connections:
            websocket = self.active_connections[job_id]
            try:
                print(f"==DEBUG== Sending update to job {job_id}: {message.get('status')}")
                print(f"==DEBUG== Message full content: {json.dumps(message)[:200]}...")
                await websocket.send_json(message)
                print(f"==DEBUG== Update sent successfully to job {job_id}")
                return True
            except Exception as e:
                print(f"==DEBUG== Error sending update to job {job_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                # If there's an error, remove the connection
                self.disconnect(job_id)
                return False
        else:
            print(f"==DEBUG== No active connection for job_id: {job_id}")
            return False

    async def send_personal_message(self, message: dict, job_id: str):
        """Send a message to a specific client by job_id if they're connected."""
        print(f"==DEBUG== send_personal_message called for job_id: {job_id}")
        print(f"==DEBUG== Message type: {message.get('status')}")
        
        if job_id in self.active_connections:
            websocket = self.active_connections[job_id]
            try:
                print(f"==DEBUG== Sending message to {job_id}: {message.get('status')}")
                await websocket.send_json(message)
                print(f"==DEBUG== Message sent successfully to {job_id}")
            except Exception as e:
                print(f"==DEBUG== Error sending message to {job_id}: {str(e)}")
                self.disconnect(job_id)
        else:
            print(f"==DEBUG== Cannot send message - job_id {job_id} not connected")
                
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        print(f"==DEBUG== broadcast called")
        print(f"==DEBUG== Message type: {message.get('status')}")
        disconnected_clients = []
        for job_id, connection in self.active_connections.items():
            try:
                print(f"==DEBUG== Broadcasting to {job_id}: {message.get('status')}")
                await connection.send_json(message)
            except Exception as e:
                print(f"==DEBUG== Error broadcasting to {job_id}: {str(e)}")
                disconnected_clients.append(job_id)
                
        # Clean up any disconnected clients
        for job_id in disconnected_clients:
            self.disconnect(job_id)

# Initialize connection manager
manager = ConnectionManager()

# File system event handler for log file changes
class LogFileHandler(FileSystemEventHandler):
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.processed_files = set()
        
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)
            
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)
            
    def process_file(self, file_path):
        if file_path in self.processed_files:
            return
            
        # Only process files that appear to be API response logs
        # Relax the filtering to catch more log types
        if 'api_response' in file_path and '.json' in file_path:
            try:
                print(f"Processing potential API response log: {file_path}")
                with open(file_path, 'r') as f:
                    log_data = json.load(f)
                    
                role = log_data.get('role')
                status = log_data.get('status')
                response_data = log_data.get('response', {})
                choices = response_data.get('choices', [])
                
                print(f"Log data - role: {role}, status: {status}, has choices: {bool(choices)}")
                
                if choices and len(choices) > 0 and role:
                    message = choices[0].get('message', {})
                    content = message.get('content', '')
                    
                    if content:
                        # Map the role to an output key
                        role_to_output = {
                            "requirements_analysis": "requirements_analysis",
                            "domain_expert": "domain_expert_review",
                            "user_advocate": "user_experience_review",
                            "technical_lead": "technical_review",
                            "architect": "architecture_design",
                            "developer": "implementation",
                            "qa_engineer": "testing_plan",
                            "security_expert": "security_review",
                            "code_reviewer": "code_review"
                        }
                        
                        output_key = role_to_output.get(role, role)
                        
                        # Queue the update to be sent via WebSocket
                        print(f"Sending WebSocket message for {role} in job {self.job_id}")
                        asyncio.create_task(manager.send_update(self.job_id, {
                            "type": "model_response",
                            "status": "in_progress",
                            "role": role,
                            "output_key": output_key,
                            "content": content
                        }))
                        
                        self.processed_files.add(file_path)
                        print(f"Processed new response for {role} in job {self.job_id}")
                    else:
                        # For log files in the main log directory with a different structure
                        if not content and 'response' in log_data:
                            print(f"==DEBUG== Found log file with response field: {filepath}")
                            try:
                                if isinstance(log_data['response'], dict) and 'choices' in log_data['response']:
                                    choices = log_data['response']['choices']
                                    print(f"==DEBUG== Found choices in response: {len(choices) if choices else 0}")
                                    
                                    if choices and isinstance(choices, list) and len(choices) > 0:
                                        first_choice = choices[0]
                                        print(f"==DEBUG== Examining first choice: {first_choice.keys() if isinstance(first_choice, dict) else 'not a dict'}")
                                        
                                        if 'message' in first_choice and isinstance(first_choice['message'], dict):
                                            message = first_choice['message']
                                            print(f"==DEBUG== Found message in choice: {message.keys() if isinstance(message, dict) else 'not a dict'}")
                                            
                                            if 'content' in message and message['content']:
                                                content = message['content']
                                                print(f"==DEBUG== Extracted content from message: {content[:50]}...")
                                                
                                                # Use the role from the log file if available
                                                if role == 'system' and 'role' in log_data:
                                                    role = log_data['role']
                                                    print(f"==DEBUG== Using role from log_data: {role}")
                                                
                                                # Map the role to an output key
                                                role_to_output = {
                                                    "requirements_analysis": "requirements_analysis",
                                                    "domain_expert": "domain_expert_review",
                                                    "user_advocate": "user_experience_review",
                                                    "technical_lead": "technical_review",
                                                    "architect": "architecture_design",
                                                    "developer": "implementation",
                                                    "qa_engineer": "testing_plan",
                                                    "security_expert": "security_review",
                                                    "code_reviewer": "code_review"
                                                }
                                                
                                                output_key = role_to_output.get(role, role)
                                                
                                                # Queue the update to be sent via WebSocket
                                                print(f"Sending WebSocket message for {role} in job {self.job_id}")
                                                asyncio.create_task(manager.send_update(self.job_id, {
                                                    "type": "model_response",
                                                    "status": "in_progress",
                                                    "role": role,
                                                    "output_key": output_key,
                                                    "content": content
                                                }))
                                                
                                                self.processed_files.add(file_path)
                                                print(f"Processed new response for {role} in job {self.job_id}")
                            except Exception as e:
                                print(f"==DEBUG== Error parsing nested response: {str(e)}")
                else:
                    print(f"No valid choices or role found in log data")
            except Exception as e:
                print(f"Error processing log file {file_path}: {str(e)}")
                import traceback
                traceback.print_exc()

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
logs_dir = os.path.join(root_dir, "logs")
workspace_dir = os.path.join(root_dir, "workspace")
images_dir = os.path.join(current_dir, "images")
logs_pattern = os.path.join(logs_dir, "*.json")
workspace_pattern = os.path.join(workspace_dir, "**/*.json")
js_dir = os.path.join(current_dir, "js")
css_dir = os.path.join(current_dir, "css")
workflows_dir = os.path.join(root_dir, "workflows")
config_dir = os.path.join(root_dir, "config")
roles_dir = os.path.join(root_dir, "roles")

# Set up log directory
logs_dir = os.path.join(root_dir, "logs")

# Create directories if they don't exist
os.makedirs(workflows_dir, exist_ok=True)
os.makedirs(config_dir, exist_ok=True)
os.makedirs(roles_dir, exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)

# Image and asset directories
js_dir = os.path.join(current_dir, "js")
css_dir = os.path.join(current_dir, "css")
images_dir = os.path.join(current_dir, "images")

# Ensure directories exist
os.makedirs(js_dir, exist_ok=True)
os.makedirs(css_dir, exist_ok=True)
os.makedirs(images_dir, exist_ok=True)

# Mount static files
app.mount("/visualization", StaticFiles(directory=current_dir), name="visualization")

# Mount specific directories explicitly for better accessibility
app.mount("/js", StaticFiles(directory=js_dir), name="js")
app.mount("/css", StaticFiles(directory=css_dir), name="css")
app.mount("/images", StaticFiles(directory=images_dir), name="images")

# For serving the workspace directory
app.mount("/workspace", StaticFiles(directory=workspace_dir), name="workspace")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Redirect to the visualization page
    html_file = os.path.join(current_dir, "index.html")
    with open(html_file, "r") as f:
        content = f.read()
    return HTMLResponse(content=content)
    
@app.get("/config", response_class=HTMLResponse)
async def config_page():
    # Serve the configuration page
    html_file = os.path.join(current_dir, "config.html")
    with open(html_file, "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

# MetaGPT API endpoints
@app.post("/api/run_metagpt")
async def run_metagpt(prompt_request: PromptRequest, background_tasks: BackgroundTasks):
    try:
        # Generate a unique job ID
        job_id = f"job_{int(time.time())}_{os.urandom(4).hex()}"
        
        # Create job directory in logs
        job_dir = os.path.join(logs_dir, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # If no workflow file is specified, use the default collaborative workflow
        if not prompt_request.workflow_file:
            default_workflow_path = os.path.join(root_dir, "workflows", "collaborative_workflow.yml")
            if os.path.exists(default_workflow_path):
                prompt_request.workflow_file = "collaborative_workflow.yml"
                print(f"Using default workflow: {prompt_request.workflow_file}")
        
        # Create initial job status
        job_status = {
            "id": job_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "prompt": prompt_request.prompt,
            "workflow": prompt_request.workflow_file,
            "completed_models": [],
            "results": {}
        }
        
        # Save job status
        job_file = os.path.join(logs_dir, f"{job_id}_status.json")
        with open(job_file, "w") as f:
            json.dump(job_status, f, indent=2)
        
        # Start file watcher for this job
        event_handler = LogFileHandler(job_id)
        observer = Observer()
        observer.schedule(event_handler, logs_dir, recursive=True)
        observer.schedule(event_handler, workspace_dir, recursive=True)
        observer.start()
        
        # Process the request in background
        background_tasks.add_task(
            process_metagpt_request,
            job_id=job_id,
            prompt_request=prompt_request,
            job_file=job_file,
            observer=observer
        )
        
        return {
            "status": "accepted",
            "job_id": job_id,
            "message": "Job started. Connect to WebSocket for real-time updates."
        }
        
    except Exception as e:
        print(f"Error starting job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting job: {str(e)}")

# Background processing function for MetaGPT requests
async def process_metagpt_request(job_id: str, prompt_request: PromptRequest, job_file: str, observer: Observer):
    try:
        # Update job status to processing
        with open(job_file, "r") as f:
            job_status = json.load(f)
        
        job_status["status"] = "processing"
        job_status["started_at"] = datetime.now().isoformat()
        
        with open(job_file, "w") as f:
            json.dump(job_status, f, indent=2)
        
        # Notify clients of status change
        await manager.send_update(job_id, {
            "type": "status_update",
            "status": "processing",
            "message": "Job is now processing"
        })
        
        # Forward the request to the MetaGPT API container
        import requests
        
        # Create request payload
        payload = {
            "prompt": prompt_request.prompt,
        }
        
        # Add workflow_file if specified
        if prompt_request.workflow_file:
            payload["workflow_file"] = prompt_request.workflow_file
        
        # Add config_file if specified
        if prompt_request.config_file:
            payload["config_file"] = prompt_request.config_file
        
        # Log the request
        print(f"Processing job {job_id} with payload: {payload}")
        
        # Try multiple API endpoints with long timeout (120 seconds)
        api_endpoints = [
            "http://metagpt-api:8000/api/run_metagpt",  # Docker service name
            "http://localhost:8000/api/run_metagpt",    # Local development
            "http://127.0.0.1:8000/api/run_metagpt",    # Alternative local
            "http://host.docker.internal:8000/api/run_metagpt"  # Docker to host
        ]
        
        response = None
        error_messages = []
        
        for api_url in api_endpoints:
            try:
                print(f"Trying API endpoint: {api_url}")
                
                # Make request with long timeout
                response = requests.post(api_url, json=payload, timeout=120)
                
                if response.status_code == 200:
                    print(f"Successfully connected to {api_url}")
                    break
                else:
                    error_message = f"API returned status code {response.status_code}: {response.text}"
                    error_messages.append(error_message)
                    print(error_message)
            except requests.exceptions.RequestException as e:
                error_message = f"Failed to connect to {api_url}: {str(e)}"
                error_messages.append(error_message)
                print(error_message)
        
        # If all endpoints failed
        if not response or response.status_code != 200:
            error_details = "; ".join(error_messages)
            raise Exception(f"Failed to connect to any API endpoint: {error_details}")
        
        # Process the API response
        api_result = response.json()
        
        # Update job status with results
        with open(job_file, "r") as f:
            job_status = json.load(f)
        
        job_status["status"] = "completed"
        job_status["completed_at"] = datetime.now().isoformat()
        
        # Add results from the API response if they exist
        if "result" in api_result:
            job_status["results"] = api_result["result"]
        
        # If not, try to build results from logs
        else:
            job_status["results"] = build_results_from_logs(job_id)
        
        with open(job_file, "w") as f:
            json.dump(job_status, f, indent=2)
        
        # Notify clients of completion
        await manager.send_update(job_id, {
            "type": "status_update",
            "status": "completed",
            "message": "Job completed successfully",
            "results": job_status["results"]
        })
        
    except Exception as e:
        # Update job status to failed
        try:
            with open(job_file, "r") as f:
                job_status = json.load(f)
            
            job_status["status"] = "failed"
            job_status["error"] = str(e)
            job_status["failed_at"] = datetime.now().isoformat()
            
            with open(job_file, "w") as f:
                json.dump(job_status, f, indent=2)
            
            # Notify clients of failure
            await manager.send_update(job_id, {
                "type": "status_update",
                "status": "failed",
                "message": f"Job failed: {str(e)}"
            })
        except Exception as inner_e:
            print(f"Error updating job status: {str(inner_e)}")
    
    finally:
        # Stop the observer
        if observer:
            observer.stop()
            observer.join()

# Function to build results from log files
def build_results_from_logs(job_id: str) -> Dict[str, Any]:
    results = {}
    
    # Get all successful API response logs for this job
    success_logs = glob.glob(os.path.join(logs_dir, f"*{job_id}*success*.json"))
    
    for log_file in success_logs:
        try:
            with open(log_file, 'r') as f:
                log_data = json.load(f)
            
            role = log_data.get("role")
            response_data = log_data.get("response", {})
            choices = response_data.get("choices", [])
            
            if role and choices and len(choices) > 0:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                
                if content:
                    # Map the role to an output key based on reverse of OUTPUT_TO_ROLE_MAP
                    # Using common role to output key mappings
                    role_to_output = {
                        "requirements_analysis": "requirements_analysis",
                        "domain_expert": "domain_expert_review",
                        "user_advocate": "user_experience_review",
                        "technical_lead": "technical_review",
                        "architect": "architecture_design",
                        "developer": "implementation",
                        "qa_engineer": "testing_plan",
                        "security_expert": "security_review",
                        "code_reviewer": "code_review"
                    }
                    
                    output_key = role_to_output.get(role, role)
                    results[output_key] = content
        except Exception as e:
            print(f"Error processing log file {log_file}: {str(e)}")
    
    return results

@app.post("/api/run_metagpt_default")
async def run_metagpt_default(background_tasks: BackgroundTasks):
    # Use a default sample prompt - make it a simple TinyML prompt since that's what was shown in user's terminal
    default_prompt = "Develop a TinyML model to maintain predictions with vibration for a motor using a Raspberry Pi 4 and Google Coral Accelerator"
    
    # Create a PromptRequest with the default prompt
    prompt_request = PromptRequest(prompt=default_prompt)
    
    # Call the run_metagpt function
    return await run_metagpt(prompt_request, background_tasks)

@app.get("/api/get_output")
async def get_output():
    """Get the latest MetaGPT output.json file from the workspace."""
    try:
        # First, check if standard output.json exists in any workspace directory
        workspace_dirs = sorted(
            [d for d in os.listdir(workspace_dir) if d.startswith("workspace_")],
            key=lambda x: os.path.getmtime(os.path.join(workspace_dir, x)),
            reverse=True
        )
        
        # Check most recent workspace directories first
        for workspace in workspace_dirs:
            output_path = os.path.join(workspace_dir, workspace, "output.json")
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    return json.load(f)
        
        # If output.json not found, try to build a response from individual API logs
        print("Output.json not found. Attempting to build from API response logs...")
        
        # Get all successful API response logs
        success_logs = glob.glob(os.path.join(logs_dir, "*success*.json"))
        if not success_logs:
            return {"status": "error", "error": "No output file or API response logs found"}
        
        # Get the most recent logs, grouped by role
        success_logs.sort(key=os.path.getmtime, reverse=True)
        
        # Build a combined result from logs
        result = {}
        used_roles = set()
        
        for log_file in success_logs:
            try:
                with open(log_file, "r") as f:
                    log_data = json.load(f)
                    
                role = log_data.get("role")
                if role and role not in used_roles:
                    # Extract the content from the response
                    response_data = log_data.get("response", {})
                    choices = response_data.get("choices", [])
                    
                    if choices and len(choices) > 0:
                        message = choices[0].get("message", {})
                        content = message.get("content", "")
                        
                        if content:
                            # Map the role to an output key based on reverse of OUTPUT_TO_ROLE_MAP
                            # Using common role to output key mappings
                            role_to_output = {
                                "requirements_analysis": "requirements_analysis",
                                "domain_expert": "domain_expert_review",
                                "user_advocate": "user_experience_review",
                                "technical_lead": "technical_review",
                                "architect": "architecture_design",
                                "developer": "implementation",
                                "qa_engineer": "testing_plan",
                                "security_expert": "security_review",
                                "code_reviewer": "code_review"
                            }
                            
                            output_key = role_to_output.get(role, role)
                            result[output_key] = content
                            used_roles.add(role)
                    
            except Exception as e:
                print(f"Error processing log file {log_file}: {str(e)}")
                continue
        
        if not result:
            return {"status": "error", "error": "No valid response content found in logs"}
            
        # Create a sample output file for easier loading next time
        sample_output_path = os.path.join(current_dir, "sample_output.json")
        try:
            with open(sample_output_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Created sample output file at {sample_output_path}")
        except Exception as e:
            print(f"Failed to write sample output file: {str(e)}")
        
        return {"status": "success", "result": result}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/upload/{file_type}")
async def upload_file(file_type: str, file: UploadFile = File(...)):
    """Upload configuration files"""
    try:
        if file_type not in ["workflow", "config", "role"]:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
            
        # Determine target directory
        if file_type == "workflow":
            target_dir = workflows_dir
        elif file_type == "config":
            target_dir = config_dir
        else:  # role
            target_dir = roles_dir
            
        # Validate file extension
        if not file.filename.endswith((".yml", ".yaml")):
            raise HTTPException(status_code=400, detail="Only YAML files are supported")
            
        # Write file to target directory
        file_path = os.path.join(target_dir, file.filename)
        content = await file.read()
        
        # Basic validation of YAML content
        try:
            import yaml
            yaml_content = yaml.safe_load(content)
            if not isinstance(yaml_content, dict):
                raise HTTPException(status_code=400, detail="Invalid YAML format - must be a dictionary/object")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML content: {str(e)}")
            
        # Write file
        with open(file_path, "wb") as f:
            f.write(content)
            
        return {"success": True, "filename": file.filename}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/api/files/{file_type}")
async def list_files(file_type: str):
    """List available configuration files"""
    try:
        if file_type not in ["workflow", "config", "role"]:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
            
        # Determine target directory
        if file_type == "workflow":
            target_dir = workflows_dir
        elif file_type == "config":
            target_dir = config_dir
        else:  # role
            target_dir = roles_dir
            
        # List YAML files
        files = []
        for filename in os.listdir(target_dir):
            if filename.endswith((".yml", ".yaml")):
                file_path = os.path.join(target_dir, filename)
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
                
        return files
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@app.delete("/api/files/{file_type}/{filename}")
async def delete_file(file_type: str, filename: str):
    """Delete a configuration file"""
    try:
        if file_type not in ["workflow", "config", "role"]:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
            
        # Determine target directory
        if file_type == "workflow":
            target_dir = workflows_dir
        elif file_type == "config":
            target_dir = config_dir
        else:  # role
            target_dir = roles_dir
            
        # Check file exists
        file_path = os.path.join(target_dir, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
            
        # Delete file
        os.remove(file_path)
        return {"success": True, "filename": filename}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

# Run MetaGPT with selected workflow and config
@app.post("/api/run_with_config")
async def run_with_config(request: Request, background_tasks: BackgroundTasks):
    """Run MetaGPT with specific workflow and config files"""
    try:
        data = await request.json()
        workflow_file = data.get("workflow_file")
        config_file = data.get("config_file")
        prompt = data.get("prompt")
        api_key = data.get("api_key")  # Get API key from request
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
            
        # Build API request to metagpt-api
        api_url = "http://metagpt-api:8000/api/run_metagpt"
        payload = {
            "prompt": prompt,
            "workflow_file": workflow_file,
            "config_file": config_file
        }
        
        # Add API key to payload if provided
        if api_key:
            payload["api_key"] = api_key
            print("Using API key from request payload")
        
        # Generate a job ID for tracking
        job_id = f"job_{int(time.time())}"
        
        # Run the API request in the background
        background_tasks.add_task(run_job_in_background, api_url, payload, job_id)
        
        # Return immediately with the job ID for WebSocket connection
        return {"status": "job_started", "job_id": job_id, "message": "Job started. Connect to WebSocket for updates."}
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error in run_with_config: {str(e)}")
        
        # Create error log file for debugging
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_log_path = os.path.join(logs_dir, f"api_response_error_config_{timestamp}.json")
            with open(error_log_path, "w") as f:
                json.dump({
                    "error": str(e),
                    "timestamp": timestamp,
                    "request_data": str(await request.json()) if await request.body() else None
                }, f, indent=4)
            print(f"Created error log file at {error_log_path}")
        except:
            pass
            
        raise HTTPException(status_code=500, detail=str(e))

async def run_job_in_background(api_url, payload, job_id):
    """Run a job in the background and manage its WebSocket connection"""
    print(f"Starting background job {job_id}")
    
    try:
        # Send initial status update if the WebSocket is connected
        if job_id in manager.active_connections:
            await manager.send_update(job_id, {
                "status": "update",
                "message": "Sending request to MetaGPT API..."
            })
        
        # Make API request with error handling
        import requests
        
        # Attempt the API request with multiple fallback options
        response = None
        error_message = None
        
        try:
            # Try the service name first (for Docker networking)
            print(f"Making API request to {api_url}")
            
            # Send update about request being made
            if job_id in manager.active_connections:
                await manager.send_update(job_id, {
                    "status": "update",
                    "message": "Starting MetaGPT job processing..."
                })
            
            # Use a shorter timeout (15 seconds) for the initial request
            # The Docker container networking can sometimes be slow to establish
            response = requests.post(api_url, json=payload, timeout=15)
            print(f"API response status: {response.status_code}")
        except requests.exceptions.Timeout:
            error_message = f"Request to {api_url} timed out"
            print(error_message)
            
            # Try alternative URLs with different timeout
            print("Request timed out. Trying alternative endpoints...")
            alternative_urls = [
                "http://localhost:8000/api/run_metagpt",  # For local development
                "http://127.0.0.1:8000/api/run_metagpt",  # Alternative local IP
                "http://host.docker.internal:8000/api/run_metagpt"  # Special Docker DNS for host machine
            ]
            
            for alt_url in alternative_urls:
                try:
                    print(f"Trying alternative API endpoint: {alt_url}")
                    # Use a shorter timeout for fallback attempts
                    response = requests.post(alt_url, json=payload, timeout=10)
                    print(f"Successfully connected to {alt_url}")
                    error_message = None  # Clear the error since we succeeded
                    break
                except requests.exceptions.RequestException as e:
                    print(f"Failed to connect to {alt_url}: {str(e)}")
                    continue
            
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error to {api_url}: {str(e)}")
            # If that fails, try alternative ways to connect
            alternative_urls = [
                "http://localhost:8000/api/run_metagpt",  # For local development
                "http://127.0.0.1:8000/api/run_metagpt",  # Alternative local IP
                "http://host.docker.internal:8000/api/run_metagpt"  # Special Docker DNS for host machine
            ]
            
            # Log the connection failure and try alternatives
            print(f"Connection to {api_url} failed. Trying alternative endpoints...")
            
            for alt_url in alternative_urls:
                try:
                    print(f"Trying alternative API endpoint: {alt_url}")
                    response = requests.post(alt_url, json=payload, timeout=10)
                    print(f"Successfully connected to {alt_url}")
                    error_message = None  # Clear the error since we succeeded
                    break
                except requests.exceptions.RequestException as e:
                    print(f"Failed to connect to {alt_url}: {str(e)}")
                    continue
            
            if not response and not error_message:
                error_message = "Failed to connect to any API endpoint"
                print(error_message)
                
        except Exception as e:
            error_message = f"Unexpected error making request: {str(e)}"
            print(error_message)
        
        # Handle API response or error
        if error_message:
            print(f"Sending error message to client: {error_message}")
            # Send error to WebSocket client
            if job_id in manager.active_connections:
                await manager.send_update(job_id, {
                    "status": "error",
                    "error": error_message
                })
            return
        
        # Check response status code
        if not response or response.status_code != 200:
            error_text = response.text if response else "No response"
            error_message = f"MetaGPT API error: {error_text}"
            print(error_message)
            
            # Send error to WebSocket client
            if job_id in manager.active_connections:
                await manager.send_update(job_id, {
                    "status": "error",
                    "error": error_message
                })
            return
        
        # Successfully started the job in the API container
        try:
            result = response.json()
            print(f"MetaGPT job started successfully: {result}")
        except Exception as e:
            error_message = f"Failed to parse API response: {str(e)}, Raw response: {response.text[:100]}"
            print(error_message)
            
            # Send error to WebSocket client
            if job_id in manager.active_connections:
                await manager.send_update(job_id, {
                    "status": "error",
                    "error": error_message
                })
            return
        
        # Notify the client that the job has started
        if job_id in manager.active_connections:
            await manager.send_update(job_id, {
                "status": "update",
                "message": "Job submitted to MetaGPT, workspace created. Starting processing...",
                "job_details": result
            })
            
        # Set up log monitoring for this job
        workspace_monitor_task = None
        try:
            # Extract workspace ID from response or generate based on job ID
            workspace_id = result.get('workspace_id', f"workspace_{job_id}")
            
            # Set up paths to monitor for log files
            print(f"Setting up log monitoring for job {job_id}")
            # Start a background task to monitor both logs directory and workspace directory
            workspace_monitor_task = asyncio.create_task(monitor_workspace_files(job_id, workspace_id))
            print(f"Log monitoring started for job {job_id}")
        except Exception as e:
            print(f"Error setting up log monitoring: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # The job is running in the API container, so we just periodically check and wait
        # for a reasonable time before telling the client it's running in the background
        wait_count = 0
        while wait_count < 20 and job_id in manager.active_connections:
            # Send periodic updates to keep the client informed
            if wait_count % 5 == 0 and job_id in manager.active_connections:
                await manager.send_update(job_id, {
                    "status": "update",
                    "message": f"MetaGPT processing... (waited {wait_count*2} seconds)"
                })
            
            # Sleep for 2 seconds
            await asyncio.sleep(2)
            wait_count += 1
        
        # If we still have a connection after waiting, send a final update
        if job_id in manager.active_connections:
            await manager.send_update(job_id, {
                "status": "update",
                "message": "MetaGPT job is running in the background. Results will update automatically when available."
            })
            
        # Wait for the monitor task to complete (this will run indefinitely until the WebSocket disconnects)
        if workspace_monitor_task:
            try:
                # We don't actually wait for it to complete, as it will run until the WebSocket disconnects
                # This is just to keep a reference to the task so it doesn't get garbage collected
                print(f"Workspace monitoring task is running for job {job_id}")
            except Exception as e:
                print(f"Error in workspace monitoring task: {str(e)}")
            
    except Exception as e:
        error_message = f"Error in background job: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc()
        
        # Send error to WebSocket if it's connected
        if job_id in manager.active_connections:
            await manager.send_update(job_id, {
                "status": "error",
                "error": error_message
            })

async def monitor_workspace_files(job_id, workspace_id):
    """Monitor workspace files for changes and send updates via WebSocket."""
    print(f"Starting workspace file monitoring for job {job_id}, workspace {workspace_id}")
    
    # Define the paths to monitor
    logs_dir = "/logs"  # Main logs directory
    workspace_dir = f"/workspace/{workspace_id}"  # Job-specific workspace
    workspace_logs_dir = f"{workspace_dir}/logs"  # Job-specific logs directory
    
    print(f"Monitoring directories for job {job_id}:")
    print(f"  - Main logs: {logs_dir}")
    print(f"  - Workspace: {workspace_dir}")
    print(f"  - Workspace logs: {workspace_logs_dir}")
    
    # Track processed files to avoid duplicates
    processed_files = set()
    
    # Track if any message has been sent to the client
    message_sent = False
    
    try:
        # Initial scan of existing files
        print(f"==DEBUG== Performing initial scan for job {job_id}")
        
        # Create necessary directories if they don't exist
        for directory in [workspace_dir, workspace_logs_dir]:
            try:
                os.makedirs(directory, exist_ok=True)
                print(f"==DEBUG== Created directory: {directory}")
            except Exception as e:
                print(f"==DEBUG== Error creating directory {directory}: {str(e)}")
        
        # Main monitoring loop
        check_count = 0
        while job_id in manager.active_connections:
            try:
                check_count += 1
                # Check for new logs in workspace logs directory
                new_logs = []
                
                # First check the workspace logs directory
                if os.path.exists(workspace_logs_dir):
                    if check_count % 10 == 0:  # Reduce log spam
                        print(f"==DEBUG== Checking {workspace_logs_dir} for new files")
                    for filename in os.listdir(workspace_logs_dir):
                        if filename.endswith(".json"):
                            filepath = os.path.join(workspace_logs_dir, filename)
                            if filepath not in processed_files:
                                print(f"==DEBUG== Found new log file: {filepath}")
                                new_logs.append(filepath)
                
                # Also check the main logs directory
                if os.path.exists(logs_dir):
                    if check_count % 10 == 0:  # Reduce log spam
                        print(f"==DEBUG== Checking {logs_dir} for new files")
                    for filename in os.listdir(logs_dir):
                        if filename.endswith(".json") and job_id in filename:
                            filepath = os.path.join(logs_dir, filename)
                            if filepath not in processed_files:
                                print(f"==DEBUG== Found new log file: {filepath}")
                                new_logs.append(filepath)
                
                # Process any new log files
                for filepath in new_logs:
                    try:
                        print(f"==DEBUG== Processing log file: {filepath}")
                        with open(filepath, 'r') as f:
                            log_data = json.load(f)
                        
                        # Extract content and role from the log data
                        role = log_data.get('role', 'system')
                        content = log_data.get('content', '')
                        
                        # For API response log files with a different structure
                        if not content and 'response' in log_data:
                            print(f"==DEBUG== Found API response log file: {filepath}")
                            
                            try:
                                response = log_data['response']
                                if isinstance(response, dict) and 'choices' in response:
                                    choices = response['choices']
                                    print(f"==DEBUG== Found {len(choices) if choices else 0} choices in response")
                                    
                                    if choices and isinstance(choices, list) and len(choices) > 0:
                                        choice = choices[0]
                                        print(f"==DEBUG== Examining first choice")
                                        
                                        if isinstance(choice, dict) and 'message' in choice:
                                            message = choice['message']
                                            print(f"==DEBUG== Found message in choice")
                                            
                                            if isinstance(message, dict) and 'content' in message:
                                                content = message['content']
                                                print(f"==DEBUG== Extracted content from message ({len(content)} chars)")
                                
                                # Use the role from the log file if available
                                if role == 'system' and 'role' in log_data:
                                    role = log_data['role']
                                    print(f"==DEBUG== Using role from log file: {role}")
                            except Exception as e:
                                print(f"==DEBUG== Error extracting content from API response: {str(e)}")
                                import traceback
                                traceback.print_exc()
                        
                        if content:
                            print(f"==DEBUG== Sending content update for role: {role}")
                            # Send the update with the extracted content
                            update_success = await manager.send_update(job_id, {
                                "status": "update",
                                "role": role,
                                "content": content,
                                "message": f"Received message from {role}",
                                "timestamp": time.time()
                            })
                            
                            if update_success:
                                print(f"==DEBUG== Update sent successfully for {filepath}")
                                message_sent = True
                            else:
                                print(f"==DEBUG== Failed to send update for {filepath} - WebSocket might be disconnected")
                        else:
                            print(f"==DEBUG== No content found in {filepath}")
                        
                        # Mark as processed regardless of content
                        processed_files.add(filepath)
                        
                    except json.JSONDecodeError as e:
                        print(f"==DEBUG== JSON decode error for {filepath}: {str(e)}")
                    except Exception as e:
                        print(f"==DEBUG== Error processing log file {filepath}: {str(e)}")
                
                # Check for output.json in the workspace directory
                output_path = os.path.join(workspace_dir, "output.json")
                if os.path.exists(output_path) and output_path not in processed_files:
                    try:
                        print(f"==DEBUG== Processing output file: {output_path}")
                        with open(output_path, 'r') as f:
                            output_data = json.load(f)
                        
                        # If output_data is a list, send each item as a separate message
                        if isinstance(output_data, list):
                            for item in output_data:
                                role = item.get('role', 'system')
                                content = item.get('content', '')
                                
                                if content:
                                    print(f"==DEBUG== Sending output content update for role: {role}")
                                    update_success = await manager.send_update(job_id, {
                                        "status": "update",
                                        "role": role,
                                        "content": content,
                                        "message": f"Received message from {role}",
                                        "timestamp": time.time()
                                    })
                                    
                                    if update_success:
                                        message_sent = True
                        
                        # Mark as processed
                        processed_files.add(output_path)
                        
                    except json.JSONDecodeError as e:
                        print(f"==DEBUG== JSON decode error for {output_path}: {str(e)}")
                    except Exception as e:
                        print(f"==DEBUG== Error processing output file: {str(e)}")
                
                # Send a status update every 5 seconds if no messages have been sent
                if not message_sent and check_count % 10 == 0:
                    try:
                        print(f"==DEBUG== Sending status update for job {job_id}")
                        await manager.send_update(job_id, {
                            "status": "status",
                            "message": f"Monitoring files for job {job_id}...",
                            "timestamp": time.time()
                        })
                    except Exception as e:
                        print(f"==DEBUG== Error sending status update: {str(e)}")
                
                # Sleep for a shorter time before checking again (0.5 seconds instead of 1)
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"==DEBUG== Error in monitoring loop for {job_id}: {str(e)}")
                await asyncio.sleep(2)  # Longer sleep on error
    
    except asyncio.CancelledError:
        print(f"==DEBUG== File monitoring task for job {job_id} was cancelled")
    except Exception as e:
        print(f"==DEBUG== Unexpected error in file monitoring for {job_id}: {str(e)}")
        import traceback
        traceback.print_exc()

@app.get("/api/test_websocket/{job_id}")
async def test_websocket(job_id: str):
    """Test endpoint to send a message directly to a WebSocket client."""
    try:
        print(f"==DEBUG== Testing WebSocket for job_id: {job_id}")
        
        # Check if the job_id has an active WebSocket connection
        if job_id not in manager.active_connections:
            print(f"==DEBUG== No active WebSocket connection for job_id: {job_id}")
            return {"status": "error", "message": f"No active WebSocket connection for job_id: {job_id}"}
        
        # Create test messages
        test_messages = [
            {
                "status": "update",
                "role": "product_manager",
                "content": "# Test Message from Product Manager\n\nThis is a test message to verify that the WebSocket display works correctly.",
                "model": "test-model",
                "timestamp": datetime.now().isoformat()
            },
            {
                "status": "update",
                "role": "technical_lead",
                "content": "## Technical Lead Response\n\nConfirming that the WebSocket communication is working properly.",
                "model": "test-model",
                "timestamp": datetime.now().isoformat()
            },
            {
                "status": "update",
                "role": "engineer",
                "content": "```python\n# Code example\ndef test_function():\n    print('WebSocket display is working!')\n```",
                "model": "test-model",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        # Send test messages with a delay
        async def send_test_messages():
            for i, message in enumerate(test_messages):
                print(f"==DEBUG== Sending test message {i+1}/{len(test_messages)}")
                await manager.send_update(job_id, message)
                await asyncio.sleep(1)  # Small delay between messages
                
        # Start sending messages in the background
        asyncio.create_task(send_test_messages())
        
        return {"status": "success", "message": f"Sending test messages to WebSocket for job_id: {job_id}"}
    except Exception as e:
        print(f"==DEBUG== Error in test_websocket: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/api/logs/list")
async def list_logs(limit: int = 50):
    """List available API log files."""
    try:
        # Get all log files from the logs directory
        logs_pattern = os.path.join(logs_dir, "**/*.json")
        log_files_from_logs = glob.glob(logs_pattern, recursive=True)
        print(f"Found {len(log_files_from_logs)} log files in main logs directory")
        
        # Get all log files from the workspace directory
        workspace_pattern = os.path.join(workspace_dir, "**/*.json") 
        log_files_from_workspace = glob.glob(workspace_pattern, recursive=True)
        print(f"Found {len(log_files_from_workspace)} log files in workspace directories")
        
        # Combine all log files
        all_log_files = log_files_from_logs + log_files_from_workspace
        
        # Sort by modification time (newest first)
        all_log_files.sort(key=os.path.getmtime, reverse=True)
        
        # Limit the number of logs returned
        all_log_files = all_log_files[:limit]
        
        result = []
        for file_path in all_log_files:
            filename = os.path.basename(file_path)
            rel_path = os.path.relpath(file_path, root_dir)
            
            # Get file metadata
            stat = os.stat(file_path)
            file_size = stat.st_size
            created = stat.st_mtime
            
            # Initialize metadata
            model = "unknown"
            status = "unknown"
            role = "unknown"
            location = "logs" if file_path.startswith(logs_dir) else "workspace"
            
            try:
                # Try to extract info from the file content
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                        model = data.get('model', 'unknown')
                        status = data.get('status', 'unknown')
                        role = data.get('role', 'unknown')
                    except json.JSONDecodeError:
                        # If we can't parse JSON, try to extract from filename
                        if '_' in filename:
                            parts = filename.split('_')
                            if len(parts) >= 3:
                                if "success" in filename.lower():
                                    status = "success"
                                elif "error" in filename.lower():
                                    status = "error"
                                if "api_response" in filename.lower():
                                    model = parts[2] if len(parts) > 2 else "unknown"
            except Exception as e:
                print(f"Error processing log file {filename}: {str(e)}")
                # If we can't read the file, just use defaults
            
            result.append({
                "filename": filename,
                "filepath": file_path,  # Include full path for retrieval
                "rel_path": rel_path,   # Relative path for display
                "created": created,
                "size": file_size,
                "model": model,
                "role": role,
                "status": status,
                "location": location
            })
        
        return result
    except Exception as e:
        print(f"Error listing logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing logs: {str(e)}")

@app.get("/api/logs/view/{filename}")
async def view_log(filename: str):
    """View the content of a specific log file."""
    try:
        # First try to find the file directly by filename in the main logs directory
        file_path = os.path.join(logs_dir, filename)
        
        # If not found there, check workspace directories
        if not os.path.exists(file_path):
            print(f"Log file not found at {file_path}, searching in workspaces...")
            # Search in all workspace directories
            workspace_pattern = os.path.join(workspace_dir, "**/logs", filename)
            workspace_matches = glob.glob(workspace_pattern, recursive=True)
            
            # If found in workspace, use the first match
            if workspace_matches:
                file_path = workspace_matches[0]
                print(f"Found log file in workspace: {file_path}")
            else:
                # As a last resort, search for any file with this name anywhere in logs or workspace
                any_pattern = os.path.join(root_dir, "**", filename)
                any_matches = glob.glob(any_pattern, recursive=True)
                
                if any_matches:
                    file_path = any_matches[0]
                    print(f"Found log file elsewhere: {file_path}")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Log file {filename} not found")
        
        # Read and parse the log file
        with open(file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # If it's not valid JSON, return as text
                f.seek(0)
                content = f.read()
                return {"content": content, "format": "text"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error reading log file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

@app.get("/api/workflows")
async def list_workflows():
    """List available workflows and extract their participants"""
    try:
        workflow_files = []
        
        # If workflows directory doesn't exist, check if we have a default file to use
        if not os.path.exists(workflows_dir) or not os.listdir(workflows_dir):
            # Check for default workflow in the codebase
            default_workflow_path = os.path.join(root_dir, "workflows", "collaborative_workflow.yml")
            if os.path.exists(default_workflow_path):
                try:
                    with open(default_workflow_path, "r") as f:
                        workflow_data = yaml.safe_load(f)
                        
                    workflow_info = {
                        "filename": "collaborative.yml",
                        "name": workflow_data.get("name", "collaborative"),
                        "description": workflow_data.get("description", "Default collaborative workflow"),
                        "participants": []
                    }
                    
                    # Extract unique participants from all stages
                    all_participants = set()
                    stages = workflow_data.get("stages", [])
                    
                    for stage in stages:
                        stage_participants = stage.get("participants", [])
                        for participant in stage_participants:
                            role = participant.get("role", "")
                            if role and role not in all_participants:
                                all_participants.add(role)
                    
                    workflow_info["participants"] = sorted(list(all_participants))
                    workflow_files.append(workflow_info)
                except Exception as e:
                    print(f"Error parsing default workflow file: {str(e)}")
            
            # If we still don't have any workflows, return an empty list
            # We don't want to show hardcoded roles anymore
            if not workflow_files:
                return []
        
        # If the workflows directory exists, look for YAML files
        elif os.path.exists(workflows_dir):
            # List all YAML files in the workflows directory
            for filename in os.listdir(workflows_dir):
                if filename.endswith((".yml", ".yaml")):
                    file_path = os.path.join(workflows_dir, filename)
                    
                    # Extract workflow metadata and participants
                    try:
                        with open(file_path, "r") as f:
                            workflow_data = yaml.safe_load(f)
                            
                        workflow_info = {
                            "filename": filename,
                            "name": workflow_data.get("name", filename.split(".")[0]),
                            "description": workflow_data.get("description", ""),
                            "participants": []
                        }
                        
                        # Extract unique participants from all stages
                        all_participants = set()
                        stages = workflow_data.get("stages", [])
                        
                        for stage in stages:
                            stage_participants = stage.get("participants", [])
                            for participant in stage_participants:
                                role = participant.get("role", "")
                                if role and role not in all_participants:
                                    all_participants.add(role)
                        
                        workflow_info["participants"] = sorted(list(all_participants))
                        workflow_files.append(workflow_info)
                    except Exception as e:
                        print(f"Error parsing workflow file {filename}: {str(e)}")
        
        return workflow_files
    except Exception as e:
        print(f"Error in list_workflows: {str(e)}")
        # Return empty list instead of hardcoded fallback
        return []

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    print(f"==DEBUG== WebSocket connection attempt for job {job_id}")
    
    # Add better logging for the connection process
    print(f"==DEBUG== Active connections before connecting: {list(manager.active_connections.keys())}")
    
    try:
        await manager.connect(websocket, job_id)
        print(f"==DEBUG== WebSocket connected and registered for job: {job_id}")
        print(f"==DEBUG== Active connections after connecting: {list(manager.active_connections.keys())}")
        
        # Send initial connection confirmation
        try:
            await websocket.send_json({"status": "connected", "message": "WebSocket connection established"})
            print(f"==DEBUG== Sent initial connection confirmation to {job_id}")
        except Exception as e:
            print(f"==DEBUG== Error sending initial confirmation: {str(e)}")
        
        # Start ping task to keep connection alive
        ping_task = None
        try:
            async def send_periodic_pings():
                """Send periodic pings to keep WebSocket connection alive"""
                try:
                    while True:
                        if job_id not in manager.active_connections:
                            print(f"==DEBUG== Stopping ping task - connection for {job_id} closed")
                            break
                            
                        try:
                            await websocket.send_json({"status": "ping", "timestamp": time.time()})
                            print(f"==DEBUG== Sent ping to {job_id}")
                        except Exception as e:
                            print(f"==DEBUG== Error sending ping to {job_id}: {str(e)}")
                            break
                            
                        await asyncio.sleep(15)  # Send ping every 15 seconds
                except asyncio.CancelledError:
                    print(f"==DEBUG== Ping task for {job_id} was cancelled")
                except Exception as e:
                    print(f"==DEBUG== Error in ping task for {job_id}: {str(e)}")
            
            # Start ping task
            ping_task = asyncio.create_task(send_periodic_pings())
            print(f"==DEBUG== Started ping task for {job_id}")
        except Exception as e:
            print(f"==DEBUG== Error starting ping task: {str(e)}")
        
        # Start a monitor task for this job immediately - this will run in background
        monitor_task = None
        try:
            # Generate workspace ID based on job ID
            workspace_id = f"workspace_{job_id}"
            print(f"==DEBUG== Starting file monitoring for job {job_id}, workspace {workspace_id}")
            monitor_task = asyncio.create_task(monitor_workspace_files(job_id, workspace_id))
        except Exception as e:
            print(f"==DEBUG== Error starting monitor task: {str(e)}")
        
        # Main WebSocket message processing loop
        try:
            while True:
                # Wait for any message from the client
                try:
                    data = await websocket.receive_json()
                    print(f"==DEBUG== Received message from job {job_id}: {data}")
                    
                    # Handle ping messages to keep connection alive
                    if data.get("type") == "ping" or data.get("action") == "ping":
                        await websocket.send_json({"status": "ping", "message": "pong"})
                        print(f"==DEBUG== Sent ping response to {job_id}")
                        
                except WebSocketDisconnect:
                    print(f"==DEBUG== WebSocket disconnected during receive for job {job_id}")
                    break
                except Exception as e:
                    print(f"==DEBUG== Error receiving message from job {job_id}: {str(e)}")
                    # Log but continue - don't break the loop for message errors
                    continue
                    
        except Exception as e:
            print(f"==DEBUG== Error in WebSocket processing loop for job {job_id}: {str(e)}")
                
    except WebSocketDisconnect:
        print(f"==DEBUG== WebSocket disconnected for job {job_id}")
        manager.disconnect(job_id)
    except Exception as e:
        print(f"==DEBUG== WebSocket error for job {job_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        manager.disconnect(job_id)
    finally:
        # Cancel any running tasks
        if 'ping_task' in locals() and ping_task is not None:
            ping_task.cancel()
            print(f"==DEBUG== Cancelled ping task for {job_id}")
            
        if 'monitor_task' in locals() and monitor_task is not None:
            monitor_task.cancel()
            print(f"==DEBUG== Cancelled monitor task for {job_id}")
            
        # Make sure we always disconnect if the loop exits
        print(f"==DEBUG== WebSocket connection ended for job {job_id}")
        manager.disconnect(job_id)

if __name__ == "__main__":
    print(f"Visualization server running at http://localhost:8088")
    print(f"Open your browser to view the MetaGPT conversation visualization")
    uvicorn.run(app, host="0.0.0.0", port=8088)
