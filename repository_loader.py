#!/usr/bin/env python
# repository_loader.py
# Loads a git repository and prepares it for review

import os
import glob
import subprocess
from typing import Dict, List, Optional, Set
from pathlib import Path
import json

class RepositoryLoader:
    """Loads a repository and prepares its files for review."""
    
    def __init__(self, 
                repo_path: str,
                ignore_patterns: List[str] = None,
                max_file_size_kb: int = 500):
        """Initialize the repository loader.
        
        Args:
            repo_path: Path to the repository
            ignore_patterns: Patterns to ignore (glob format)
            max_file_size_kb: Maximum file size to process in KB
        """
        self.repo_path = Path(repo_path).resolve()
        self.ignore_patterns = ignore_patterns or [
            "**/.git/**", 
            "**/node_modules/**", 
            "**/__pycache__/**",
            "**/*.pyc",
            "**/venv/**",
            "**/.vscode/**",
            "**/.idea/**",
            "**/dist/**",
            "**/build/**",
            "**/*.min.js",
            "**/*.min.css"
        ]
        # Add patterns from .gitignore if it exists
        gitignore_path = self.repo_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Convert .gitignore pattern to glob pattern
                            if not line.startswith('/'):
                                # Pattern applies to any directory
                                self.ignore_patterns.append(f"**/{line}")
                            else:
                                # Pattern is relative to repo root
                                self.ignore_patterns.append(line[1:])  # Remove leading /
            except Exception as e:
                print(f"Error reading .gitignore: {str(e)}")
        
        # Add user-provided patterns
        if ignore_patterns:
            self.ignore_patterns.extend(ignore_patterns)
        self.max_file_size = max_file_size_kb * 1024  # Convert to bytes
        
    def get_file_list(self) -> List[str]:
        """Get list of files to process.
        
        Returns:
            List of file paths
        """
        all_files = []
        
        # Start from repo path
        for root, dirs, files in os.walk(self.repo_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]
            
            # Add non-ignored files
            for file in files:
                file_path = os.path.join(root, file)
                if not self._should_ignore(file_path):
                    # Check file size
                    if os.path.getsize(file_path) <= self.max_file_size:
                        all_files.append(file_path)
                    else:
                        print(f"Skipping large file: {file_path}")
        
        # Convert to relative paths
        relative_files = [os.path.relpath(f, self.repo_path) for f in all_files]
        return relative_files
    
    def _should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored.
        
        Args:
            path: Path to check
            
        Returns:
            True if the path should be ignored, False otherwise
        """
        rel_path = os.path.relpath(path, self.repo_path)
        
        for pattern in self.ignore_patterns:
            if glob.fnmatch.fnmatch(rel_path, pattern):
                return True
        
        return False
    
    def load_file_content(self, file_path: str) -> Optional[str]:
        """Load content of a file.
        
        Args:
            file_path: Path to file (relative to repo_path)
            
        Returns:
            File content or None if file couldn't be loaded
        """
        full_path = os.path.join(self.repo_path, file_path)
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading file {file_path}: {str(e)}")
            return None
    
    def analyze_repository(self) -> Dict:
        """Analyze repository structure and files.
        
        Returns:
            Dictionary with repository information
        """
        repo_info = {
            "files": [],
            "file_counts": {
                "py": 0,
                "js": 0,
                "html": 0,
                "css": 0,
                "md": 0,
                "json": 0,
                "other": 0
            },
            "total_lines": 0,
            "imports": {},
            "dependencies": []
        }
        
        # Get git information if available
        try:
            repo_info["git"] = {
                "remote": subprocess.check_output(
                    ["git", "-C", str(self.repo_path), "remote", "-v"],
                    universal_newlines=True
                ).strip(),
                "branch": subprocess.check_output(
                    ["git", "-C", str(self.repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
                    universal_newlines=True
                ).strip(),
                "last_commit": subprocess.check_output(
                    ["git", "-C", str(self.repo_path), "log", "-1", "--pretty=format:%h - %an, %ar : %s"],
                    universal_newlines=True
                ).strip()
            }
        except:
            repo_info["git"] = None
        
        # Process files
        files = self.get_file_list()
        
        for file_path in files:
            try:
                content = self.load_file_content(file_path)
                if content is None:
                    continue
                    
                lines = content.splitlines()
                line_count = len(lines)
                repo_info["total_lines"] += line_count
                
                ext = os.path.splitext(file_path)[1].lower()[1:]
                if ext in repo_info["file_counts"]:
                    repo_info["file_counts"][ext] += 1
                else:
                    repo_info["file_counts"]["other"] += 1
                
                # Extract imports/dependencies for certain file types
                imports = []
                if ext == "py":
                    imports = self._extract_python_imports(lines)
                elif ext == "js":
                    imports = self._extract_js_imports(lines)
                
                # Add file info
                repo_info["files"].append({
                    "path": file_path,
                    "lines": line_count,
                    "imports": imports
                })
                
                # Track imports
                for imp in imports:
                    if imp not in repo_info["imports"]:
                        repo_info["imports"][imp] = []
                    repo_info["imports"][imp].append(file_path)
                
            except Exception as e:
                print(f"Error processing file {file_path}: {str(e)}")
        
        # Try to find package dependencies
        if os.path.exists(os.path.join(self.repo_path, "requirements.txt")):
            try:
                with open(os.path.join(self.repo_path, "requirements.txt"), 'r') as f:
                    repo_info["dependencies"] = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            except:
                pass
        
        if os.path.exists(os.path.join(self.repo_path, "package.json")):
            try:
                with open(os.path.join(self.repo_path, "package.json"), 'r') as f:
                    package_json = json.load(f)
                    deps = {}
                    deps.update(package_json.get("dependencies", {}))
                    deps.update(package_json.get("devDependencies", {}))
                    repo_info["dependencies"].extend([f"{k}@{v}" for k, v in deps.items()])
            except:
                pass
        
        return repo_info
    
    def _extract_python_imports(self, lines: List[str]) -> List[str]:
        """Extract Python imports from lines of code.
        
        Args:
            lines: Lines of code
            
        Returns:
            List of imports
        """
        imports = []
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("import "):
                # Handle "import foo" or "import foo, bar"
                modules = line[7:].split(",")
                for module in modules:
                    base_module = module.strip().split(" as ")[0].split(".")[0]
                    imports.append(base_module)
            
            elif line.startswith("from "):
                # Handle "from foo import bar"
                parts = line.split(" import ")
                if len(parts) == 2:
                    base_module = parts[0][5:].split(".")[0]
                    imports.append(base_module)
        
        return list(set(imports))
    
    def _extract_js_imports(self, lines: List[str]) -> List[str]:
        """Extract JavaScript imports from lines of code.
        
        Args:
            lines: Lines of code
            
        Returns:
            List of imports
        """
        imports = []
        
        for line in lines:
            line = line.strip()
            
            if "import " in line or "require(" in line:
                # Extract quoted string
                start_indexes = []
                for char in ["'", '"', '`']:
                    if char in line:
                        start_idx = line.find(char)
                        if start_idx != -1:
                            start_indexes.append((start_idx, char))
                
                if start_indexes:
                    start_idx, quote_char = min(start_indexes, key=lambda x: x[0])
                    end_idx = line.find(quote_char, start_idx + 1)
                    
                    if end_idx != -1:
                        module_path = line[start_idx + 1:end_idx]
                        
                        # Handle relative imports and keep only module name
                        if not module_path.startswith("."):
                            # For npm packages, extract the package name (before slash or @version)
                            if "/" in module_path:
                                if module_path.startswith("@"):
                                    # Scoped package
                                    parts = module_path.split("/")
                                    if len(parts) >= 2:
                                        module_path = f"{parts[0]}/{parts[1]}"
                                else:
                                    # Regular package
                                    module_path = module_path.split("/")[0]
                            
                            imports.append(module_path)
        
        return list(set(imports))
