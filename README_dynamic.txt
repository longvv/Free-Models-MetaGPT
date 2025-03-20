# Enhanced Dynamic Configuration System for MetaGPT

This enhanced configuration system allows for dynamic management of models, roles, and workflows in MetaGPT, providing greater flexibility and customization.

## Overview

The dynamic configuration system consists of several key components:

1. **ModelRegistry**: Manages available models from OpenRouter and recommends the best models for specific tasks.
2. **RoleManager**: Handles role definitions and their associated prompts and configurations.
3. **WorkflowManager**: Manages workflow definitions that specify the sequence of tasks.
4. **DynamicConfigManager**: Coordinates between all components to provide a unified configuration interface.
5. **DynamicTaskOrchestrator**: Uses the dynamic configuration to execute tasks with the appropriate models and roles.

## Features

- **Dynamic Model Selection**: Automatically selects the best available models for each task based on capabilities and context size.
- **Role-based Prompting**: Uses specialized prompts for each role in the development process.
- **Customizable Workflows**: Define and reuse custom workflows with different stages and roles.
- **Command-line Interface**: Manage configurations, roles, and workflows easily through a CLI.
- **Backward Compatibility**: Works with existing configurations while providing enhanced flexibility.

## Usage

### Managing Roles

Custom roles can be created to specialize the system for specific tasks:

```yaml
name: Security Focused Workflow
description: A workflow that prioritizes security in the development process

stages:
  - task: requirements_analysis
    input: user_idea
    output: requirements_doc
    role: requirements_analysis

  - task: system_design
    input: requirements_doc
    output: design_doc
    role: system_design

  - task: security_analysis
    input: design_doc
    output: security_assessment
    role: security_expert

  - task: implementation_planning
    input: security_assessment
    output: implementation_plan
    role: implementation_planning

  - task: code_generation
    input: implementation_plan
    output: source_code
    role: code_generation

  - task: code_review
    input: source_code
    output: review_comments
    role: code_review
```

## Directory Structure

```
.
├── config.yml                        # Main configuration file
├── config_manager.py                 # Dynamic configuration system
├── config_cli.py                     # Command-line interface for configuration
├── enhanced_task_orchestrator_dynamic.py  # Task orchestrator with dynamic config
├── run_dynamic_metagpt.py            # Main script with dynamic config support
├── roles/                            # Custom role definitions
│   ├── security_expert.yml           # Security expert role
│   └── ...
├── workflows/                        # Custom workflow definitions
│   ├── security_focused.yml          # Security focused workflow
│   └── ...
└── workspace/                        # Output directory
```

## Creating Custom Roles

Custom roles allow you to specialize the system for specific tasks. Here's an example of creating a security expert role:

1. Create a file with the system prompt:

```bash
cat > security_prompt.txt << EOL
You are a senior cybersecurity expert with extensive experience in application security, infrastructure security, and secure system design. Your task is to analyze system architecture for security vulnerabilities and provide recommendations for secure implementation.

SECURITY ANALYSIS METHODOLOGY:
1. Threat modeling using STRIDE framework
2. Security assessment of authentication and authorization mechanisms
3. Analysis of data protection mechanisms
...
EOL
```

2. Create the role using the CLI:

```bash
python config_cli.py create-role security_expert \
  --display-name "Security Expert" \
  --description "Performs comprehensive security analysis" \
  --prompt-file security_prompt.txt
```

## Creating Custom Workflows

Custom workflows allow you to define specialized development processes:

1. Create a file with the workflow stages:

```bash
cat > security_workflow_stages.yml << EOL
- task: requirements_analysis
  input: user_idea
  output: requirements_doc
  role: requirements_analysis

- task: system_design
  input: requirements_doc
  output: design_doc
  role: system_design

- task: security_analysis
  input: design_doc
  output: security_assessment
  role: security_expert

...
EOL
```

2. Create the workflow using the CLI:

```bash
python config_cli.py create-workflow security_focused \
  --display-name "Security Focused Development" \
  --description "Prioritizes security in the SDLC" \
  --stages-file security_workflow_stages.yml
```

## Technical Details

### Model Selection Logic

The system uses the following criteria to select the best model for each task:

1. **Task Capability Matching**: Models are matched to tasks based on their capabilities (e.g., code generation, reasoning).
2. **Context Size**: Larger context windows are preferred for tasks that require more context.
3. **Availability**: Only available models (e.g., those that are free if `free_only` is enabled) are considered.
4. **Backup Models**: Each task has a backup model in case the primary model fails.

