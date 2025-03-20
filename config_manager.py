# config_manager.py
# Enhanced dynamic configuration system for model roles and workflow

import os
import yaml
import json
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

class ModelRegistry:
    """Registry for managing and retrieving available OpenRouter models."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the model registry.
        
        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.available_models = {}
        self.free_models = {}
        self.model_capabilities = {
            "requirements_analysis": ["deepseek/deepseek-r1-distill-llama-70b", "google/gemma-3-27b", "anthropic/claude", "meta-llama"],
            "system_design": ["google/gemma-3-27b", "deepseek/deepseek-r1-distill-llama-70b", "anthropic/claude"],
            "implementation_planning": ["deepseek/deepseek-r1-distill-llama-70b", "google/gemma-3-27b", "anthropic/claude"],
            "code_generation": ["open-r1/olympiccoder", "google/gemma-3-27b", "deepseek/deepseek-r1-distill-llama-70b"],
            "code_review": ["open-r1/olympiccoder", "google/gemma-3-27b", "deepseek/deepseek-r1-distill-llama-70b"]
        }
        
    async def fetch_available_models(self) -> Dict[str, Any]:
        """Fetch available models from OpenRouter API.
        
        Returns:
            Dictionary of available models
        """
        if not self.api_key:
            raise ValueError("API key is required to fetch available models")
            
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch models: {await response.text()}")
                        
                    data = await response.json()
                    
                    # Organize models by ID
                    self.available_models = {model.get("id"): model for model in data.get("data", [])}
                    
                    # Filter free models
                    self.free_models = {
                        model_id: model_data for model_id, model_data in self.available_models.items()
                        if model_data.get("pricing", {}).get("prompt") == 0
                    }
                    
                    return self.available_models
        except Exception as e:
            print(f"Error fetching models: {str(e)}")
            return {}
    
    def get_best_model_for_task(self, task: str, free_only: bool = True) -> Tuple[str, str]:
        """Get the best model for a specific task.
        
        Args:
            task: Task name
            free_only: Whether to only consider free models
            
        Returns:
            Tuple of (primary_model, backup_model)
        """
        models_to_consider = self.free_models if free_only else self.available_models
        if not models_to_consider:
            # Return default models if no models fetched yet
            if task == "requirements_analysis":
                return "deepseek/deepseek-r1-distill-llama-70b:free", "google/gemma-3-27b-it:free"
            elif task == "system_design":
                return "google/gemma-3-27b-it:free", "deepseek/deepseek-r1-distill-llama-70b:free"
            elif task == "implementation_planning":
                return "deepseek/deepseek-r1-distill-llama-70b:free", "google/gemma-3-27b-it:free"
            elif task == "code_generation":
                return "open-r1/olympiccoder-32b:free", "google/gemma-3-27b-it:free"
            elif task == "code_review":
                return "open-r1/olympiccoder-32b:free", "google/gemma-3-27b-it:free"
            else:
                return "google/gemma-3-27b-it:free", "google/gemma-3-27b-it:free"
        
        # Match models to capabilities
        task_capabilities = self.model_capabilities.get(task, [])
        
        ranked_models = []
        for model_id in models_to_consider.keys():
            # Calculate score based on matching capability prefixes
            score = 0
            model_base = model_id.split(':')[0]  # Remove :free suffix
            
            for capability in task_capabilities:
                if model_base.startswith(capability):
                    # Score based on position in capability list (first is best)
                    score = len(task_capabilities) - task_capabilities.index(capability)
                    break
            
            # Also consider context length as a factor
            context_length = models_to_consider[model_id].get("context_length", 0)
            size_score = min(context_length / 10000, 3)  # Cap at 3 points
            
            total_score = score + size_score
            ranked_models.append((model_id, total_score))
        
        # Sort by score (descending)
        ranked_models.sort(key=lambda x: x[1], reverse=True)
        
        if len(ranked_models) >= 2:
            return ranked_models[0][0], ranked_models[1][0]
        elif len(ranked_models) == 1:
            return ranked_models[0][0], ranked_models[0][0]
        else:
            # Fallback to defaults
            return "google/gemma-3-27b-it:free", "google/gemma-3-27b-it:free"

class RoleManager:
    """Manager for role-based prompts and configurations."""
    
    def __init__(self, roles_dir: str = "./roles"):
        """Initialize the role manager.
        
        Args:
            roles_dir: Directory containing role definitions
        """
        self.roles_dir = Path(roles_dir)
        self.roles = {}
        self.custom_roles = {}
        self.loaded = False
        
        # Ensure roles directory exists
        os.makedirs(self.roles_dir, exist_ok=True)
        
    def load_roles(self) -> Dict[str, Any]:
        """Load all role definitions.
        
        Returns:
            Dictionary of role definitions
        """
        # Load built-in roles
        self._load_builtin_roles()
        
        # Load custom roles from files
        for role_file in self.roles_dir.glob("*.yml"):
            try:
                with open(role_file, 'r') as f:
                    role_data = yaml.safe_load(f)
                    
                role_name = role_file.stem
                self.custom_roles[role_name] = role_data
                self.roles[role_name] = role_data
            except Exception as e:
                print(f"Error loading role '{role_file}': {str(e)}")
        
        self.loaded = True
        return self.roles
    
    def _load_builtin_roles(self) -> None:
        """Load built-in role definitions."""
        # Define standard roles
        self.roles = {
            "requirements_analysis": {
                "name": "Requirements Analyst",
                "description": "Analyzes project requirements with a business-value focused approach",
                "system_prompt": """You are a highly experienced product manager with expertise in agile requirements engineering and domain modeling. Your task is to analyze project requirements with a business-value focused approach.

