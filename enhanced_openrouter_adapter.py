# enhanced_openrouter_adapter.py
# Enhanced OpenRouter adapter with rate limiting and circuit breaker

import os
import json
import aiohttp
import asyncio
import time
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta

class CircuitBreaker:
    """Circuit breaker for API calls to prevent hammering failing services."""
    
    CLOSED = 'closed'  # Normal operation - requests pass through
    OPEN = 'open'      # Service considered down - requests fail fast
    HALF_OPEN = 'half_open'  # Testing if service is back up
    
    def __init__(self, 
                failure_threshold: int = 5,
                recovery_timeout: int = 30,
                timeout_factor: float = 2.0):
        """Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds to wait before trying again
            timeout_factor: Factor to multiply timeout by on consecutive failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout_factor = timeout_factor
        
        self.failure_count = 0
        self.state = self.CLOSED
        self.last_failure_time = None
        self.current_timeout = recovery_timeout
        
    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            print(f"Circuit OPEN after {self.failure_count} failures")
            
        elif self.state == self.HALF_OPEN:
            self.state = self.OPEN
            self.current_timeout = min(self.current_timeout * self.timeout_factor, 300)
            print(f"Circuit re-OPEN after test failure. New timeout: {self.current_timeout}s")
            
    def record_success(self) -> None:
        """Record a success and potentially close the circuit."""
        self.failure_count = 0
        
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self.current_timeout = self.recovery_timeout
            print("Circuit CLOSED after successful test")
            
    def can_request(self) -> bool:
        """Check if a request can be made through the circuit.
        
        Returns:
            True if request can proceed, False otherwise
        """
        if self.state == self.CLOSED:
            return True
            
        elif self.state == self.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time is None:
                return True
                
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed >= self.current_timeout:
                self.state = self.HALF_OPEN
                print(f"Circuit HALF-OPEN after {elapsed:.1f}s timeout")
                return True
                
            return False
            
        elif self.state == self.HALF_OPEN:
            return True
            
        return False


class RateLimiter:
    """Rate limiter for API calls to prevent exceeding rate limits."""
    
    def __init__(self, 
                requests_per_minute: int = 10,
                max_parallel: int = 2,
                backoff_strategy: str = "exponential",
                initial_backoff: float = 1.0,
                max_backoff: float = 60.0):
        """Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            max_parallel: Maximum parallel requests
            backoff_strategy: Strategy for backoff ('fixed', 'linear', 'exponential')
            initial_backoff: Initial backoff time in seconds
            max_backoff: Maximum backoff time in seconds
        """
        self.requests_per_minute = requests_per_minute
        self.max_parallel = max_parallel
        self.backoff_strategy = backoff_strategy
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        
        self.request_times = []
        self.semaphore = asyncio.Semaphore(max_parallel)
        self.retry_counts = {}
        
    async def acquire(self, key: str = "default") -> None:
        """Acquire permission to make a request.
        
        Args:
            key: Key to identify the request type
        """
        # Wait for semaphore to control parallel requests
        await self.semaphore.acquire()
        
        # Check rate limit
        now = time.time()
        minute_ago = now - 60
        
        # Cleanup old request times
        self.request_times = [t for t in self.request_times if t > minute_ago]
        
        # If at rate limit, wait until a slot opens up
        if len(self.request_times) >= self.requests_per_minute:
            # Calculate time to wait
            oldest = min(self.request_times)
            wait_time = oldest + 60 - now
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                
        # Record this request
        self.request_times.append(time.time())
        
    def release(self) -> None:
        """Release a request slot."""
        self.semaphore.release()
        
    def get_backoff_time(self, key: str) -> float:
        """Get backoff time for a retry.
        
        Args:
            key: Key to identify the request type
            
        Returns:
            Backoff time in seconds
        """
        retry_count = self.retry_counts.get(key, 0)
        self.retry_counts[key] = retry_count + 1
        
        if self.backoff_strategy == "fixed":
            return self.initial_backoff
            
        elif self.backoff_strategy == "linear":
            backoff = self.initial_backoff * (retry_count + 1)
            
        elif self.backoff_strategy == "exponential":
            backoff = self.initial_backoff * (2 ** retry_count)
            
        else:  # Default to exponential
            backoff = self.initial_backoff * (2 ** retry_count)
            
        return min(backoff, self.max_backoff)
        
    def reset_retries(self, key: str) -> None:
        """Reset retry count for a key.
        
        Args:
            key: Key to identify the request type
        """
        if key in self.retry_counts:
            del self.retry_counts[key]


class ModelRotator:
    """Rotates through available models to distribute load."""
    
    def __init__(self, primary_model: str, backup_models: List[str] = None, model_api_keys: Dict[str, str] = None):
        """Initialize the model rotator.
        
        Args:
            primary_model: Primary model to use
            backup_models: List of backup models
            model_api_keys: Dictionary mapping model names to API keys
        """
        self.primary_model = primary_model
        self.backup_models = backup_models or []
        self.circuit_breakers = {
            model: CircuitBreaker() for model in [primary_model] + self.backup_models
        }
        self.current_index = 0
        self.model_api_keys = model_api_keys or {}
        
        # Add model size awareness
        self.model_sizes = {
            "deepseek/deepseek-r1-distill-llama-70b": "large",
            "open-r1/olympiccoder-32b": "medium",
            "microsoft/phi-3-medium-128k-instruct": "medium-large-context",
            "mistralai/mistral-7b-instruct": "small",
            "microsoft/wizardlm-2-8x22b": "medium",
            "meta-llama/llama-guard-3-8b": "small"
        }
        
    def get_next_available_model(self) -> Optional[str]:
        """Get the next available model.
        
        Returns:
            Next available model or None if all are unavailable
        """
        # First check primary model
        if self.circuit_breakers[self.primary_model].can_request():
            return self.primary_model
            
        # Check backup models
        if not self.backup_models:
            return None
            
        # Try to find an available backup model
        for _ in range(len(self.backup_models)):
            self.current_index = (self.current_index + 1) % len(self.backup_models)
            model = self.backup_models[self.current_index]
            
            if self.circuit_breakers[model].can_request():
                return model
                
        return None
    
    def get_api_key_for_model(self, model: str) -> Optional[str]:
        """Get the API key for a specific model.
        
        Args:
            model: Model name
            
        Returns:
            API key for the model or None if not found
        """
        return self.model_api_keys.get(model)
        
    def record_success(self, model: str) -> None:
        """Record a successful API call.
        
        Args:
            model: Model that succeeded
        """
        if model in self.circuit_breakers:
            self.circuit_breakers[model].record_success()
            
    def record_failure(self, model: str) -> None:
        """Record a failed API call.
        
        Args:
            model: Model that failed
        """
        if model in self.circuit_breakers:
            self.circuit_breakers[model].record_failure()


class EnhancedOpenRouterAdapter:
    """Enhanced adapter for connecting with OpenRouter's free models."""
    
    def __init__(self, 
                config: Dict[str, Any],
                api_key: Optional[str] = None):
        """Initialize the enhanced OpenRouter adapter.
        
        Args:
            config: Configuration dictionary
            api_key: OpenRouter API key (optional, can be set via env variable)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or config.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key not provided and not found in environment")
            
        rate_limit_config = config.get("RATE_LIMITING", {})
        self.rate_limiter = RateLimiter(
            requests_per_minute=rate_limit_config.get("requests_per_minute", 10),
            max_parallel=rate_limit_config.get("max_parallel_requests", 2),
            backoff_strategy=rate_limit_config.get("backoff_strategy", "exponential"),
            initial_backoff=rate_limit_config.get("initial_backoff_seconds", 1.0),
            max_backoff=rate_limit_config.get("max_backoff_seconds", 60.0)
        )
        
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_rotators = {}
        
        # Extract model API keys from config
        self.model_api_keys = {}
        for task_name, task_config in config.get("TASK_MODEL_MAPPING", {}).items():
            primary_config = task_config.get("primary", {})
            backup_config = task_config.get("backup", {})
            
            primary_model = primary_config.get("model")
            backup_model = backup_config.get("model")
            
            if primary_model and "api_key" in primary_config:
                self.model_api_keys[primary_model] = primary_config["api_key"]
                
            if backup_model and "api_key" in backup_config:
                self.model_api_keys[backup_model] = backup_config["api_key"]
        
    def _get_model_rotator(self, 
                          primary_model: str, 
                          backup_models: List[str] = None) -> ModelRotator:
        """Get or create a model rotator for the given models.
        
        Args:
            primary_model: Primary model
            backup_models: Backup models
            
        Returns:
            ModelRotator instance
        """
        key = primary_model
        if key not in self.model_rotators:
            self.model_rotators[key] = ModelRotator(
                primary_model, 
                backup_models,
                model_api_keys=self.model_api_keys
            )
            
        return self.model_rotators[key]
        
    async def _make_request(self, 
                           endpoint: str, 
                           payload: Dict[str, Any],
                           model: str,
                           backup_models: List[str] = None,
                           timeout: float = 120,
                           max_retries: int = 3) -> Dict[str, Any]:
        """Make an async request to OpenRouter API with retry logic.
        
        Args:
            endpoint: API endpoint to call
            payload: Request payload
            model: Primary model to use
            backup_models: Backup models to use if primary fails
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            
        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}/{endpoint}"
        
        # Get model rotator
        rotator = self._get_model_rotator(model, backup_models)
        
        # Generate request key for rate limiter
        request_key = f"{model}:{endpoint}"
        
        retries = 0
        while retries <= max_retries:
            # Get next available model
            current_model = rotator.get_next_available_model()
            if not current_model:
                raise Exception(f"All models are currently unavailable. Try again later.")
                
            # Get the model-specific API key if available
            model_api_key = rotator.get_api_key_for_model(current_model) or self.api_key
            
            # Set up headers with the appropriate API key
            headers = {
                "Authorization": f"Bearer {model_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://metagpt.com",  # Replace with your domain
                "X-Title": "MetaGPT Free Models"        # Your application name
            }
            
            # Update payload with current model
            model_payload = dict(payload)
            model_payload["model"] = current_model
            
            # Adjust timeout based on model size
            model_timeout = timeout
            if "70b" in current_model:
                model_timeout = max(timeout, 240)  # Longer timeout for 70B model
            elif "128k" in current_model:
                model_timeout = max(timeout, 300)  # Even longer timeout for large context model
            elif "32b" in current_model or "22b" in current_model:
                model_timeout = max(timeout, 180)  # Extended timeout for larger models
            
            try:
                # Acquire rate limiter permission
                await self.rate_limiter.acquire(request_key)
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, 
                                              json=model_payload, 
                                              headers=headers, 
                                              timeout=model_timeout) as response:
                            
                            if response.status == 200:
                                # Success!
                                result = await response.json()
                                rotator.record_success(current_model)
                                self.rate_limiter.reset_retries(request_key)
                                return result
                                
                            elif response.status == 429:
                                # Rate limit hit
                                error_text = await response.text()
                                print(f"Rate limit hit: {error_text}")
                                
                                # Add dynamic backoff based on response headers
                                retry_after = response.headers.get("Retry-After")
                                wait_time = float(retry_after) if retry_after else self.rate_limiter.get_backoff_time(request_key)
                                
                                print(f"Rate limited. Waiting {wait_time:.1f}s before retry.")
                                await asyncio.sleep(wait_time)
                                
                            else:
                                # Other error
                                error_text = await response.text()
                                print(f"OpenRouter API error ({response.status}): {error_text}")
                                
                                rotator.record_failure(current_model)
                                
                                if retries < max_retries:
                                    wait_time = self.rate_limiter.get_backoff_time(request_key)
                                    print(f"Retrying in {wait_time:.1f}s ({retries+1}/{max_retries})")
                                    await asyncio.sleep(wait_time)
                                else:
                                    raise Exception(f"OpenRouter API error after {max_retries} retries: {error_text}")
                                    
                except aiohttp.ClientError as e:
                    print(f"HTTP error: {str(e)}")
                    rotator.record_failure(current_model)
                    
                    if retries < max_retries:
                        wait_time = self.rate_limiter.get_backoff_time(request_key)
                        print(f"Retrying in {wait_time:.1f}s ({retries+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"HTTP error after {max_retries} retries: {str(e)}")
                        
            finally:
                # Always release the rate limiter
                self.rate_limiter.release()
                
            retries += 1
            
        raise Exception(f"Failed after {max_retries} retries")
    
    async def generate_completion(self,
                                 messages: List[Dict[str, str]],
                                 task_config: Dict[str, Any],
                                 timeout: float = 120) -> Dict[str, Any]:
        """Generate a completion using OpenRouter with enhanced reliability.
        
        Args:
            messages: List of message dictionaries (role, content)
            task_config: Task configuration with model information
            timeout: Request timeout in seconds
            
        Returns:
            Completion response
        """
        # Extract models and parameters from task config
        primary_config = task_config.get("primary", {})
        backup_config = task_config.get("backup", {})
        
        primary_model = primary_config.get("model")
        backup_model = backup_config.get("model")
        
        temperature = primary_config.get("temperature", 0.7)
        max_tokens = primary_config.get("max_tokens", 2048)
        
        # Special handling for large context window models
        if primary_model == "microsoft/phi-3-medium-128k-instruct":
            timeout = max(timeout, 300)  # Longer timeout for large context window
            
        # Special handling for large parameter models
        if "70b" in primary_model or "32b" in primary_model or "22b" in primary_model:
            timeout = max(timeout, 240)  # Longer timeout for large models
        
        backup_models = [backup_model] if backup_model else []
        
        payload = {
            "model": primary_model,  # Will be updated in _make_request
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        return await self._make_request(
            endpoint="chat/completions", 
            payload=payload, 
            model=primary_model,
            backup_models=backup_models,
            timeout=timeout
        )
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from OpenRouter.
        
        Returns:
            List of model information dictionaries
        """
        url = f"{self.base_url}/models"
        # Use the default API key for this operation
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        # Acquire rate limiter permission
        await self.rate_limiter.acquire("get_models")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"OpenRouter API error ({response.status}): {error_text}")
                        
                    data = await response.json()
                    return data.get("data", [])
        finally:
            # Always release the rate limiter
            self.rate_limiter.release()
    
    async def get_free_models(self) -> List[Dict[str, Any]]:
        """Get list of free models from OpenRouter.
        
        Returns:
            List of free model information dictionaries
        """
        models = await self.get_available_models()
        return [model for model in models if model.get("pricing", {}).get("prompt") == 0]
