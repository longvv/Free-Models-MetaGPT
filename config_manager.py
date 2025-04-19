# config_manager.py
# Enhanced dynamic configuration system for model roles and workflow

import os
import yaml
import json
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Load the main configuration file once
CONFIG_PATH = Path(__file__).parent / "config.yml"
CONFIG = {}
if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, 'r') as f:
            CONFIG = yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Could not load config.yml: {e}")

class ModelRegistry:
    """Registry for managing and retrieving available OpenRouter models."""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the model registry.
        
        Args:
            api_key: OpenRouter API key (overrides config and env var)
            config: Loaded configuration dictionary (e.g., from config.yml)
        """
        # API Key precedence: provided api_key > config > environment variable
        openrouter_config = config.get("OPENROUTER_CONFIG", {}) if config else CONFIG.get("OPENROUTER_CONFIG", {})
        self.api_key = api_key or openrouter_config.get("default_api_key") or os.getenv("OPENROUTER_API_KEY")
        self.model_keys = openrouter_config.get("model_keys", {})

        self.available_models = {}
        self.free_models = {}

        # Load model registry settings from config
        model_registry_config = config.get("MODEL_REGISTRY", {}) if config else CONFIG.get("MODEL_REGISTRY", {})
        self.model_capabilities = model_registry_config.get("model_capabilities", {})
        self.fallback_free_models_list = model_registry_config.get("fallback_free_models", [])
        self.default_models_by_task = model_registry_config.get("default_models_by_task", {})
        # Ensure a basic default exists if config is missing the 'default' key
        if "default" not in self.default_models_by_task:
            self.default_models_by_task["default"] = ["google/gemini-flash-1.5:free", "google/gemini-flash-1.5:free"] # A sensible, widely available free default
        
    # This patch should be applied to the ModelRegistry class in config_manager.py

    async def fetch_available_models(self) -> Dict[str, Any]:
        """Fetch available models from OpenRouter API.
        
        Returns:
            Dictionary of available models
        """
        if not self.api_key:
            print("Warning: API key not configured. Cannot fetch models. Using fallback free models.")
            self._use_fallback_free_models()
            return {}
            
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Warning: Failed to fetch models (Status: {response.status}). Using fallback free models. Error: {await response.text()}")
                        self._use_fallback_free_models()
                        return {}
                        
                    data = await response.json()
                    
                    # Organize models by ID
                    self.available_models = {model.get("id"): model for model in data.get("data", [])}
                    
                    # Filter free models: Look for models with ':free' suffix
                    self.free_models = {}
                    for model_id, model_data in self.available_models.items():
                        if model_id.endswith(':free'):
                            self.free_models[model_id] = model_data
                    
                    # If no free models detected, use fallback free models from config
                    if not self.free_models:
                        print("Warning: No free models detected from API. Using fallback list from config.")
                        self._use_fallback_free_models(check_available=True)
                    else:
                        # Ensure the models from config are included in free_models
                        # This ensures models explicitly configured in config.yml are always available
                        for model_id in self.fallback_free_models_list:
                            if model_id not in self.free_models:
                                self.free_models[model_id] = {
                                    "id": model_id,
                                    "context_length": 8000, 
                                    "description": "Added from config.yml free model list"
                                }
                    
                    print(f"Found {len(self.available_models)} total models")
                    print(f"Found {len(self.free_models)} free models")
                    
                    return self.available_models
        except Exception as e:
            print(f"Error fetching models: {str(e)}. Using fallback free models.")
            self._use_fallback_free_models()
            return {}

    def _use_fallback_free_models(self, check_available: bool = False):
        """Populate free_models using the fallback list from config."""
        self.free_models = {}
        for model_id in self.fallback_free_models_list:
            if check_available and model_id in self.available_models:
                # If checking available models, only add if it exists in the full list
                self.free_models[model_id] = self.available_models[model_id]
            elif not check_available:
                # If not checking (e.g., API failed), create minimal info
                self.free_models[model_id] = {
                    "id": model_id,
                    "context_length": 8000, # Assume a default context length
                    "description": "Fallback free model (API fetch failed or no free models found)"
                }
        print(f"Using {len(self.free_models)} fallback free models from config.")

    def get_api_key_for_model(self, model_id: str) -> Optional[str]:
        """Get the specific API key for a model, falling back to default or env var."""
        return self.model_keys.get(model_id, self.api_key)
    
    def get_best_model_for_task(self, task: str, free_only: bool = True) -> Tuple[str, str]:
        """Get the best model for a specific task based on config capabilities.
        
        Args:
            task: Task name (e.g., 'code_generation')
            free_only: Whether to only consider free models
            
        Returns:
            Tuple of (primary_model, backup_model)
        """
        models_to_consider = self.free_models if free_only else self.available_models
        
        # Use default models from config if no models fetched/available
        if not models_to_consider:
            print(f"Warning: No {'free ' if free_only else ''}models available for task '{task}'. Using default models from config.")
            defaults = self.default_models_by_task.get(task, self.default_models_by_task.get("default"))
            return defaults[0], defaults[1] if len(defaults) > 1 else defaults[0]
        
        # Match models to capabilities defined in config
        task_capabilities = self.model_capabilities.get(task, [])
        
        # Handle empty case - use default models from config
        if not task_capabilities:
            print(f"No capabilities defined for task '{task}'. Using default models from config.")
            defaults = self.default_models_by_task.get(task, self.default_models_by_task.get("default"))
            return defaults[0], defaults[1] if len(defaults) > 1 else defaults[0]
        
        ranked_models = []
        for model_id in models_to_consider.keys():
            # Calculate score based on matching capability prefixes
            score = 0
            model_base = model_id.split(':')[0]  # Remove :free suffix if present
            
            for capability in task_capabilities:
                # Use exact model ID comparison to avoid partial prefix matching
                if capability == model_base or model_id == capability:
                    # Score based on position in capability list (first is best)
                    score = len(task_capabilities) - task_capabilities.index(capability)
                    break
            
            # Also consider context length as a factor
            context_length = models_to_consider[model_id].get("context_length", 0)
            # Normalize context length score (e.g., 1 point per 16k context, capped)
            size_score = min(context_length / 16000, 5) 
            
            total_score = score + size_score
            ranked_models.append((model_id, total_score))
        
        # Sort by score (descending)
        ranked_models.sort(key=lambda x: x[1], reverse=True)
        
        if len(ranked_models) >= 2:
            return ranked_models[0][0], ranked_models[1][0]
        elif len(ranked_models) == 1:
            return ranked_models[0][0], ranked_models[0][0]
        else:
            # Fallback to defaults from config if no suitable model found after ranking
            print(f"Warning: No suitable {'free ' if free_only else ''}model found for task '{task}' after ranking. Using default models from config.")
            defaults = self.default_models_by_task.get(task, self.default_models_by_task.get("default"))
            return defaults[0], defaults[1] if len(defaults) > 1 else defaults[0]

class RoleManager:
    """Manager for role-based prompts and configurations loaded from config.yml."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the role manager.
        
        Args:
            config: Loaded configuration dictionary (e.g., from config.yml)
        """
        self.roles = config.get("ROLES", {}) if config else CONFIG.get("ROLES", {})
        if not self.roles:
            print("Warning: No roles found in configuration.")
        self.loaded = bool(self.roles)
        
    def load_roles(self) -> Dict[str, Any]:
        """Returns the loaded role definitions.
        
        Returns:
            Dictionary of role definitions
        """
        # Roles are now loaded during __init__ from the main config
        return self.roles

    def get_role(self, role_name: str) -> Optional[Dict[str, Any]]:
        """Get definition for a specific role.
        
        Args:
            role_name: Name of the role
            
        Returns:
            Role definition dictionary or None if not found
        """
        return self.roles.get(role_name)

    def get_system_prompt(self, role_name: str) -> Optional[str]:
        """Get the system prompt for a specific role.
        
        Args:
            role_name: Name of the role
            
        Returns:
            System prompt string or None if not found
        """
        role = self.get_role(role_name)
        return role.get("system_prompt") if role else None

    def get_output_format(self, role_name: str) -> Optional[Dict[str, Any]]:
        """Get the output format specification for a specific role.
        
        Args:
            role_name: Name of the role
            
        Returns:
            Output format dictionary or None if not found
        """
        role = self.get_role(role_name)
        return role.get("output_format") if role else None

    def get_model_preferences(self, role_name: str) -> Optional[Dict[str, Any]]:
        """Get the model preferences for a specific role.
        
        Args:
            role_name: Name of the role
            
        Returns:
            Model preferences dictionary or None if not found
        """
        role = self.get_role(role_name)
        return role.get("model_preferences") if role else None

class DynamicConfigManager:
    """Dynamic configuration manager for loading and managing configuration."""
    
    def __init__(self, config_path: str):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to configuration file
        """
        # Convert string path to Path object
        if isinstance(config_path, str):
            # Handle both absolute and relative paths
            if os.path.isabs(config_path):
                self.config_path = Path(config_path)
            else:
                # Try relative to current directory
                if os.path.exists(config_path):
                    self.config_path = Path(os.path.abspath(config_path))
                else:
                    # Try relative to script directory
                    script_dir = Path(__file__).parent
                    alt_path = script_dir / config_path
                    if alt_path.exists():
                        self.config_path = alt_path
                    else:
                        # Just store the path and we'll check existence in initialize()
                        self.config_path = Path(config_path)
        else:
            self.config_path = config_path
            
        self.config = {}
        self.model_registry = None
        self.role_manager = None
        self.loaded = False
        
    async def initialize(self) -> None:
        """Load configuration and initialize managers."""
        if not self.config_path.exists():
            # Try to find the config file in common locations
            potential_paths = [
                self.config_path,
                Path(os.getcwd()) / self.config_path.name,
                Path(__file__).parent / self.config_path.name,
                Path(__file__).parent / "config" / self.config_path.name
            ]
            
            for path in potential_paths:
                if path.exists():
                    self.config_path = path
                    break
            else:
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            raise IOError(f"Error loading configuration file {self.config_path}: {str(e)}")
            
        # Initialize Model Registry with config
        self.model_registry = ModelRegistry(config=self.config)
        await self.model_registry.fetch_available_models() # Fetch models upon initialization
        
        # Initialize Role Manager with config
        self.role_manager = RoleManager(config=self.config)
        self.role_manager.load_roles() # Load roles from config
        
        self.loaded = True
        print("Dynamic configuration loaded successfully.")

    def get_config_section(self, section_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific section from the loaded configuration.
        
        Args:
            section_name: Name of the configuration section (e.g., 'OPENROUTER_CONFIG')
            
        Returns:
            Configuration section dictionary or None if not found
        """
        if not self.loaded:
            raise RuntimeError("Configuration not loaded. Call initialize() first.")
        return self.config.get(section_name)

    def get_model_registry(self) -> ModelRegistry:
        """Get the initialized ModelRegistry instance."""
        if not self.loaded or not self.model_registry:
            raise RuntimeError("ModelRegistry not initialized. Call initialize() first.")
        return self.model_registry

    def get_role_manager(self) -> RoleManager:
        """Get the initialized RoleManager instance."""
        if not self.loaded or not self.role_manager:
            raise RuntimeError("RoleManager not initialized. Call initialize() first.")
        return self.role_manager

    def get_workflow_stages(self, workflow_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get the stages for a specific workflow by loading its YAML file.
        
        Args:
            workflow_name: Name of the workflow (corresponds to a file in workflows/)
            
        Returns:
            List of workflow stage dictionaries or None if not found
        """
        if not self.loaded:
            raise RuntimeError("Configuration not loaded. Call initialize() first.")
            
        workflow_dir = self.config_path.parent / "workflows"
        workflow_file = workflow_dir / f"{workflow_name}.yml"
        
        if not workflow_file.exists():
            print(f"Warning: Workflow file not found: {workflow_file}")
            # Attempt to load from WORKFLOWS section in main config as a fallback
            workflows_section = self.config.get("WORKFLOWS")
            if workflows_section and workflow_name in workflows_section:
                print(f"Loading workflow '{workflow_name}' from main config.")
                return workflows_section.get(workflow_name)
            return None
            
        try:
            with open(workflow_file, 'r') as f:
                workflow_config = yaml.safe_load(f)
                # Assuming the stages are the top-level list in the YAML
                if isinstance(workflow_config, list):
                    return workflow_config
                # Or if they are under a specific key like 'stages'
                elif isinstance(workflow_config, dict) and 'stages' in workflow_config:
                     return workflow_config.get('stages')
                else:
                    print(f"Warning: Unexpected format in workflow file: {workflow_file}")
                    return None
        except Exception as e:
            print(f"Error loading workflow file {workflow_file}: {str(e)}")
            return None

# Example usage (optional, for testing)
async def main():
    config_manager = DynamicConfigManager()
    try:
        await config_manager.initialize()
        
        # Access config sections
        openrouter_config = config_manager.get_config_section("OPENROUTER_CONFIG")
        # print("OpenRouter Config:", openrouter_config)
        
        # Access Model Registry
        model_registry = config_manager.get_model_registry()
        print("Available Free Models:", list(model_registry.free_models.keys()))
        primary, backup = model_registry.get_best_model_for_task("code_generation")
        print(f"Best models for code_generation: Primary={primary}, Backup={backup}")
        
        # Access Role Manager
        role_manager = config_manager.get_role_manager()
        analyst_prompt = role_manager.get_system_prompt("requirements_analysis")
        print("\nRequirements Analyst Prompt Snippet:", analyst_prompt[:100] + "...")
        
        # Access Workflow
        collab_workflow = config_manager.get_workflow_stages("collaborative")
        print("\nCollaborative Workflow Stages:", [stage['name'] for stage in collab_workflow])
        
    except Exception as e:
        print(f"Error during example usage: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())