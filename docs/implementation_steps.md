# Implementation Steps for Code Reorganization

This document outlines the specific steps to implement the reorganization plan for separating fixed model and dynamic model approaches.

## Step 1: Create Directory Structure

```bash
# Create main directories
mkdir -p common/
mkdir -p fixed_model/
mkdir -p dynamic_model/
mkdir -p dynamic_model/roles/
```

## Step 2: Move and Rename Files

### Common Components
```bash
# Copy files to common directory with new names
cp enhanced_memory.py common/memory.py
cp enhanced_openrouter_adapter.py common/openrouter_adapter.py
cp enhanced_validators.py common/validators.py

# Create __init__.py for common package
touch common/__init__.py
```

### Fixed Model Components
```bash
# Copy files to fixed_model directory with new names
cp enhanced_task_orchestrator.py fixed_model/task_orchestrator.py
cp run_free_models_metagpt.py fixed_model/run.py

# Create __init__.py for fixed_model package
touch fixed_model/__init__.py
```

### Dynamic Model Components
```bash
# Copy files to dynamic_model directory with new names
cp config_manager.py dynamic_model/config_manager.py
cp enhanced_task_orchestrator_dynamic.py dynamic_model/task_orchestrator.py
cp run_dynamic_metagpt.py dynamic_model/run.py

# Create __init__.py for dynamic_model package
touch dynamic_model/__init__.py
touch dynamic_model/roles/__init__.py
```

## Step 3: Update Import Statements

### In common/memory.py
- Update imports to use relative imports where needed

### In common/openrouter_adapter.py
- Update imports to use relative imports where needed

### In fixed_model/task_orchestrator.py
- Change `from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter` to `from ..common.openrouter_adapter import EnhancedOpenRouterAdapter`
- Change `from enhanced_memory import EnhancedMemorySystem` to `from ..common.memory import EnhancedMemorySystem`
- Change `from validators import ValidationSystem` to `from ..common.validators import ValidationSystem`

### In fixed_model/run.py
- Change `from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter` to `from ..common.openrouter_adapter import EnhancedOpenRouterAdapter`
- Change `from enhanced_task_orchestrator import EnhancedTaskOrchestrator` to `from .task_orchestrator import EnhancedTaskOrchestrator`

### In dynamic_model/task_orchestrator.py
- Change `from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter` to `from ..common.openrouter_adapter import EnhancedOpenRouterAdapter`
- Change `from enhanced_memory import EnhancedMemorySystem` to `from ..common.memory import EnhancedMemorySystem`
- Change `from validators import ValidationSystem` to `from ..common.validators import ValidationSystem`
- Change `from config_manager import DynamicConfigManager` to `from .config_manager import DynamicConfigManager`

### In dynamic_model/run.py
- Change `from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter` to `from ..common.openrouter_adapter import EnhancedOpenRouterAdapter`
- Change `from enhanced_task_orchestrator_dynamic import DynamicTaskOrchestrator` to `from .task_orchestrator import DynamicTaskOrchestrator`
- Change `from config_manager import DynamicConfigManager` to `from .config_manager import DynamicConfigManager`

## Step 4: Create Root Package

```bash
# Create root __init__.py
touch __init__.py
```

Content for `__init__.py`:
```python
# Free-Models-MetaGPT package

# Import main components for easy access
from common.memory import EnhancedMemorySystem
from common.openrouter_adapter import EnhancedOpenRouterAdapter
from common.validators import ValidationSystem

# Provide shortcuts to both approaches
from fixed_model.task_orchestrator import EnhancedTaskOrchestrator
from dynamic_model.task_orchestrator import DynamicTaskOrchestrator
from dynamic_model.config_manager import DynamicConfigManager
```

## Step 5: Create Entry Point Scripts

### Create run_fixed.py
```python
#!/usr/bin/env python
# run_fixed.py - Entry point for fixed model approach

import sys
from fixed_model.run import main

if __name__ == "__main__":
    sys.exit(main())
```

### Create run_dynamic.py
```python
#!/usr/bin/env python
# run_dynamic.py - Entry point for dynamic model approach

import sys
from dynamic_model.run import main

if __name__ == "__main__":
    sys.exit(main())
```

## Step 6: Update Documentation

1. Update README.md to reflect the new structure
2. Add documentation about the two approaches and when to use each
3. Update any examples or tutorials to use the new structure

## Step 7: Testing

1. Test both approaches with the new structure
2. Verify that all functionality works as expected
3. Fix any issues that arise during testing

## Step 8: Cleanup

After confirming everything works correctly:

```bash
# Remove old files (only after confirming new structure works)
# rm enhanced_memory.py
# rm enhanced_openrouter_adapter.py
# rm enhanced_validators.py
# rm enhanced_task_orchestrator.py
# rm enhanced_task_orchestrator_dynamic.py
# rm run_free_models_metagpt.py
# rm run_dynamic_metagpt.py
# rm config_manager.py
```

**Note:** Keep the original files until the new structure is thoroughly tested and confirmed working.