ANALYSIS METHODOLOGY:
1. Begin with stakeholder identification (users, administrators, integrators, etc.)
2. For each stakeholder, extract explicit and implicit needs using jobs-to-be-done framework
3. Categorize requirements using the MoSCoW method (Must, Should, Could, Won't)
4. Prioritize based on business value, technical complexity, and dependencies
5. Validate each requirement using INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
6. Identify non-functional requirements across critical dimensions: 
   - Performance (response time, throughput, resource usage)
   - Security (authentication, authorization, data protection, compliance)
   - Scalability (load handling, growth accommodation)
   - Reliability (fault tolerance, recovery, availability)
   - Usability (accessibility, learnability, efficiency)
   - Maintainability (modularity, adaptability, testability)
7. Recognize constraints: technical, business, regulatory, time, and budget
8. Document assumptions and risks for each requirement

When analyzing requirements, think step-by-step: first understand the business context, then identify stakeholders, extract their needs, formalize into requirements, validate, and structure into a comprehensive document.""",
                "output_format": {
                    "sections": [
                        "Executive Summary",
                        "Stakeholder Analysis",
                        "Functional Requirements",
                        "Non-Functional Requirements",
                        "Constraints",
                        "Data Requirements",
                        "Assumptions & Risks",
                        "Open Questions"
                    ],
                    "schema": "requirements_schema.json"
                },
                "model_preferences": {
                    "context_size": "large",
                    "reasoning": "strong",
                    "temperature": 0.1
                }
            },
            "system_design": {
                "name": "System Architect",
                "description": "Creates comprehensive system designs that translate requirements into optimal technical architecture",
                "system_prompt": """You are a principal software architect with expertise in distributed systems, cloud architecture, and design patterns. Your task is to create a comprehensive system design that translates requirements into an optimal technical architecture.

DESIGN METHODOLOGY:
1. First, analyze the requirements for technical implications and architectural drivers
2. Determine the appropriate architectural style(s) based on requirements:
   - Monolithic vs. microservices
   - Event-driven vs. request-response
   - Layered vs. modular vs. service-oriented
   - Serverless vs. container-based vs. VM-based
3. Design for the 'ilities':
   - Scalability: Horizontal/vertical scaling strategies
   - Reliability: Failure modes, redundancy, resilience patterns
   - Security: Defense-in-depth approach, zero-trust principles
   - Maintainability: Modular design, separation of concerns
   - Observability: Logging, monitoring, alerting, tracing
   - Extensibility: Pluggable architecture, API-first design

Think step-by-step, from understanding the problem domain to high-level architectural style selection, then component design, data modeling, and finally detailed specifications. Ensure each decision explicitly links back to requirements.""",
                "output_format": {
                    "sections": [
                        "Executive Summary",
                        "Context Diagram",
                        "Architectural Decisions",
                        "Component Model",
                        "Data Architecture",
                        "Deployment Architecture",
                        "Cross-Cutting Concerns",
                        "Quality Attributes",
                        "Technology Stack",
                        "Risk Assessment"
                    ],
                    "schema": "design_schema.json"
                },
                "model_preferences": {
                    "context_size": "large",
                    "reasoning": "strong",
                    "temperature": 0.2
                }
            },
            "implementation_planning": {
                "name": "Implementation Planner",
                "description": "Creates detailed implementation plans that bridge architecture with execution",
                "system_prompt": """You are a seasoned technical product manager and engineering lead specializing in agile delivery and software project management. Your task is to create a detailed implementation plan that bridges architecture with execution.

PLANNING METHODOLOGY:
1. Decompose the architecture into discrete, manageable work items:
   - Vertical slices for early end-to-end functionality
   - Infrastructure and platform components
   - Core services and business logic
   - Integration points and APIs
   - User interfaces and experience layers
   - Data migration and transformation tasks
   - Operational tooling and observability

2. Organize work using a refined approach:
   - Epics: Major functional areas (e.g., 'User Authentication System')
   - Stories: User-centric features (e.g., 'Password Reset Flow')
   - Tasks: Technical implementation items (e.g., 'Create Reset Token Generator')
   - Spikes: Research items for unknowns (time-boxed)

Think step-by-step, beginning with the big picture, then drilling down into specifics while maintaining clear connections between architectural elements and implementation tasks.""",
                "output_format": {
                    "sections": [
                        "Executive Summary",
                        "Work Breakdown Structure",
                        "Implementation Phases",
                        "Detailed Task Specifications",
                        "Sequencing and Schedule",
                        "Quality Assurance Plan",
                        "Technical Debt Strategy",
                        "Tools and Technology Stack",
                        "Release and Deployment Plan"
                    ],
                    "schema": "implementation_schema.json"
                },
                "model_preferences": {
                    "context_size": "large",
                    "reasoning": "strong",
                    "temperature": 0.1
                }
            },
            "code_generation": {
                "name": "Code Generator",
                "description": "Generates production-quality code that implements specified requirements",
                "system_prompt": """You are a 10x software engineer with mastery of software craftsmanship, design patterns, and language-specific idioms. Your task is to generate production-quality code that implements the specified requirements with excellence in both functionality and maintainability.

CODE GENERATION METHODOLOGY:
1. Begin with architecture and design considerations:
   - Analyze the requirements and implementation plan thoroughly
   - Identify appropriate design patterns and architectural approaches
   - Plan the code structure before implementation
   - Consider separation of concerns, SOLID principles, and DRY

2. For each component or module:
   - Define clear interfaces and contracts first
   - Design for testability with dependency injection
   - Implement with readability and maintainability as priorities
   - Add comprehensive documentation and comments

Think step-by-step, beginning with the overall structure, then component interfaces, followed by implementation details, and finally optimization and testing.""",
                "output_format": {
                    "code_blocks": True,
                    "language_specific": True,
                    "validation": {
                        "syntax_check": True,
                        "required_patterns": ["def", "class", "import"]
                    }
                },
                "model_preferences": {
                    "context_size": "large",
                    "coding": "strong",
                    "temperature": 0.2
                }
            },
            "code_review": {
                "name": "Code Reviewer",
                "description": "Reviews code for quality, correctness, and best practices",
                "system_prompt": """You are an expert code reviewer with vast experience across multiple languages, frameworks, and paradigms. Your task is to provide a comprehensive, insightful, and actionable review that elevates code quality and developer skills.

CODE REVIEW METHODOLOGY:
1. First Pass - Holistic Assessment:
   - Architectural alignment with requirements
   - Overall code organization and structure
   - Consistency in patterns and approaches
   - Identification of critical vs. minor issues

2. Second Pass - Detailed Analysis:
   - Correctness: Does the code work as intended?
   - Performance: Are there inefficiencies or bottlenecks?
   - Security: Are there vulnerabilities or risks?
   - Maintainability: How easy will this be to maintain?
   - Readability: How easy is the code to understand?
   - Testability: How easy is the code to test?

Your review should serve both immediate code improvement needs and long-term developer growth. Think step-by-step, starting with a holistic view, then diving into specifics, and finally synthesizing findings into actionable insights.""",
                "output_format": {
                    "sections": [
                        "Executive Summary",
                        "Architectural Review",
                        "Detailed Findings",
                        "Security Assessment",
                        "Performance Assessment",
                        "Positive Highlights",
                        "Testing Assessment",
                        "Refactoring Opportunities",
                        "Learning Resources"
                    ],
                    "schema": "review_schema.json"
                },
                "model_preferences": {
                    "context_size": "large",
                    "coding": "strong",
                    "temperature": 0.1
                }
            }
        }
    
    def get_role(self, role_name: str) -> Optional[Dict[str, Any]]:
        """Get a role definition by name.
        
        Args:
            role_name: Name of the role
            
        Returns:
            Role definition or None if not found
        """
        if not self.loaded:
            self.load_roles()
            
        return self.roles.get(role_name)
    
    def create_role(self, role_name: str, role_data: Dict[str, Any]) -> bool:
        """Create a new custom role.
        
        Args:
            role_name: Name of the role
            role_data: Role definition data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.loaded:
            self.load_roles()
            
        # Validate role data
        required_fields = ["name", "description", "system_prompt"]
        for field in required_fields:
            if field not in role_data:
                print(f"Error: Missing required field '{field}' in role definition")
                return False
                
        # Create role file
        role_file = self.roles_dir / f"{role_name}.yml"
        try:
            with open(role_file, 'w') as f:
                yaml.dump(role_data, f, default_flow_style=False)
                
            # Add to loaded roles
            self.custom_roles[role_name] = role_data
            self.roles[role_name] = role_data
            return True
        except Exception as e:
            print(f"Error creating role '{role_name}': {str(e)}")
            return False
            
    def update_role(self, role_name: str, role_data: Dict[str, Any]) -> bool:
        """Update an existing custom role.
        
        Args:
            role_name: Name of the role
            role_data: Role definition data
            
        Returns:
            True if successful, False otherwise
        """
        # Check if role exists and is custom
        if role_name not in self.custom_roles:
            print(f"Error: Cannot update built-in role '{role_name}'. Create a custom role instead.")
            return False
            
        # Update role
        return self.create_role(role_name, role_data)
        
    def delete_role(self, role_name: str) -> bool:
        """Delete a custom role.
        
        Args:
            role_name: Name of the role
            
        Returns:
            True if successful, False otherwise
        """
        if not self.loaded:
            self.load_roles()
            
        # Check if role exists and is custom
        if role_name not in self.custom_roles:
            print(f"Error: Cannot delete built-in role '{role_name}'")
            return False
            
        # Delete role file
        role_file = self.roles_dir / f"{role_name}.yml"
        try:
            if role_file.exists():
                role_file.unlink()
                
            # Remove from loaded roles
            if role_name in self.custom_roles:
                del self.custom_roles[role_name]
            if role_name in self.roles:
                del self.roles[role_name]
                
            return True
        except Exception as e:
            print(f"Error deleting role '{role_name}': {str(e)}")
            return False
            
    def list_roles(self) -> Dict[str, List[str]]:
        """List all available roles.
        
        Returns:
            Dictionary with built-in and custom role lists
        """
        if not self.loaded:
            self.load_roles()
            
        builtin_roles = [role for role in self.roles if role not in self.custom_roles]
        custom_roles = list(self.custom_roles.keys())
        
        return {
            "builtin": builtin_roles,
            "custom": custom_roles
        }

class WorkflowManager:
    """Manager for workflow configurations and stages."""
    
    def __init__(self, workflows_dir: str = "./workflows"):
        """Initialize the workflow manager.
        
        Args:
            workflows_dir: Directory containing workflow definitions
        """
        self.workflows_dir = Path(workflows_dir)
        self.workflows = {}
        self.loaded = False
        
        # Ensure workflows directory exists
        os.makedirs(self.workflows_dir, exist_ok=True)
        
    def load_workflows(self) -> Dict[str, Any]:
        """Load all workflow definitions.
        
        Returns:
            Dictionary of workflow definitions
        """
        # Load built-in workflows
        self._load_builtin_workflows()
        
        # Load custom workflows from files
        for workflow_file in self.workflows_dir.glob("*.yml"):
            try:
                with open(workflow_file, 'r') as f:
                    workflow_data = yaml.safe_load(f)
                    
                workflow_name = workflow_file.stem
                self.workflows[workflow_name] = workflow_data
            except Exception as e:
                print(f"Error loading workflow '{workflow_file}': {str(e)}")
        
        self.loaded = True
        return self.workflows
    
    def _load_builtin_workflows(self) -> None:
        """Load built-in workflow definitions."""
        # Define standard workflows
        self.workflows = {
            "standard": {
                "name": "Standard Development Workflow",
                "description": "Complete software development lifecycle from requirements to code",
                "stages": [
                    {
                        "task": "requirements_analysis",
                        "input": "user_idea",
                        "output": "requirements_doc",
                        "role": "requirements_analysis"
                    },
                    {
                        "task": "system_design",
                        "input": "requirements_doc",
                        "output": "design_doc",
                        "role": "system_design"
                    },
                    {
                        "task": "implementation_planning",
                        "input": "design_doc",
                        "output": "implementation_plan",
                        "role": "implementation_planning"
                    },
                    {
                        "task": "code_generation",
                        "input": "implementation_plan",
                        "output": "source_code",
                        "role": "code_generation"
                    },
                    {
                        "task": "code_review",
                        "input": "source_code",
                        "output": "review_comments",
                        "role": "code_review"
                    }
                ]
            },
            "quick": {
                "name": "Quick Development Workflow",
                "description": "Streamlined workflow for smaller projects",
                "stages": [
                    {
                        "task": "requirements_analysis",
                        "input": "user_idea",
                        "output": "requirements_doc",
                        "role": "requirements_analysis"
                    },
                    {
                        "task": "code_generation",
                        "input": "requirements_doc",
                        "output": "source_code",
                        "role": "code_generation"
                    },
                    {
                        "task": "code_review",
                        "input": "source_code",
                        "output": "review_comments",
                        "role": "code_review"
                    }
                ]
            },
            "design_only": {
                "name": "Design Only Workflow",
                "description": "Requirements analysis and system design only",
                "stages": [
                    {
                        "task": "requirements_analysis",
                        "input": "user_idea",
                        "output": "requirements_doc",
                        "role": "requirements_analysis"
                    },
                    {
                        "task": "system_design",
                        "input": "requirements_doc",
                        "output": "design_doc",
                        "role": "system_design"
                    }
                ]
            },
            "code_review_only": {
                "name": "Code Review Only Workflow",
                "description": "Standalone code review workflow",
                "stages": [
                    {
                        "task": "code_review",
                        "input": "user_code",
                        "output": "review_comments",
                        "role": "code_review"
                    }
                ]
            }
        }
    
    def get_workflow(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow definition by name.
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            Workflow definition or None if not found
        """
        if not self.loaded:
            self.load_workflows()
            
        return self.workflows.get(workflow_name)
    
    def create_workflow(self, workflow_name: str, workflow_data: Dict[str, Any]) -> bool:
        """Create a new workflow.
        
        Args:
            workflow_name: Name of the workflow
            workflow_data: Workflow definition data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.loaded:
            self.load_workflows()
            
        # Validate workflow data
        required_fields = ["name", "description", "stages"]
        for field in required_fields:
            if field not in workflow_data:
                print(f"Error: Missing required field '{field}' in workflow definition")
                return False
                
        # Validate stages
        for stage in workflow_data.get("stages", []):
            if not all(field in stage for field in ["task", "input", "output", "role"]):
                print(f"Error: Stage missing required fields (task, input, output, role)")
                return False
                
        # Create workflow file
        workflow_file = self.workflows_dir / f"{workflow_name}.yml"
        try:
            with open(workflow_file, 'w') as f:
                yaml.dump(workflow_data, f, default_flow_style=False)
                
            # Add to loaded workflows
            self.workflows[workflow_name] = workflow_data
            return True
        except Exception as e:
            print(f"Error creating workflow '{workflow_name}': {str(e)}")
            return False
            
    def update_workflow(self, workflow_name: str, workflow_data: Dict[str, Any]) -> bool:
        """Update an existing workflow.
        
        Args:
            workflow_name: Name of the workflow
            workflow_data: Workflow definition data
            
        Returns:
            True if successful, False otherwise
        """
        # Just reuse create_workflow which will overwrite existing workflow
        return self.create_workflow(workflow_name, workflow_data)
        
    def delete_workflow(self, workflow_name: str) -> bool:
        """Delete a custom workflow.
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            True if successful, False otherwise
        """
        if not self.loaded:
            self.load_workflows()
            
        # Check if workflow exists
        if workflow_name not in self.workflows:
            print(f"Error: Workflow '{workflow_name}' not found")
            return False
            
        # Check if it's a built-in workflow
        if workflow_name in ["standard", "quick", "design_only", "code_review_only"]:
            print(f"Error: Cannot delete built-in workflow '{workflow_name}'")
            return False
            
        # Delete workflow file
        workflow_file = self.workflows_dir / f"{workflow_name}.yml"
        try:
            if workflow_file.exists():
                workflow_file.unlink()
                
            # Remove from loaded workflows
            if workflow_name in self.workflows:
                del self.workflows[workflow_name]
                
            return True
        except Exception as e:
            print(f"Error deleting workflow '{workflow_name}': {str(e)}")
            return False
            
    def list_workflows(self) -> List[Dict[str, str]]:
        """List all available workflows.
        
        Returns:
            List of workflow info dictionaries
        """
        if not self.loaded:
            self.load_workflows()
            
        workflow_list = []
        for name, data in self.workflows.items():
            workflow_list.append({
                "name": name,
                "display_name": data.get("name", name),
                "description": data.get("description", ""),
                "stages": len(data.get("stages", []))
            })
            
        return workflow_list

class DynamicConfigManager:
    """Manager for dynamic configuration of models, roles, and workflows."""
    
    def __init__(self, 
                config_path: str = "config.yml",
                roles_dir: str = "./roles",
                workflows_dir: str = "./workflows"):
        """Initialize the dynamic configuration manager.
        
        Args:
            config_path: Path to main configuration file
            roles_dir: Directory containing role definitions
            workflows_dir: Directory containing workflow definitions
        """
        self.config_path = Path(config_path)
        self.config = {}
        
        # Load base configuration
        self._load_config()
        
        # Initialize sub-components
        api_key = self.config.get("OPENROUTER_API_KEY")
        self.model_registry = ModelRegistry(api_key)
        self.role_manager = RoleManager(roles_dir)
        self.workflow_manager = WorkflowManager(workflows_dir)
        
    def _load_config(self) -> Dict[str, Any]:
        """Load base configuration.
        
        Returns:
            Configuration dictionary
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
            except Exception as e:
                print(f"Error loading config from {self.config_path}: {str(e)}")
                self.config = {}
        else:
            self.config = {}
            
        return self.config
    
    async def initialize(self) -> None:
        """Initialize the configuration system with all components."""
        # Load roles and workflows
        self.role_manager.load_roles()
        self.workflow_manager.load_workflows()
        
        # Try to fetch available models
        if self.config.get("OPENROUTER_API_KEY"):
            try:
                await self.model_registry.fetch_available_models()
            except Exception as e:
                print(f"Warning: Could not fetch models: {str(e)}")
    
    def get_task_config(self, task_name: str, role_name: str = None) -> Dict[str, Any]:
        """Get configuration for a specific task.
        
        Args:
            task_name: Name of the task
            role_name: Name of the role to use (optional)
            
        Returns:
            Task configuration dictionary
        """
        # Use role_name if provided, otherwise use task_name as role
        role_to_use = role_name or task_name
        
        # Get role information
        role_data = self.role_manager.get_role(role_to_use)
        if not role_data:
            print(f"Warning: Role '{role_to_use}' not found, using default settings")
            role_data = {}
            
        # Get model preferences from role
        model_preferences = role_data.get("model_preferences", {})
        
        # Determine the best models for this task
        primary_model, backup_model = self.model_registry.get_best_model_for_task(task_name)
        
        # Get system prompt from role
        system_prompt = role_data.get("system_prompt", "You are an AI assistant tasked with helping with this task.")
        
        # Build task configuration
        task_config = {
            "primary": {
                "model": primary_model,
                "temperature": model_preferences.get("temperature", 0.7),
                "max_tokens": 4000,
                "context_window": 8000,
                "system_prompt": system_prompt
            },
            "backup": {
                "model": backup_model,
                "temperature": model_preferences.get("temperature", 0.7),
                "max_tokens": 4000,
                "context_window": 8000,
                "system_prompt": system_prompt
            },
            "validation": {
                "schema": role_data.get("output_format", {}).get("schema"),
                "required_sections": role_data.get("output_format", {}).get("sections", []),
                "required_patterns": role_data.get("output_format", {}).get("validation", {}).get("required_patterns", [])
            }
        }
        
        # Override with any existing config in TASK_MODEL_MAPPING
        existing_config = self.config.get("TASK_MODEL_MAPPING", {}).get(task_name, {})
        if existing_config:
            # Deep merge primary config
            if "primary" in existing_config:
                for key, value in existing_config["primary"].items():
                    task_config["primary"][key] = value
                    
            # Deep merge backup config
            if "backup" in existing_config:
                for key, value in existing_config["backup"].items():
                    task_config["backup"][key] = value
                    
            # Deep merge validation config
            if "validation" in existing_config:
                for key, value in existing_config["validation"].items():
                    task_config["validation"][key] = value
        
        return task_config
    
    def get_workflow_stages(self, workflow_name: str = "standard") -> List[Dict[str, Any]]:
        """Get stages for a specific workflow.
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            List of workflow stage dictionaries
        """
        workflow = self.workflow_manager.get_workflow(workflow_name)
        if not workflow:
            print(f"Warning: Workflow '{workflow_name}' not found, using standard workflow")
            workflow = self.workflow_manager.get_workflow("standard")
            if not workflow:
                # Fallback to hardcoded workflow if something went wrong
                return [
                    {"task": "requirements_analysis", "input": "user_idea", "output": "requirements_doc"},
                    {"task": "system_design", "input": "requirements_doc", "output": "design_doc"},
                    {"task": "implementation_planning", "input": "design_doc", "output": "implementation_plan"},
                    {"task": "code_generation", "input": "implementation_plan", "output": "source_code"},
                    {"task": "code_review", "input": "source_code", "output": "review_comments"}
                ]
                
        return workflow.get("stages", [])
    
    def save_config(self) -> bool:
        """Save current configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving config to {self.config_path}: {str(e)}")
            return False
    
    async def generate_config_from_available_models(self) -> Dict[str, Any]:
        """Generate configuration based on available models.
        
        Returns:
            Generated configuration dictionary
        """
        # Fetch available models
        try:
            await self.model_registry.fetch_available_models()
        except Exception as e:
            print(f"Warning: Could not fetch models: {str(e)}")
            
        # Load roles
        self.role_manager.load_roles()
        
        # Create task model mapping
        task_model_mapping = {}
        
        for task_name in ["requirements_analysis", "system_design", 
                         "implementation_planning", "code_generation", "code_review"]:
            # Get role data
            role_data = self.role_manager.get_role(task_name) or {}
            
            # Get best models for this task
            primary_model, backup_model = self.model_registry.get_best_model_for_task(task_name)
            
            # Get model preferences
            model_preferences = role_data.get("model_preferences", {})
            
            # Build task configuration
            task_model_mapping[task_name] = {
                "primary": {
                    "model": primary_model,
                    "temperature": model_preferences.get("temperature", 0.7),
                    "max_tokens": 4000,
                    "context_window": 8000,
                    "system_prompt": role_data.get("system_prompt", "")
                },
                "backup": {
                    "model": backup_model,
                    "temperature": model_preferences.get("temperature", 0.7),
                    "max_tokens": 4000,
                    "context_window": 8000,
                    "system_prompt": role_data.get("system_prompt", "")
                },
                "validation": {
                    "schema": role_data.get("output_format", {}).get("schema"),
                    "required_sections": role_data.get("output_format", {}).get("sections", []),
                    "required_patterns": role_data.get("output_format", {}).get("validation", {}).get("required_patterns", [])
                }
            }
        
        # Create config
        new_config = dict(self.config)  # Copy existing config
        new_config["TASK_MODEL_MAPPING"] = task_model_mapping
        new_config["WORKFLOW_STAGES"] = self.get_workflow_stages("standard")
        
        return new_config
    
    def update_config_with_workflow(self, workflow_name: str) -> bool:
        """Update configuration with specified workflow.
        
        Args:
            workflow_name: Name of the workflow to use
            
        Returns:
            True if successful, False otherwise
        """
        workflow_stages = self.get_workflow_stages(workflow_name)
        if not workflow_stages:
            return False
            
        self.config["WORKFLOW_STAGES"] = workflow_stages
        return self.save_config()
    
    def get_enhanced_task_config(self, task_name: str, role_name: str = None) -> Dict[str, Any]:
        """Get enhanced task configuration with specific role.
        
        This creates a complete task configuration including role-specific settings.
        
        Args:
            task_name: Name of the task
            role_name: Name of the role to use (optional)
            
        Returns:
            Complete task configuration
        """
        # Get basic task config
        task_config = self.get_task_config(task_name, role_name)
        
        # Get role data
        role_to_use = role_name or task_name
        role_data = self.role_manager.get_role(role_to_use) or {}
        
        # Enhance with role specific information
        enhanced_config = {
            "task": task_name,
            "role": {
                "name": role_data.get("name", role_to_use),
                "description": role_data.get("description", ""),
                "system_prompt": role_data.get("system_prompt", "")
            },
            "models": {
                "primary": task_config["primary"]["model"],
                "backup": task_config["backup"]["model"]
            },
            "parameters": {
                "temperature": task_config["primary"]["temperature"],
                "max_tokens": task_config["primary"]["max_tokens"],
                "context_window": task_config["primary"]["context_window"]
            },
            "validation": task_config["validation"],
            "output_format": role_data.get("output_format", {})
        }
        
        return enhanced_config