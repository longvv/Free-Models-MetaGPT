#!/usr/bin/env python3
"""
MetaGPT Visualization Runner
----------------------------
This script runs the MetaGPT visualization server, allowing you to interact with MetaGPT
through a web interface. It handles starting all necessary services.

Usage:
    python run_all.py
"""

import os
import sys
import subprocess
import time
import threading
import webbrowser
import signal
import argparse
from pathlib import Path

# Get the current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VISUALIZATION_DIR = os.path.join(CURRENT_DIR, "visualization")

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        # Check FastAPI and Uvicorn
        import fastapi
        import uvicorn
        print("✓ FastAPI and Uvicorn are installed")
    except ImportError:
        print("✗ FastAPI or Uvicorn not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "jinja2"], check=True)
    
    # Check if MetaGPT is installed (optional)
    try:
        subprocess.run(
            [sys.executable, "-m", "metagpt", "--help"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        print("✓ MetaGPT is installed - full API functionality available")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        print("ℹ MetaGPT is not installed - running in visualization-only mode")
        print("  For full functionality: pip install metagpt")
        return True  # Still return True to continue with visualization-only mode

def run_visualization_server(port=8088):
    """Run the visualization server."""
    # Import here to ensure dependencies are already checked
    import uvicorn
    from visualization.server import app
    
    # This will block until the server is stopped
    uvicorn.run(app, host="0.0.0.0", port=port)

def create_workspace_directories():
    """Create necessary workspace directories if they don't exist."""
    workspace_dir = os.path.join(CURRENT_DIR, "workspace")
    logs_dir = os.path.join(CURRENT_DIR, "logs")
    
    # Create necessary directories
    os.makedirs(workspace_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    print(f"✓ Created workspace directory: {workspace_dir}")
    print(f"✓ Created logs directory: {logs_dir}")
    
    # Create the sample output.json file if it doesn't exist in either location
    workspace_output = os.path.join(workspace_dir, "output.json")
    sample_output = os.path.join(VISUALIZATION_DIR, "sample_output.json")
    
    if not os.path.exists(workspace_output) and os.path.exists(sample_output):
        # Copy the sample output.json to the workspace directory
        import shutil
        shutil.copy(sample_output, workspace_output)
        print(f"✓ Copied sample output.json to {workspace_output}")

def open_browser(port=8088, delay=1.5):
    """Open the browser after a small delay."""
    def _open_browser():
        time.sleep(delay)  # Give the server a moment to start
        url = f"http://localhost:{port}"
        print(f"Opening browser at {url}")
        webbrowser.open(url)
    
    browser_thread = threading.Thread(target=_open_browser)
    browser_thread.daemon = True
    browser_thread.start()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run the MetaGPT visualization server")
    parser.add_argument("--port", type=int, default=8088, help="Port to run the server on")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the browser automatically")
    args = parser.parse_args()
    
    print("==== MetaGPT Visualization Runner ====\n")
    
    # Check dependencies - always continue since MetaGPT is optional
    check_dependencies()
    
    # Create workspace directories
    create_workspace_directories()
    
    # Start the visualization server
    print(f"\nStarting visualization server on port {args.port}...")
    
    # Open browser if not disabled
    if not args.no_browser:
        open_browser(args.port)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nShutting down server...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the server (this will block until the server is stopped)
    run_visualization_server(args.port)

if __name__ == "__main__":
    main()
