#!/usr/bin/env python3
import os
import json
import argparse
import requests
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default API URL (can be overridden with env var or command-line arg)
API_URL = os.getenv("METAGPT_API_URL", "http://localhost:8000")

def parse_arguments():
    parser = argparse.ArgumentParser(description="MetaGPT Rocket.Chat Integration Client")
    parser.add_argument(
        "--input", "-i", 
        type=str, 
        default="../workspace/output.json",
        help="Path to MetaGPT output JSON file"
    )
    parser.add_argument(
        "--project", "-p", 
        type=str, 
        required=True,
        help="Project name for the conversation channel"
    )
    parser.add_argument(
        "--api-url", 
        type=str, 
        default=API_URL,
        help="URL of the MetaGPT API service"
    )
    return parser.parse_args()

def process_metagpt_output(args):
    """Send MetaGPT output to the API for processing (self-hosted chat UI)"""
    try:
        # Check if file exists
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return False
        
        # Send to API
        api_url = f"{args.api_url}/process_metagpt_output"
        
        logger.info(f"Sending output to API: {api_url}")
        response = requests.post(
            api_url,
            params={
                "project_name": args.project,
                "file_path": str(input_path) if input_path.is_absolute() else None
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Success! Conversation created for project: {args.project}")
            return True
        else:
            logger.error(f"API Error ({response.status_code}): {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing MetaGPT output: {e}")
        return False

def main():
    args = parse_arguments()
    if process_metagpt_output(args):
        logger.info("MetaGPT output successfully sent to Rocket.Chat")
        
        # Print instructions for viewing the conversation
        rocket_chat_url = os.getenv("ROCKET_CHAT_URL", "http://localhost:3000")
        if rocket_chat_url.startswith("http://rocketchat:"):
            # Adjust URL for local browser access
            rocket_chat_url = f"http://localhost:{rocket_chat_url.split(':')[-1]}"
            
        logger.info(f"\nView the conversation at:\n{rocket_chat_url}\n")
        logger.info(f"Login credentials:")
        logger.info(f"Username: {os.getenv('ROCKET_CHAT_USER', 'metagpt-admin')}")
        logger.info(f"Password: {os.getenv('ROCKET_CHAT_PASSWORD', 'password123')}")
    else:
        logger.error("Failed to send MetaGPT output to Rocket.Chat")

if __name__ == "__main__":
    main()