### Role-based Prompting

The system uses the following approach for role-based prompting:

1. Each role has a specific system prompt that guides the model behavior.
2. Roles can specify output formats, validation criteria, and model preferences.
3. The system prompt can be enhanced based on the model being used.

### Workflow Execution

Workflows are executed as follows:

1. Tasks are processed in the order defined in the workflow.
2. Each task uses the appropriate role and model configuration.
3. Outputs from previous tasks are provided as inputs to subsequent tasks.
4. Parallel execution is possible for tasks that don't depend on each other.

## Advanced Configuration

### Customizing Model Selection

You can customize how models are selected for specific tasks by modifying the `model_capabilities` in the `ModelRegistry` class:

```python
model_capabilities = {
    "requirements_analysis": ["deepseek-70b", "gemma-27b", "claude"],
    "system_design": ["gemma-27b", "deepseek-70b", "claude"],
    "code_generation": ["olympiccoder", "gemma-27b", "deepseek-70b"],
    # Add custom tasks here
}
```

### Extending with New Tasks

To add new task types to the system:

1. Add a new role definition in the `roles` directory.
2. Update workflows to include the new task.
3. Optionally, update the `model_capabilities` to provide model recommendations for the new task.

## Troubleshooting

### API Key Issues

If you encounter authentication errors:

1. Ensure your OpenRouter API key is set in `config.yml` or as the `OPENROUTER_API_KEY` environment variable.
2. Verify your API key with `python run_dynamic_metagpt.py list-models`.

### Model Availability

If certain models aren't working:

1. Run `python run_dynamic_metagpt.py list-models` to see which models are currently available.
2. Update your configuration with `python run_dynamic_metagpt.py update-config`.

### Role and Workflow Issues

If roles or workflows aren't behaving as expected:

1. Check that the role or workflow exists with `list-roles` or `list-workflows`.
2. Inspect the role or workflow definition for errors.
3. Try exporting and then reimporting the role or workflow to reset it.

## Future Enhancements

Some planned enhancements for the configuration system:

1. **Web-based Configuration Interface**: Graphical interface for managing configurations.
2. **Role Marketplace**: Share and discover custom roles created by the community.
3. **Workflow Templates**: Pre-made workflows for common development scenarios.
4. **Advanced Dependency Management**: More sophisticated task dependency resolution.
5. **Learning from Feedback**: Improve model recommendations based on task success rates.bash
# List available roles
python config_cli.py list-roles

# Create a custom role
python config_cli.py create-role security_expert --display-name "Security Expert" --description "Performs security analysis" --prompt-file security_prompt.txt

# Export a role to share with others
python config_cli.py export-role security_expert --output security_expert_role.yml

# Import a role from a file
python config_cli.py import-role security_expert --input security_expert_role.yml
```

### Managing Workflows

Create custom workflows to handle specialized development processes:

```bash
# List available workflows
python config_cli.py list-workflows

# Set the active workflow
python config_cli.py set-workflow security_focused

# Create a custom workflow
python config_cli.py create-workflow security_focused --display-name "Security Focused Development" --description "Prioritizes security in the SDLC" --stages-file security_workflow_stages.yml

# Export a workflow to share with others
python config_cli.py export-workflow security_focused --output security_workflow.yml

# Import a workflow from a file
python config_cli.py import-workflow security_focused --input security_workflow.yml
```

### Running Projects

Run projects with specific workflows and configurations:

```bash
# Run a project with standard workflow
python run_dynamic_metagpt.py run --idea "Create a secure REST API for user management"

# Run a project with a custom workflow
python run_dynamic_metagpt.py run --idea "Create a secure REST API for user management" --workflow security_focused

# Run in parallel mode
python run_dynamic_metagpt.py run --idea "Create a secure REST API for user management" --workflow security_focused --parallel
```

### Model Management

Manage available models and update configurations:

```bash
# List available models
python run_dynamic_metagpt.py list-models

# Update configuration with available models
python run_dynamic_metagpt.py update-config
```

## Configuration Files

### Role Definition

Roles are defined in YAML format:

```yaml
name: Security Expert
description: Performs comprehensive security analysis

system_prompt: |
  You are a senior cybersecurity expert...

output_format:
  sections:
    - Executive Summary
    - Threat Model
    - Detailed Findings
  validation:
    required_patterns:
      - OWASP
      - authentication
      - encryption

model_preferences:
  context_size: large
  reasoning: strong
  temperature: 0.1
```

### Workflow Definition

Workflows are defined in YAML format:

```