#!/usr/bin/env python3
import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

class RoleConfigLoader:
    """Loads role configurations from individual files."""
    
    def __init__(self, roles_dir: Path):
        """Initialize the role config loader.
        
        Args:
            roles_dir: Directory containing role configuration files
        """
        self.roles_dir = roles_dir
        self.roles = {}
        
    def load_all_roles(self):
        """Load all role configuration files from the roles directory."""
        for role_file in self.roles_dir.glob("*.yml"):
            role_name = role_file.stem
            self.roles[role_name] = self.load_role(role_file)
        
        print(f"Loaded {len(self.roles)} role configurations")
        return self.roles
            
    def load_role(self, role_file: Path):
        """Load a specific role configuration file.
        
        Args:
            role_file: Path to the role configuration file
            
        Returns:
            Role configuration dictionary
        """
        with open(role_file, 'r') as f:
            role_config = yaml.safe_load(f)
        return role_config.get('role', {})
    
    def get_role(self, role_name: str):
        """Get a specific role configuration by name.
        
        Args:
            role_name: Name of the role to get configuration for
            
        Returns:
            Role configuration dictionary or None if not found
        """
        # Try to load from file if not already loaded
        if role_name not in self.roles:
            role_file = self.roles_dir / f"{role_name}.yml"
            if role_file.exists():
                self.roles[role_name] = self.load_role(role_file)
                
        return self.roles.get(role_name)

class EnhancedConfigManager:
    """Enhanced configuration manager that supports modular configuration files."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the enhanced configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or Path("/Users/rian.vu/Documents/Free-Models-MetaGPT/config")
        self.system_config = {}
        self.models_config = {}
        self.role_loader = None
        self.loaded = False
        
    async def initialize(self):
        """Initialize the configuration manager and load all configurations."""
        # Check if config directory exists
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {self.config_dir}")
        
        # Load system configuration
        system_file = self.config_dir / "system.yml"
        if system_file.exists():
            with open(system_file, 'r') as f:
                self.system_config = yaml.safe_load(f)
                
        # Load models configuration
        models_file = self.config_dir / "models.yml"
        if models_file.exists():
            with open(models_file, 'r') as f:
                self.models_config = yaml.safe_load(f)
        
        # Initialize role loader
        roles_dir = self.config_dir / "roles"
        if roles_dir.exists():
            self.role_loader = RoleConfigLoader(roles_dir)
            self.role_loader.load_all_roles()
        else:
            raise FileNotFoundError(f"Roles directory not found: {roles_dir}")
        
        self.loaded = True
        print("Enhanced configuration loaded successfully.")
    
    def check_loaded(self):
        """Check if configurations have been loaded."""
        if not self.loaded:
            raise RuntimeError("Configuration not loaded. Call initialize() first.")
    
    def get_system_config(self, section_name: Optional[str] = None):
        """Get system configuration section or full config.
        
        Args:
            section_name: Name of the section to get (optional)
            
        Returns:
            System configuration dictionary
        """
        self.check_loaded()
        
        if section_name:
            return self.system_config.get(section_name, {})
        return self.system_config
    
    def get_models_config(self):
        """Get models configuration.
        
        Returns:
            Models configuration dictionary
        """
        self.check_loaded()
        return self.models_config
    
    def get_api_keys(self):
        """Get API key configuration.
        
        Returns:
            API key configuration dictionary
        """
        self.check_loaded()
        return self.models_config.get('api_keys', {})
    
    def get_model_capabilities(self):
        """Get model capabilities configuration.
        
        Returns:
            Model capabilities dictionary
        """
        self.check_loaded()
        return self.models_config.get('models', {}).get('capabilities', {})
    
    def get_fallback_models(self):
        """Get fallback models configuration.
        
        Returns:
            List of fallback model IDs
        """
        self.check_loaded()
        return self.models_config.get('models', {}).get('fallback_free_models', [])
    
    def get_context_sizes(self):
        """Get model context sizes configuration.
        
        Returns:
            Dictionary of model context sizes
        """
        self.check_loaded()
        return self.models_config.get('models', {}).get('context_sizes', {})
    
    def get_role(self, role_name: str):
        """Get a specific role configuration.
        
        Args:
            role_name: Name of the role to get configuration for
            
        Returns:
            Role configuration dictionary or None if not found
        """
        self.check_loaded()
        if not self.role_loader:
            return None
        return self.role_loader.get_role(role_name)
    
    def get_all_roles(self):
        """Get all role configurations.
        
        Returns:
            Dictionary of all role configurations
        """
        self.check_loaded()
        if not self.role_loader:
            return {}
        return self.role_loader.roles
    
    def get_full_config(self):
        """Get a consolidated configuration dictionary (for backwards compatibility).
        
        Returns:
            Full configuration dictionary in the old format
        """
        self.check_loaded()
        
        # Reconstruct the original config.yml structure
        config = {}
        
        # Add API keys
        config["OPENROUTER_CONFIG"] = {
            "default_api_key": self.get_api_keys().get("default", ""),
            "model_keys": self.get_api_keys().get("model_specific", {})
        }
        
        # Add model registry
        config["MODEL_REGISTRY"] = {
            "model_capabilities": self.get_model_capabilities(),
            "fallback_free_models": self.get_fallback_models(),
            "model_context_sizes": self.get_context_sizes()
        }
        
        # Add system configs
        for key, value in self.system_config.items():
            config[key.upper()] = value
        
        # Add roles
        config["ROLES"] = {}
        for role_name, role_config in self.get_all_roles().items():
            config["ROLES"][role_name] = role_config
        
        return config
