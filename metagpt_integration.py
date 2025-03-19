# metagpt_integration.py
# Integration with MetaGPT framework

import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

class MetaGPTIntegration:
    """Integration with the MetaGPT framework."""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        """Initialize the MetaGPT integration.
        
        Args:
            workspace_dir: Directory containing workspace files
        """
        self.workspace_dir = Path(workspace_dir)
        
    def export_to_metagpt(self, output_dir: Optional[str] = None) -> str:
        """Export project to MetaGPT format.
        
        Args:
            output_dir: Output directory for MetaGPT files
            
        Returns:
            Path to exported MetaGPT directory
        """
        if output_dir is None:
            output_dir = self.workspace_dir / "metagpt_export"
            
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Copy and transform files
        self._export_requirements(output_dir)
        self._export_design(output_dir)
        self._export_implementation(output_dir)
        self._export_code(output_dir)
        
        return str(output_dir)
        
    def _export_requirements(self, output_dir: str) -> None:
        """Export requirements document to MetaGPT format.
        
        Args:
            output_dir: Output directory
        """
        requirements_path = self.workspace_dir / "requirements_doc.txt"
        if not requirements_path.exists():
            print(f"Warning: Requirements file not found at {requirements_path}")
            return
            
        # Read requirements
        with open(requirements_path, 'r') as f:
            requirements = f.read()
            
        # Write in MetaGPT format
        output_path = Path(output_dir) / "requirements.md"
        with open(output_path, 'w') as f:
            f.write("# Requirements\n\n")
            f.write(requirements)
            
        print(f"Exported requirements to {output_path}")
        
    def _export_design(self, output_dir: str) -> None:
        """Export design document to MetaGPT format.
        
        Args:
            output_dir: Output directory
        """
        design_path = self.workspace_dir / "design_doc.txt"
        if not design_path.exists():
            print(f"Warning: Design file not found at {design_path}")
            return
            
        # Read design
        with open(design_path, 'r') as f:
            design = f.read()
            
        # Write in MetaGPT format
        output_path = Path(output_dir) / "architecture_design.md"
        with open(output_path, 'w') as f:
            f.write("# Architecture Design\n\n")
            f.write(design)
            
        print(f"Exported design to {output_path}")
        
    def _export_implementation(self, output_dir: str) -> None:
        """Export implementation plan to MetaGPT format.
        
        Args:
            output_dir: Output directory
        """
        plan_path = self.workspace_dir / "implementation_plan.txt"
        if not plan_path.exists():
            print(f"Warning: Implementation plan not found at {plan_path}")
            return
            
        # Read plan
        with open(plan_path, 'r') as f:
            plan = f.read()
            
        # Write in MetaGPT format
        output_path = Path(output_dir) / "task_list.md"
        with open(output_path, 'w') as f:
            f.write("# Task List\n\n")
            f.write(plan)
            
        print(f"Exported implementation plan to {output_path}")
        
    def _export_code(self, output_dir: str) -> None:
        """Export source code to MetaGPT format.
        
        Args:
            output_dir: Output directory
        """
        code_path = self.workspace_dir / "source_code.txt"
        if not code_path.exists():
            print(f"Warning: Source code not found at {code_path}")
            return
            
        # Read code
        with open(code_path, 'r') as f:
            code = f.read()
            
        # Create code directory
        code_dir = Path(output_dir) / "code"
        os.makedirs(code_dir, exist_ok=True)
        
        # Try to extract individual files from the code
        self._extract_files_from_code(code, code_dir)
            
        print(f"Exported code to {code_dir}")
        
    def _extract_files_from_code(self, code: str, code_dir: Path) -> None:
        """Extract individual files from code document.
        
        Args:
            code: Code text
            code_dir: Directory to save extracted files
        """
        # Look for file headers in the format "# filename.py" or "```python # filename.py"
        import re
        
        # Try to find Python files
        python_pattern = re.compile(r'```python\s*#\s*([a-zA-Z0-9_\-\.]+\.py)\s*\n(.*?)```', re.DOTALL)
        py_matches = python_pattern.findall(code)
        
        if py_matches:
            for filename, content in py_matches:
                file_path = code_dir / filename
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"  - Extracted {filename}")
                
        # If no matches found, try to find other patterns or just save as a single file
        if not py_matches:
            # Try alternative pattern
            alt_pattern = re.compile(r'#\s*File:\s*([a-zA-Z0-9_\-\.]+\.py)\s*\n(.*?)(?=#\s*File:|$)', re.DOTALL)
            alt_matches = alt_pattern.findall(code)
            
            if alt_matches:
                for filename, content in alt_matches:
                    file_path = code_dir / filename
                    with open(file_path, 'w') as f:
                        f.write(content)
                    print(f"  - Extracted {filename}")
            else:
                # Just save as a single file
                file_path = code_dir / "main.py"
                with open(file_path, 'w') as f:
                    f.write(code)
                print(f"  - Saved all code as main.py")
