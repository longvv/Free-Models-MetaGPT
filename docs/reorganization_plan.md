# Code Reorganization Plan: Fixed vs Dynamic Model Approaches

This document outlines a plan to reorganize the codebase to better separate the fixed model and dynamic model approaches while maintaining shared components.

## Current Structure Analysis

The codebase currently has two main approaches:

1. **Fixed Model Approach**: Uses predefined models in configuration
   - Entry point: `run_free_models_metagpt.py`
   - Core component: `enhanced_task_orchestrator.py`
   - Uses static configuration from `config.yml`

2. **Dynamic Model Approach**: Uses dynamic model selection and configuration
   - Entry point: `run_dynamic_metagpt.py`
   - Core component: `enhanced_task_orchestrator_dynamic.py`
   - Uses `config_manager.py` for dynamic configuration
   - Has additional features like role management

## Shared Components

- `enhanced_memory.py`: Memory system used by both approaches
- `enhanced_openrouter_adapter.py`: API adapter used by both approaches
- `enhanced_validators.py`: Validation system used by both approaches
- `schemas/`: JSON schemas used for validation

## Proposed Directory Structure

```
Free-Models-MetaGPT/
├── common/
│   ├── memory.py (from enhanced_memory.py)
│   ├── openrouter_adapter.py (from enhanced_openrouter_adapter.py)
│   ├── validators.py (from enhanced_validators.py)
│   └── utils.py (common utilities)
│
├── fixed_model/
│   ├── task_orchestrator.py (from enhanced_task_orchestrator.py)
│   └── run.py (from run_free_models_metagpt.py)
│
├── dynamic_model/
│   ├── config_manager.py (from config_manager.py)
│   ├── task_orchestrator.py (from enhanced_task_orchestrator_dynamic.py)
│   ├── run.py (from run_dynamic_metagpt.py)
│   └── roles/ (role definitions)
│
├── schemas/ (unchanged)
├── workflows/ (for both approaches)
├── config.yml (base configuration)
└── requirements.txt
```

## Migration Steps

1. Create the directory structure
2. Move files to their new locations with appropriate imports updated
3. Update import statements in all files to reflect new structure
4. Update configuration paths and references
5. Create appropriate `__init__.py` files for package structure

## Benefits of Reorganization

1. **Clear Separation of Concerns**: Each approach has its own directory
2. **Reduced Duplication**: Common components are shared
3. **Better Maintainability**: Easier to understand and modify each approach
4. **Improved Extensibility**: Easier to add new features to either approach
5. **Better Documentation**: Structure makes the differences between approaches clearer

## Implementation Considerations

- Ensure backward compatibility with existing scripts and configurations
- Update documentation to reflect new structure
- Add appropriate tests for each component
- Consider creating a unified CLI interface that can use either approach