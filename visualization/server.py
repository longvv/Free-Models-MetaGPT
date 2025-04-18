import os
import uvicorn
import subprocess
import sys
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, List, Optional
import json
from pathlib import Path
from pydantic import BaseModel
import shutil
import time

# Define request models
class PromptRequest(BaseModel):
    prompt: str
    workflow_file: Optional[str] = None
    config_file: Optional[str] = None

# Create FastAPI app
app = FastAPI(title="MetaGPT Chat Visualization")

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
workspace_dir = os.path.join(parent_dir, "workspace")

# Set up directories for configuration files
workflows_dir = os.path.join(parent_dir, "workflows")
config_dir = os.path.join(parent_dir, "config")
roles_dir = os.path.join(parent_dir, "roles")

# Create directories if they don't exist
os.makedirs(workflows_dir, exist_ok=True)
os.makedirs(config_dir, exist_ok=True)
os.makedirs(roles_dir, exist_ok=True)

# Mount static files
app.mount("/visualization", StaticFiles(directory=current_dir), name="visualization")

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
        import requests
        
        # Forward the request to the MetaGPT API container
        api_url = "http://metagpt-api:8000/api/run_metagpt"
        print(f"Forwarding request to MetaGPT API at {api_url}")
        
        # Create request payload
        payload = {
            "prompt": prompt_request.prompt,
        }
        
        # Add workflow_file if specified
        if prompt_request.workflow_file:
            payload["workflow_file"] = prompt_request.workflow_file
            print(f"Using workflow file: {prompt_request.workflow_file}")
        
        # Add config_file if specified
        if prompt_request.config_file:
            payload["config_file"] = prompt_request.config_file
            print(f"Using config file: {prompt_request.config_file}")
            
        # Forward the request to the API container
        response = requests.post(api_url, json=payload)
        
        if response.status_code != 200:
            print(f"Error from API: {response.status_code} - {response.text}")
            return {"status": "error", "error": f"API Error: {response.text}"}
            
        # Return the API response
        return response.json()
    except Exception as e:
        import traceback
        print(f"Error forwarding request to API: {str(e)}")
        traceback.print_exc()
        return {"status": "error", "error": f"Failed to forward request to API: {str(e)}"}

@app.post("/api/run_metagpt_default")
async def run_metagpt_default(background_tasks: BackgroundTasks):
    # Use a default sample prompt - make it a simple TinyML prompt since that's what was shown in user's terminal
    default_prompt = "Develop a TinyML model to maintain predictions with vibration for a motor using a Raspberry Pi 4 and Google Coral Accelerator"
    
    # Create a PromptRequest with the default prompt
    prompt_request = PromptRequest(prompt=default_prompt)
    
    # Call the run_metagpt function
    return await run_metagpt(prompt_request, background_tasks)

@app.get("/output.json")
async def get_output():
    # First try workspace directory
    output_file = os.path.join(workspace_dir, "output.json")
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            return json.load(f)
    
    # If not found, use the sample file
    sample_file = os.path.join(current_dir, "sample_output.json")
    if os.path.exists(sample_file):
        with open(sample_file, "r") as f:
            return json.load(f)
    else:
        raise HTTPException(status_code=404, detail="Output file not found")

# Configuration management endpoints
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
        
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
            
        # Build API request to metagpt-api
        api_url = "http://metagpt-api:8000/api/run_metagpt"
        payload = {
            "prompt": prompt,
            "workflow_file": workflow_file,
            "config_file": config_file
        }
        
        # Make API request
        import requests
        response = requests.post(api_url, json=payload)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"MetaGPT API error: {response.text}"
            )
            
        return response.json()
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running MetaGPT: {str(e)}")

if __name__ == "__main__":
    print(f"Visualization server running at http://localhost:8088")
    print(f"Open your browser to view the MetaGPT conversation visualization")
    uvicorn.run(app, host="0.0.0.0", port=8088)
