# enhanced_rate_limiting_adapter.py
# Enhanced OpenRouter adapter with advanced rate limiting and retry mechanisms

import os
import json
import aiohttp
import asyncio
import time
import random
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta

# Import logging functionality
from logger import log_model_request, log_model_response, log_error, log_processing_step

class TokenBucketRateLimiter:
    """Token bucket algorithm for rate limiting API calls.
    
    This implementation tracks rate limits per model and globally to ensure
    we don't exceed OpenRouter's limits.
    """
    
    def __init__(self, 
                requests_per_minute: int = 20,
                bucket_capacity: int = 20,
                refill_rate: float = 0.33,  # Tokens per second
                jitter_factor: float = 0.2):
        """Initialize the token bucket rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            bucket_capacity: Maximum tokens the bucket can hold
            refill_rate: Rate at which tokens are added (per second)
            jitter_factor: Random factor to add to wait times (0.0-1.0)
        """
        self.requests_per_minute = requests_per_minute
        self.bucket_capacity = bucket_capacity
        self.refill_rate = refill_rate
        self.jitter_factor = jitter_factor
        
        # Global bucket
        self.global_tokens = bucket_capacity
        self.last_refill_time = time.time()
        
        # Per-model buckets
        self.model_buckets = {}
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
        
        # Rate limit tracking
        self.rate_limit_headers = {}
    
    def update_rate_limit_info(self, model: str, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers.
        
        Args:
            model: The model identifier
            headers: Response headers containing rate limit information
        """
        if not headers:
            return
            
        limit_info = {
            "limit": headers.get("X-RateLimit-Limit"),
            "remaining": headers.get("X-RateLimit-Remaining"),
            "reset": headers.get("X-RateLimit-Reset"),
            "updated_at": time.time()
        }
        
        self.rate_limit_headers[model] = limit_info
        
        # If we got a rate limit response, adjust our tokens accordingly
        if limit_info["remaining"] and int(limit_info["remaining"]) == 0:
            self.model_buckets[model] = 0
            self.global_tokens = max(0, self.global_tokens - 5)  # Penalize global bucket
            
            print(f"Rate limit reached for {model}. Adjusting token buckets.")
    
    async def acquire(self, model: str) -> float:
        """Acquire permission to make a request, returning wait time if needed.
        
        Args:
            model: The model identifier
            
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        async with self.lock:
            # Refill tokens based on time elapsed
            now = time.time()
            elapsed = now - self.last_refill_time
            self.last_refill_time = now
            
            # Refill global bucket
            new_tokens = elapsed * self.refill_rate
            self.global_tokens = min(self.bucket_capacity, self.global_tokens + new_tokens)
            
            # Refill model bucket if it exists
            if model in self.model_buckets:
                self.model_buckets[model] = min(
                    self.bucket_capacity, 
                    self.model_buckets[model] + new_tokens
                )
            else:
                # Initialize model bucket with same tokens as global
                self.model_buckets[model] = self.global_tokens
            
            # Check if we have rate limit info for this model
            if model in self.rate_limit_headers:
                limit_info = self.rate_limit_headers[model]
                
                # If we have recent rate limit info with remaining=0, calculate wait time
                if (limit_info["remaining"] and int(limit_info["remaining"]) == 0 and 
                    limit_info["reset"] and time.time() - limit_info["updated_at"] < 60):
                    
                    reset_time = int(limit_info["reset"]) / 1000  # Convert from milliseconds
                    wait_time = max(0, reset_time - time.time())
                    
                    if wait_time > 0:
                        print(f"Rate limit for {model} will reset in {wait_time:.2f}s")
                        return wait_time
            
            # Check if we have enough tokens
            if self.global_tokens < 1 or self.model_buckets[model] < 1:
                # Calculate wait time based on refill rate
                global_wait = max(0, (1 - self.global_tokens) / self.refill_rate)
                model_wait = max(0, (1 - self.model_buckets[model]) / self.refill_rate)
                wait_time = max(global_wait, model_wait)
                
                # Add jitter to prevent thundering herd
                jitter = wait_time * self.jitter_factor * random.random()
                wait_time += jitter
                
                print(f"Rate limit prevention: waiting {wait_time:.2f}s before requesting {model}")
                return wait_time
            
            # Consume tokens
            self.global_tokens -= 1
            self.model_buckets[model] -= 1
            
            return 0


class RequestQueue:
    """Queue system for managing API requests with priority."""
    
    def __init__(self, max_parallel: int = 3):
        """Initialize the request queue.
        
        Args:
            max_parallel: Maximum number of parallel requests
        """
        self.queue = asyncio.PriorityQueue()
        self.semaphore = asyncio.Semaphore(max_parallel)
        self.processing = set()
    
    async def add_request(self, priority: int, request_id: str, coroutine: Any) -> Any:
        """Add a request to the queue and wait for its result.
        
        Args:
            priority: Priority of the request (lower is higher priority)
            request_id: Unique identifier for the request
            coroutine: Coroutine to execute
            
        Returns:
            Result of the coroutine
        """
        # Create a future to store the result
        future = asyncio.Future()
        
        # Add to queue
        await self.queue.put((priority, request_id, coroutine, future))
        
        # Start processing the queue if not already running
        asyncio.create_task(self._process_queue())
        
        # Wait for the result
        return await future
    
    async def _process_queue(self) -> None:
        """Process requests from the queue."""
        while not self.queue.empty():
            # Get next request
            priority, request_id, coroutine, future = await self.queue.get()
            
            # Skip if already processing this request
            if request_id in self.processing:
                self.queue.task_done()
                continue
            
            # Mark as processing
            self.processing.add(request_id)
            
            # Wait for semaphore
            async with self.semaphore:
                try:
                    # Execute the coroutine
                    result = await coroutine
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    # Mark as done
                    self.processing.remove(request_id)
                    self.queue.task_done()


class EnhancedRateLimitingAdapter:
    """Enhanced OpenRouter adapter with advanced rate limiting and retry mechanisms."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the adapter with configuration.
        
        Args:
            config: Configuration dictionary
        """
        # Extract OpenRouter configuration
        openrouter_config = config.get("OPENROUTER_CONFIG", {})
        
        # API keys
        self.default_api_key = openrouter_config.get("default_api_key", os.environ.get("OPENROUTER_API_KEY", ""))
        self.model_keys = openrouter_config.get("model_keys", {})
        
        # Rate limiting configuration
        rate_limit_config = openrouter_config.get("rate_limiting", {})
        self.rate_limiter = TokenBucketRateLimiter(
            requests_per_minute=rate_limit_config.get("requests_per_minute", 20),
            bucket_capacity=rate_limit_config.get("bucket_capacity", 20),
            refill_rate=rate_limit_config.get("refill_rate", 0.33),
            jitter_factor=rate_limit_config.get("jitter_factor", 0.2)
        )
        
        # Request queue
        self.request_queue = RequestQueue(
            max_parallel=rate_limit_config.get("max_parallel", 3)
        )
        
        # Retry configuration
        self.max_retries = rate_limit_config.get("max_retries", 3)
        self.base_retry_delay = rate_limit_config.get("base_retry_delay", 2.0)
        self.max_retry_delay = rate_limit_config.get("max_retry_delay", 60.0)
        
        # Delay between consecutive requests (to avoid hammering the API)
        self.request_delay = rate_limit_config.get("request_delay", 0.5)
        self.last_request_time = 0
        
        # API endpoint
        self.api_endpoint = "https://openrouter.ai/api/v1/chat/completions"
        
        # Logging configuration
        self.log_dir = config.get("log_dir", "logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def _get_api_key(self, model: str) -> str:
        """Get the API key for a specific model.
        
        Args:
            model: The model identifier
            
        Returns:
            API key to use
        """
        # Check if we have a model-specific key
        if model in self.model_keys:
            return self.model_keys[model]
        
        # Fall back to default key
        return self.default_api_key
    
    async def _make_request(self, 
                          model: str, 
                          messages: List[Dict[str, str]], 
                          temperature: float = 0.7,
                          max_tokens: int = 1000,
                          retry_count: int = 0) -> Dict[str, Any]:
        """Make a request to the OpenRouter API with rate limiting and retries.
        
        Args:
            model: The model identifier
            messages: List of message dictionaries
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            retry_count: Current retry attempt
            
        Returns:
            API response dictionary
        """
        # Wait for rate limiter
        wait_time = await self.rate_limiter.acquire(model)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        # Ensure minimum delay between requests
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        
        # Update last request time
        self.last_request_time = time.time()
        
        # Prepare request
        api_key = self._get_api_key(model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # Log request
        request_id = f"{model}_{int(time.time())}_{random.randint(1000, 9999)}"
        log_model_request(model, request_id, messages)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_endpoint, 
                                       headers=headers, 
                                       json=payload, 
                                       timeout=60) as response:
                    
                    # Update rate limit information
                    self.rate_limiter.update_rate_limit_info(model, response.headers)
                    
                    # Handle response
                    if response.status == 200:
                        # Success
                        result = await response.json()
                        log_model_response(model, request_id, result)
                        return result
                    
                    elif response.status == 429:
                        # Rate limit exceeded
                        error_text = await response.text()
                        log_error(f"Rate limit exceeded for {model}: {error_text}")
                        
                        # Check if we should retry
                        if retry_count < self.max_retries:
                            # Calculate retry delay with exponential backoff and jitter
                            delay = min(
                                self.max_retry_delay,
                                self.base_retry_delay * (2 ** retry_count)
                            )
                            jitter = delay * 0.2 * random.random()
                            delay += jitter
                            
                            print(f"Rate limit exceeded. Retrying in {delay:.2f}s (attempt {retry_count+1}/{self.max_retries})")
                            await asyncio.sleep(delay)
                            
                            # Retry the request
                            return await self._make_request(
                                model, messages, temperature, max_tokens, retry_count + 1
                            )
                        else:
                            # Max retries exceeded
                            error_data = {
                                "error": {
                                    "message": f"Rate limit exceeded: {error_text}",
                                    "code": 429,
                                    "metadata": {
                                        "headers": dict(response.headers),
                                        "provider_name": None
                                    }
                                },
                                "user_id": "user_id"
                            }
                            return error_data
                    
                    else:
                        # Other error
                        error_text = await response.text()
                        log_error(f"API error for {model}: {response.status} - {error_text}")
                        
                        error_data = {
                            "error": {
                                "message": f"API error: {error_text}",
                                "code": response.status,
                                "metadata": {
                                    "headers": dict(response.headers),
                                    "provider_name": None
                                }
                            },
                            "user_id": "user_id"
                        }
                        return error_data
                        
        except asyncio.TimeoutError:
            log_error(f"Request timeout for {model}")
            
            # Check if we should retry
            if retry_count < self.max_retries:
                delay = min(
                    self.max_retry_delay,
                    self.base_retry_delay * (2 ** retry_count)
                )
                print(f"Request timeout. Retrying in {delay:.2f}s (attempt {retry_count+1}/{self.max_retries})")
                await asyncio.sleep(delay)
                
                # Retry the request
                return await self._make_request(
                    model, messages, temperature, max_tokens, retry_count + 1
                )
            else:
                # Max retries exceeded
                error_data = {
                    "error": {
                        "message": "Request timeout after multiple retries",
                        "code": 408,
                        "metadata": {
                            "retry_count": retry_count
                        }
                    },
                    "user_id": "user_id"
                }
                return error_data
                
        except Exception as e:
            log_error(f"Request error for {model}: {str(e)}")
            
            error_data = {
                "error": {
                    "message": f"Request error: {str(e)}",
                    "code": 500,
                    "metadata": {
                        "exception": str(e)
                    }
                },
                "user_id": "user_id"
            }
            return error_data
    
    async def generate_completion(self, 
                               model: str, 
                               messages: List[Dict[str, str]], 
                               temperature: float = 0.7,
                               max_tokens: int = 1000,
                               priority: int = 5) -> Dict[str, Any]:
        """Generate a completion using the OpenRouter API.
        
        Args:
            model: The model identifier
            messages: List of message dictionaries
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            priority: Request priority (lower is higher priority)
            
        Returns:
            API response dictionary
        """
        # Create a unique request ID
        request_id = f"{model}_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Create the coroutine
        coroutine = self._make_request(model, messages, temperature, max_tokens)
        
        # Add to queue and wait for result
        return await self.request_queue.add_request(priority, request_id, coroutine)
    
    async def generate_completion_with_fallback(self, 
                                            primary_model: str,
                                            backup_models: List[str],
                                            messages: List[Dict[str, str]],
                                            temperature: float = 0.7,
                                            max_tokens: int = 1000) -> Dict[str, Any]:
        """Generate a completion with fallback to backup models if primary fails.
        
        Args:
            primary_model: Primary model to try first
            backup_models: List of backup models to try if primary fails
            messages: List of message dictionaries
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            API response dictionary
        """
        # Try primary model first
        response = await self.generate_completion(
            primary_model, messages, temperature, max_tokens, priority=1
        )
        
        # Check if primary model succeeded
        if "error" not in response:
            return response
        
        # If primary model failed, try backup models
        for i, model in enumerate(backup_models):
            print(f"Primary model {primary_model} failed. Trying backup model {model}")
            
            # Add delay before trying backup model
            await asyncio.sleep(1.0)
            
            # Try backup model with lower priority
            response = await self.generate_completion(
                model, messages, temperature, max_tokens, priority=i+2
            )
            
            # Check if backup model succeeded
            if "error" not in response:
                return response
        
        # If all models failed, return the last error
        return response
    
    def log_api_response(self, role: str, model: str, status: str, response: Dict[str, Any]) -> None:
        """Log API response to a file.
        
        Args:
            role: The role making the request
            model: The model used
            status: Status of the request (success/error)
            response: API response dictionary
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"api_response_{model.replace('/', '_')}_{role}_{status}_{timestamp}.json"
        filepath = os.path.join(self.log_dir, filename)
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "role": role,
            "status": status,
            "response": response
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)