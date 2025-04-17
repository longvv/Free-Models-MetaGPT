#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
from pathlib import Path
from typing import Dict, Any

from enhanced_collaborative_orchestrator import EnhancedCollaborativeTaskOrchestrator

async def main():
    """Run the enhanced collaborative workflow with role-based configurations."""
    parser = argparse.ArgumentParser(description="Run enhanced collaborative workflow with role-based configurations.")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config", 
        help="Path to configuration directory"
    )
    parser.add_argument(
        "--workflow", 
        type=str, 
        default="collaborative", 
        help="Name of workflow to execute or path to workflow file"
    )
    parser.add_argument(
        "--input", 
        type=str, 
        help="Input prompt or path to input file"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="workspace/enhanced_output.json", 
        help="Path to output file"
    )
    
    args = parser.parse_args()
    
    # Check if input is a file path or direct input
    if args.input and os.path.isfile(args.input):
        with open(args.input, "r") as f:
            input_data = f.read()
    else:
        input_data = args.input or "Please provide a detailed description of the software you want to build."
    
    # Initialize the enhanced orchestrator
    orchestrator = EnhancedCollaborativeTaskOrchestrator(args.config)
    await orchestrator.initialize()
    
    print(f"\n=== Starting Enhanced Collaborative Workflow: {args.workflow} ===")
    print(f"Input: {input_data[:100]}..." if len(input_data) > 100 else f"Input: {input_data}")
    
    # Execute the workflow
    print("\n=== Starting conversation between expert models using role-based configuration ===\n")
    print("Messages will be displayed in real-time as models respond...\n")
    
    # Extract workflow name from path if a path is provided
    workflow_name = os.path.splitext(os.path.basename(args.workflow))[0] if os.path.isfile(args.workflow) else args.workflow
    
    results = await orchestrator.execute_workflow(args.workflow, input_data)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
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
