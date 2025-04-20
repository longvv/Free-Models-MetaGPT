#!/usr/bin/env python3
"""
Final WebSocket Message Display Verification Test

This script tests the end-to-end WebSocket message display functionality 
with our improved debugging and direct messaging approach.
"""

import os
import time
import json
import sys
import requests
import subprocess

# Configuration
UI_URL = "http://localhost:8088"
TEST_WEBSOCKET_URL = "http://localhost:8088/api/test_websocket/{job_id}"

def main():
    """Main test function"""
    print("\n=== Running Final WebSocket Message Display Verification ===\n")
    
    # Check if the UI is accessible
    print("1. Checking UI accessibility...")
    try:
        response = requests.get(UI_URL)
        if response.status_code != 200:
            print(f"Error: UI not accessible (Status: {response.status_code})")
            return 1
        print("✓ UI is accessible")
    except Exception as e:
        print(f"Error: Unable to connect to UI: {str(e)}")
        return 1
    
    # Create test job ID
    job_id = f"test_final_{int(time.time())}"
    print(f"✓ Generated test job ID: {job_id}")
    
    # Create test files
    print("\n2. Creating test message files...")
    workspace_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", f"workspace_{job_id}")
    logs_path = os.path.join(workspace_path, "logs")
    os.makedirs(logs_path, exist_ok=True)
    
    # Create message files with different roles
    roles = ["product_manager", "architect", "engineer", "qa_engineer", "technical_lead"]
    for i, role in enumerate(roles):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        content = f"# Test Message from {role.replace('_', ' ').title()}\n\nThis is message #{i+1} testing WebSocket display.\n\n"
        
        # Add role-specific content
        if role == "engineer":
            content += "```python\ndef test_function():\n    print('WebSocket test successful!')\n    return True\n```"
        elif role == "architect":
            content += "## System Components\n\n1. WebSocket Server\n2. Client Handler\n3. Message Display"
        elif role == "product_manager":
            content += "**Key Requirements:**\n\n* Real-time updates\n* Proper formatting\n* Role-based styling"
        
        # Create the message file
        log_data = {
            "role": role,
            "content": content,
            "model": "test-model-verification"
        }
        
        filename = f"{timestamp}_{job_id}_test_{i}.json"
        filepath = os.path.join(logs_path, filename)
        with open(filepath, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"✓ Created test file for {role}: {filename}")
    
    # Create output.json
    output_data = []
    for i, role in enumerate(roles):
        output_data.append({
            "role": role,
            "content": f"Summary message from {role.replace('_', ' ').title()} - Test #{i+1} successful!",
            "model": "test-model-verification"
        })
    
    output_path = os.path.join(workspace_path, "output.json")
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✓ Created output.json in workspace directory")
    
    print("\n3. Test Instructions:")
    print(f"   a. Open the browser at {UI_URL}")
    print(f"   b. Enter this job ID in the prompt field and submit: {job_id}")
    print("   c. Enable the debug console by clicking the 'Debug' button")
    print("   d. Verify messages appear in the chat interface")
    print("   e. Check the debug console to see WebSocket message flow")
    print("\n   Alternative Test Method:")
    print("   a. Click the 'Test WebSocket' button in the UI")
    print("   b. Verify test messages appear correctly")
    print("   c. Check the debug console for message flow details")
    
    print("\n=== Test Setup Complete ===")
    print("Monitor the browser interface to verify WebSocket message display")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
