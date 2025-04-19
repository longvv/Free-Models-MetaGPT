#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
from pathlib import Path
from typing import Dict, Any

from dynamic_model.collaborative_task_orchestrator import CollaborativeTaskOrchestrator

async def main():
    """Run the collaborative workflow with multiple expert models interacting together."""
    parser = argparse.ArgumentParser(description="Run a collaborative workflow with multiple expert models.")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config.yml", 
        help="Path to configuration file"
    )
    parser.add_argument(
        "--workflow", 
        type=str, 
        default="collaborative", 
        help="Name of workflow to execute"
    )
    parser.add_argument(
        "--input", 
        type=str, 
        help="Input prompt or path to input file"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="output.json", 
        help="Path to output file"
    )
    
    args = parser.parse_args()
    
    # Check if input is a file path or direct input
    if args.input and os.path.isfile(args.input):
        with open(args.input, "r") as f:
            input_data = f.read()
    else:
        input_data = args.input or "Please provide a detailed description of the software you want to build."
    
    # Resolve config path - handle both absolute and relative paths
    config_path = args.config
    if not os.path.isabs(config_path):
        # Try relative to current directory first
        if os.path.exists(config_path):
            config_path = os.path.abspath(config_path)
        else:
            # Try relative to script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            alt_config_path = os.path.join(script_dir, config_path)
            if os.path.exists(alt_config_path):
                config_path = alt_config_path
    
    print(f"Using configuration file: {config_path}")
    
    # Resolve workflow path - handle both name and path
    workflow_path = args.workflow
    if not os.path.isfile(workflow_path):
        # Try as a name in the workflows directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        workflows_dir = os.path.join(script_dir, "workflows")
        potential_paths = [
            os.path.join(workflows_dir, f"{workflow_path}.yml"),
            os.path.join(workflows_dir, f"{workflow_path}.yaml"),
            os.path.join(workflows_dir, workflow_path)
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                workflow_path = path
                break
    
    print(f"Using workflow file: {workflow_path}")
    
    # Initialize the collaborative task orchestrator
    orchestrator = CollaborativeTaskOrchestrator(config_path)
    await orchestrator.initialize()
    
    print(f"\n=== Starting Collaborative Workflow: {os.path.basename(workflow_path)} ===")
    print(f"Input: {input_data[:100]}..." if len(input_data) > 100 else f"Input: {input_data}")
    
    # Execute the workflow
    print("\n=== Starting conversation between expert models ===\n")
    print("Messages will be displayed in real-time as models respond...\n")

    # Extract workflow name from path
    workflow_name = os.path.splitext(os.path.basename(workflow_path))[0]
    
    results = await orchestrator.execute_workflow(workflow_name, input_data)
    
    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Save results to output file
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n=== Workflow completed. Results saved to {args.output} ===")
    
    # Print a summary of the results
    print("\nWorkflow Summary:")
    for task, result in results.items():
        if not task.endswith("_validation"):
            print(f"- {task}: {len(result)} characters")

if __name__ == "__main__":
    asyncio.run(main())