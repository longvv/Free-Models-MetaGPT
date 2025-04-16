# logger.py
# Logging utility for tracking model processing and errors

import logging
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

class ModelLogger:
    """Logger for tracking model processing and errors."""
    
    def __init__(self, 
                log_dir: str = "./logs",
                log_level: int = logging.INFO,
                console_output: bool = True):
        """Initialize the model logger.
        
        Args:
            log_dir: Directory to save log files
            log_level: Logging level (default: INFO)
            console_output: Whether to output logs to console
        """
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamp for log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"model_processing_{timestamp}.log"
        
        # Configure logger
        self.logger = logging.getLogger("model_logger")
        self.logger.setLevel(log_level)
        self.logger.propagate = False  # Prevent duplicate logs
        
        # Clear any existing handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler (optional)
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def log_model_request(self, model: str, messages: Any, task_config: Dict[str, Any]) -> None:
        """Log a model request.
        
        Args:
            model: Model name
            messages: Messages sent to the model
            task_config: Task configuration
        """
        self.logger.info(f"Model request to {model}")
        self.logger.debug(f"Task config: {json.dumps(task_config, indent=2)}")
        
        # Log message count and approximate token count
        message_count = len(messages) if isinstance(messages, list) else 1
        total_content = ""
        
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and "content" in msg:
                    total_content += msg["content"]
        
        approx_tokens = len(total_content) // 4  # Very rough approximation
        self.logger.info(f"Messages: {message_count}, Approx tokens: {approx_tokens}")
    
    def log_model_response(self, model: str, response: Dict[str, Any]) -> None:
        """Log a model response.
        
        Args:
            model: Model name
            response: Model response
        """
        self.logger.info(f"Received response from {model}")
        
        # Check if response contains choices
        if "choices" in response:
            choice_count = len(response["choices"])
            self.logger.info(f"Response contains {choice_count} choices")
            
            # Log first choice content
            if choice_count > 0:
                first_choice = response["choices"][0]
                if "message" in first_choice and "content" in first_choice["message"]:
                    content_preview = first_choice["message"]["content"][:100]
                    self.logger.debug(f"First choice preview: {content_preview}...")
                else:
                    self.logger.warning(f"Unexpected choice format: {first_choice}")
        else:
            self.logger.warning(f"Response missing 'choices' field: {response}")
    
    def log_error(self, error_type: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an error.
        
        Args:
            error_type: Type of error
            error_message: Error message
            details: Additional error details
        """
        self.logger.error(f"{error_type}: {error_message}")
        if details:
            self.logger.error(f"Error details: {json.dumps(details, indent=2)}")
    
    def log_processing_step(self, step_name: str, details: Optional[str] = None) -> None:
        """Log a processing step.
        
        Args:
            step_name: Name of the processing step
            details: Additional details about the step
        """
        self.logger.info(f"Processing step: {step_name}")
        if details:
            self.logger.debug(f"Step details: {details}")
    
    def log_file_processing(self, file_path: str, status: str, details: Optional[str] = None) -> None:
        """Log file processing information.
        
        Args:
            file_path: Path to the file being processed
            status: Processing status (e.g., 'started', 'completed', 'error')
            details: Additional details
        """
        self.logger.info(f"File {file_path}: {status}")
        if details:
            self.logger.debug(f"File processing details: {details}")

# Create a default logger instance
default_logger = ModelLogger()

# Convenience functions using the default logger
def log_model_request(model: str, messages: Any, task_config: Dict[str, Any]) -> None:
    default_logger.log_model_request(model, messages, task_config)

def log_model_response(model: str, response: Dict[str, Any]) -> None:
    default_logger.log_model_response(model, response)

def log_error(error_type: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
    default_logger.log_error(error_type, error_message, details)

def log_processing_step(step_name: str, details: Optional[str] = None) -> None:
    default_logger.log_processing_step(step_name, details)

def log_file_processing(file_path: str, status: str, details: Optional[str] = None) -> None:
    default_logger.log_file_processing(file_path, status, details)