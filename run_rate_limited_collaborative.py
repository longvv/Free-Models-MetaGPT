#!/usr/bin/env python3
# run_rate_limited_collaborative.py
# Script to run collaborative conversations with enhanced rate limiting

import asyncio
import argparse
import json
import os
import yaml
from pathlib import Path
from datetime import datetime

# Import the enhanced rate limiting orchestrator
from enhanced_rate_limiting_orchestrator import EnhancedRateLimitingOrchestrator

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run collaborative conversations with enhanced rate limiting")
    parser.add_argument("--workflow", "-w", type=str, required=True,
                        help="Name of the workflow or path to workflow file")
    parser.add_argument("--prompt", "-p", type=str, required=True,
                        help="Initial prompt for the conversation")
    parser.add_argument("--config", "-c", type=str, default="config",
                        help="Path to configuration directory (default: config)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Path to output file for results")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")
    args = parser.parse_args()
    
    # Print startup banner
    print("\n" + "=" * 80)
    print(f"Starting Rate-Limited Collaborative Conversation")
    print(f"Workflow: {args.workflow}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")
    
    # Initialize the orchestrator
    print("Initializing rate-limited orchestrator...")
    orchestrator = EnhancedRateLimitingOrchestrator(args.config)
    await orchestrator.initialize()
    
    # Load rate limiting configuration
    rate_limit_config_path = Path(args.config) / "rate_limiting.yml"
    if rate_limit_config_path.exists():
        try:
            with open(rate_limit_config_path, 'r') as f:
                rate_limit_config = yaml.safe_load(f)
                print(f"Loaded rate limiting configuration from {rate_limit_config_path}")
                if args.verbose:
                    print(f"Global rate limit: {rate_limit_config.get('global', {}).get('requests_per_minute', 'N/A')} requests per minute")
                    model_specific = rate_limit_config.get('model_specific', {})
                    if model_specific:
                        print("Model-specific rate limits:")
                        for model, config in model_specific.items():
                            print(f"  - {model}: {config.get('requests_per_minute', 'N/A')} requests per minute")
        except Exception as e:
            print(f"Warning: Failed to load rate limiting configuration: {e}")
    
    # Execute the workflow
    print(f"\nExecuting workflow: {args.workflow}")
    print(f"Initial prompt: {args.prompt}\n")
    
    try:
        start_time = datetime.now()
        results = await orchestrator.execute_workflow(args.workflow, args.prompt)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Print completion banner
        print("\n" + "=" * 80)
        print(f"Workflow completed in {duration:.2f} seconds")
        print("=" * 80 + "\n")
        
        # Save results if output path is specified
        if args.output:
            output_path = Path(args.output)
            # Create directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata to results
            output_data = {
                "workflow": args.workflow,
                "prompt": args.prompt,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "results": results
            }
            
            # Write to file
            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)
            
            print(f"Results saved to: {output_path}")
        
        # Print final results
        print("\nFinal Results:")
        for task_name, result in results.items():
            print(f"\n--- {task_name} ---")
            # Limit output length for readability
            if isinstance(result, str) and len(result) > 500:
                print(f"{result[:500]}...\n[Output truncated, total length: {len(result)} characters]")
            else:
                print(result)
        
    except Exception as e:
        print(f"\nError executing workflow: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())