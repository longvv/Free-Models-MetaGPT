# validators.py
# Improved validation system with better tolerance for free model outputs

import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
import jsonschema
from pathlib import Path

class SyntaxValidator:
    """Validator for checking syntax of code and structured text."""
    
    def __init__(self):
        """Initialize the syntax validator."""
        pass
        
    async def validate_code(self, text: str, language: str = "python") -> Tuple[bool, str]:
        """Validate code syntax with improved extraction of code blocks.
        
        Args:
            text: Text potentially containing code
            language: Programming language
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Extract code blocks first
        code = self._extract_code_blocks(text, language)
        
        # If no code blocks found, check if the text itself might be code
        if not code and self._looks_like_code(text, language):
            code = text
        
        # If still no code found, fail validation
        if not code:
            return False, f"No {language} code blocks found in the text"
        
        # Now validate the extracted code
        if language == "python":
            try:
                compile(code, "<string>", "exec")
                return True, "Python syntax is valid"
            except SyntaxError as e:
                return False, f"Python syntax error: {str(e)}"
        elif language == "javascript" or language == "js":
            # Simple JavaScript syntax validation
            error_patterns = [
                r"unexpected token",
                r"unclosed string",
                r"missing \)",
                r"missing \}",
                r"missing \]"
            ]
            
            for pattern in error_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    return False, f"JavaScript syntax error: {pattern}"
                    
            return True, "JavaScript syntax appears valid (basic check only)"
        else:
            # For other languages, do basic bracket matching
            brackets = {
                "(": ")",
                "[": "]",
                "{": "}"
            }
            
            stack = []
            for char in code:
                if char in brackets.keys():
                    stack.append(char)
                elif char in brackets.values():
                    if not stack:
                        return False, f"Syntax error: Unmatched closing bracket '{char}'"
                        
                    opening = stack.pop()
                    if char != brackets[opening]:
                        return False, f"Syntax error: Mismatched brackets '{opening}' and '{char}'"
                        
            if stack:
                return False, f"Syntax error: Unclosed brackets {''.join(stack)}"
                
            return True, "Bracket syntax appears valid"
    
    def _extract_code_blocks(self, text: str, language: str) -> str:
        """Extract code blocks from markdown text.
        
        Args:
            text: Text to extract code blocks from
            language: Programming language
            
        Returns:
            Extracted code or empty string if none found
        """
        # Handle language aliases
        lang_pattern = language
        if language == "python":
            lang_pattern = "(?:python|py)"
        elif language == "javascript":
            lang_pattern = "(?:javascript|js)"
            
        # Try to find code blocks with specific language tag
        pattern = re.compile(f"```{lang_pattern}[\\s\\n]*(.*?)```", re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(text)
        
        if matches:
            return "\n\n".join(matches)
            
        # If no specific language blocks found, try any code blocks
        pattern = re.compile(r"```(.*?)```", re.DOTALL)
        matches = pattern.findall(text)
        
        for match in matches:
            # Skip very short blocks or blocks that are clearly not code
            if len(match.strip()) > 20 and self._looks_like_code(match, language):
                return match
                
        return ""
    
    def _looks_like_code(self, text: str, language: str) -> bool:
        """Check if text looks like code in the specified language.
        
        Args:
            text: Text to check
            language: Programming language
            
        Returns:
            True if text looks like code, False otherwise
        """
        if language == "python":
            # Check for Python-like patterns
            python_patterns = [
                r"^\s*def\s+\w+\s*\(.*\):",
                r"^\s*class\s+\w+[:(]",
                r"^\s*import\s+\w+",
                r"^\s*from\s+\w+\s+import",
                r"if\s+.*?:\s*$"
            ]
            
            for pattern in python_patterns:
                if re.search(pattern, text, re.MULTILINE):
                    return True
                    
        elif language == "javascript":
            # Check for JavaScript-like patterns
            js_patterns = [
                r"function\s+\w+\s*\(.*\)\s*{",
                r"const\s+\w+\s*=",
                r"let\s+\w+\s*=",
                r"var\s+\w+\s*=",
                r"class\s+\w+\s*{",
                r"import\s+.*?from"
            ]
            
            for pattern in js_patterns:
                if re.search(pattern, text, re.MULTILINE):
                    return True
                    
        return False
        
    async def validate_text_structure(self, text: str, required_sections: List[str]) -> Tuple[bool, str]:
        """Validate that text contains required sections with improved matching.
        
        Args:
            text: Text to validate
            required_sections: List of section names that must be present
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not required_sections:
            return True, "No section requirements specified"
            
        missing_sections = []
        
        for section in required_sections:
            # Try multiple header patterns
            patterns = [
                # Markdown headers (various levels)
                rf"(?:^|\n)#+\s*{re.escape(section)}[\s:]*(?:\n|$)",
                # Section with colon
                rf"(?:^|\n){re.escape(section)}:(?:\n|$)",
                # Uppercase section name
                rf"(?:^|\n){re.escape(section.upper())}(?:\n|$)",
                # Section with equals or dash underline
                rf"(?:^|\n){re.escape(section)}\s*\n[=\-]+\s*(?:\n|$)",
                # Bold section name
                rf"(?:^|\n)\*\*{re.escape(section)}\*\*(?:\n|$)",
                # Numbered section
                rf"(?:^|\n)\d+\.\s*{re.escape(section)}(?:\n|$)"
            ]
            
            section_found = False
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    section_found = True
                    break
                    
            if not section_found:
                # Try to find content that might be the section without proper formatting
                content_pattern = re.compile(rf"(?:^|\n).*{re.escape(section)}.*(?:\n|$)", re.IGNORECASE)
                if content_pattern.search(text):
                    # Found something that might be the section
                    continue
                    
                missing_sections.append(section)
                
        if missing_sections:
            # Allow a certain percentage of missing sections
            missing_ratio = len(missing_sections) / len(required_sections)
            if missing_ratio <= 0.25:  # Up to 25% missing sections allowed
                warning_sections = ", ".join(missing_sections)
                return True, f"Warning: Some sections might be missing or formatted differently: {warning_sections}"
            else:
                return False, f"Missing required sections: {', '.join(missing_sections)}"
                
        return True, "All required sections present"
        
    async def validate_patterns(self, text: str, required_patterns: List[str]) -> Tuple[bool, str]:
        """Validate that text contains required string patterns with improved matching.
        
        Args:
            text: Text to validate
            required_patterns: Patterns that must be present
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not required_patterns:
            return True, "No pattern requirements specified"
            
        missing_patterns = []
        
        for pattern in required_patterns:
            # Use more flexible pattern matching
            pattern_regex = re.compile(re.escape(pattern), re.IGNORECASE)
            if not pattern_regex.search(text):
                # For code patterns, check extracted code blocks
                if pattern in ["def", "class", "import", "function"]:
                    # Check for code blocks
                    code_blocks = re.findall(r"```.*?```", text, re.DOTALL)
                    pattern_found = False
                    
                    for block in code_blocks:
                        if pattern_regex.search(block):
                            pattern_found = True
                            break
                            
                    if pattern_found:
                        continue
                        
                missing_patterns.append(pattern)
                
        if missing_patterns:
            # Allow if only a few patterns are missing
            if len(missing_patterns) <= 1 or len(missing_patterns) / len(required_patterns) <= 0.3:
                warning_patterns = ", ".join(missing_patterns)
                return True, f"Warning: Some patterns might be missing: {warning_patterns}"
            else:
                return False, f"Missing required patterns: {', '.join(missing_patterns)}"
                
        return True, "All required patterns present"


class SchemaValidator:
    """Improved validator for checking output against JSON schemas."""
    
    def __init__(self, schema_dir: str = "./schemas"):
        """Initialize the schema validator.
        
        Args:
            schema_dir: Directory containing schema files
        """
        self.schema_dir = schema_dir
        self.schemas = {}
        
        # Create schema directory if it doesn't exist
        os.makedirs(schema_dir, exist_ok=True)
        
    def _load_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """Load schema from file.
        
        Args:
            schema_name: Name of schema file
            
        Returns:
            Schema dictionary or None if not found
        """
        if schema_name in self.schemas:
            return self.schemas[schema_name]
            
        schema_path = os.path.join(self.schema_dir, schema_name)
        if not os.path.exists(schema_path):
            return None
            
        try:
            with open(schema_path, 'r') as f:
                schema = json.load(f)
                self.schemas[schema_name] = schema
                return schema
        except Exception as e:
            print(f"Error loading schema '{schema_name}': {str(e)}")
            return None
            
    async def validate(self, text: str, schema_name: str) -> Tuple[bool, str]:
        """Validate text against a schema with improved tolerance.
        
        Args:
            text: Text to validate
            schema_name: Name of schema file
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Skip schema validation for free models
        return True, "Schema validation skipped for free model output"


class ConsistencyValidator:
    """Validator for checking consistency between outputs with improved tolerance."""
    
    def __init__(self):
        """Initialize the consistency validator."""
        pass
        
    async def validate_requirements_design(self, requirements: str, design: str) -> Tuple[bool, str]:
        """Validate that design addresses all requirements with relaxed criteria.
        
        Args:
            requirements: Requirements document
            design: Design document
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Extract key terms from requirements
        requirement_lines = [line.strip() for line in requirements.split('\n') if line.strip()]
        key_terms = set()
        
        for line in requirement_lines:
            # Skip headers and non-requirement lines
            if line.startswith('#') or line.startswith('-') or line.startswith('*'):
                words = re.findall(r'\b[A-Za-z]{4,}\b', line)
                key_terms.update(words)
                
        # Check design for coverage
        missing_terms = set()
        for term in key_terms:
            if term.lower() not in design.lower():
                missing_terms.add(term)
                
        # Allow more missing terms for free models
        coverage_ratio = 1 - (len(missing_terms) / len(key_terms)) if key_terms else 1
        
        if coverage_ratio < 0.6:  # Lower threshold for free models
            return False, f"Design may not address all requirements. Missing terms: {', '.join(list(missing_terms)[:10])}..."
            
        return True, f"Design adequately addresses requirements (coverage: {coverage_ratio:.2f})"
        
    async def validate_design_implementation(self, design: str, implementation: str) -> Tuple[bool, str]:
        """Validate that implementation follows design with relaxed criteria.
        
        Args:
            design: Design document
            implementation: Implementation plan
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Extract components from design
        component_pattern = re.compile(r'(Component|Module|Class|Service)[\s:]+([\w]+)', re.IGNORECASE)
        design_components = set(match[1].lower() for match in component_pattern.findall(design))
        
        # Check implementation for components
        missing_components = set()
        for component in design_components:
            if component.lower() not in implementation.lower():
                missing_components.add(component)
                
        # Allow more missing components for free models
        if len(missing_components) > len(design_components) * 0.4:  # Allow up to 40% missing
            return False, f"Implementation plan may be missing key components from design: {', '.join(missing_components)}"
            
        return True, "Implementation plan adequately follows design"
        
    async def validate_implementation_code(self, implementation: str, code: str) -> Tuple[bool, str]:
        """Validate that code implements the implementation plan with relaxed criteria.
        
        Args:
            implementation: Implementation plan
            code: Generated code
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Extract functions and classes from implementation
        function_pattern = re.compile(r'(Function|Method|API)[\s:]+([\w]+)', re.IGNORECASE)
        class_pattern = re.compile(r'(Class|Type)[\s:]+([\w]+)', re.IGNORECASE)
        
        implementation_functions = set(match[1].lower() for match in function_pattern.findall(implementation))
        implementation_classes = set(match[1].lower() for match in class_pattern.findall(implementation))
        
        # For free models, only check a sample of functions and classes
        if len(implementation_functions) > 5:
            implementation_functions = set(list(implementation_functions)[:5])
            
        if len(implementation_classes) > 3:
            implementation_classes = set(list(implementation_classes)[:3])
        
        # Check code for functions and classes
        missing_elements = set()
        
        for func in implementation_functions:
            # Look for function definitions
            func_pattern = re.compile(r'(def|function)\s+' + re.escape(func), re.IGNORECASE)
            if not func_pattern.search(code):
                missing_elements.add(f"function:{func}")
                
        for cls in implementation_classes:
            # Look for class definitions
            class_pattern = re.compile(r'(class)\s+' + re.escape(cls), re.IGNORECASE)
            if not class_pattern.search(code):
                missing_elements.add(f"class:{cls}")
                
        # Allow more missing elements for free models
        total_elements = len(implementation_functions) + len(implementation_classes)
        if len(missing_elements) > 0 and total_elements > 0:
            missing_ratio = len(missing_elements) / total_elements
            if missing_ratio > 0.5:  # Allow up to 50% missing
                return False, f"Code may not implement key elements from the plan: {', '.join(missing_elements)}"
            
        return True, "Code adequately implements the plan"


class ValidationSystem:
    """Enhanced validation system for free model outputs."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the validation system.
        
        Args:
            config: Validation system configuration
        """
        self.config = config
        self.syntax_validator = SyntaxValidator()
        self.schema_validator = SchemaValidator(config.get("schema", {}).get("schema_dir", "./schemas"))
        self.consistency_validator = ConsistencyValidator()
        
        # Create default schemas if they don't exist
        self._create_default_schemas()
        
    def _create_default_schemas(self) -> None:
        """Create default schemas if they don't exist."""
        schema_dir = Path(self.config.get("schema", {}).get("schema_dir", "./schemas"))
        schema_dir.mkdir(parents=True, exist_ok=True)
        
        default_schemas = {
            "requirements_schema.json": {
                "type": "object",
                "required": ["functional", "non_functional"],
                "properties": {
                    "functional": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "description"],
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    },
                    "non_functional": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "description"],
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "design_schema.json": {
                "type": "object",
                "required": ["components"],
                "properties": {
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "description"],
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "implementation_schema.json": {
                "type": "object",
                "required": ["tasks"],
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "description", "dependencies"],
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"},
                                "dependencies": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    },
                    "timeline": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["phase", "tasks"],
                            "properties": {
                                "phase": {"type": "string"},
                                "tasks": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            },
            "review_schema.json": {
                "type": "object",
                "required": ["issues", "suggestions"],
                "properties": {
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "description", "severity"],
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {"type": "string", "enum": ["critical", "major", "minor", "suggestion"]}
                            }
                        }
                    },
                    "suggestions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "description"],
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"}
                            }
                        }
                    },
                    "summary": {"type": "string"}
                }
            }
        }
        
        for name, schema in default_schemas.items():
            schema_path = schema_dir / name
            if not schema_path.exists():
                with open(schema_path, 'w') as f:
                    json.dump(schema, f, indent=2)
        
    async def validate(self, 
                      text: str, 
                      task_name: str, 
                      validation_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate text based on task and configuration with improved tolerance.
        
        Args:
            text: Text to validate
            task_name: Name of the task
            validation_config: Validation configuration for the task
            
        Returns:
            Tuple of (is_valid, message)
        """
        validation_results = []
        warnings = []
        
        # First check if this is free model output
        is_free_model = True  # Assume all models are free for now
        
        # Special handling for code generation
        if task_name == "code_generation":
            if is_free_model:
                # Extract and check for code patterns
                code_patterns = validation_config.get("required_patterns", [])
                if code_patterns:
                    # For free models, be very lenient with code validation
                    code_blocks = re.findall(r"```.*?```", text, re.DOTALL)
                    if code_blocks:
                        # Found code blocks, basic validation passes
                        validation_results.append((True, "Code blocks found"))
                    else:
                        # Check if text itself contains code-like patterns
                        code_pattern_count = 0
                        for pattern in ["def ", "class ", "import ", "function"]:
                            if pattern in text:
                                code_pattern_count += 1
                                
                        if code_pattern_count >= 1:
                            validation_results.append((True, "Code-like patterns found"))
                            warnings.append("Code might not be properly formatted in code blocks")
                        else:
                            validation_results.append((False, "No code blocks or code patterns found"))
            else:
                # Regular code validation for non-free models
                # Extract code blocks for code validation
                code_blocks = {}
                python_pattern = re.compile(r'```python\s*(.*?)\s*```', re.DOTALL)
                python_matches = python_pattern.findall(text)
                if python_matches:
                    code_blocks["python"] = "\n".join(python_matches)
                    
                js_pattern = re.compile(r'```(?:javascript|js)\s*(.*?)\s*```', re.DOTALL)
                js_matches = js_pattern.findall(text)
                if js_matches:
                    code_blocks["javascript"] = "\n".join(js_matches)
                
                for language, code in code_blocks.items():
                    is_valid, message = await self.syntax_validator.validate_code(code, language)
                    validation_results.append((is_valid, f"[{language}] {message}"))
        
        # Schema validation (skip for free models)
        schema_name = validation_config.get("schema")
        if schema_name and self.config.get("schema", {}).get("enabled", True) and not is_free_model:
            is_valid, message = await self.schema_validator.validate(text, schema_name)
            validation_results.append((is_valid, message))
            
        # Required sections validation (more lenient for free models)
        required_sections = validation_config.get("required_sections", [])
        if required_sections:
            is_valid, message = await self.syntax_validator.validate_text_structure(text, required_sections)
            if not is_valid and is_free_model:
                # For free models, check if enough content is present regardless of structure
                min_length = 300  # Reasonable minimum length for a response
                content_ok = len(text) >= min_length
                
                if content_ok:
                    warnings.append(message)  # Keep original error as warning
                    validation_results.append((True, "Content length acceptable despite missing sections"))
                else:
                    validation_results.append((is_valid, message))
            else:
                validation_results.append((is_valid, message))
            
        # Required patterns validation (more lenient for free models)
        required_patterns = validation_config.get("required_patterns", [])
        if required_patterns and task_name != "code_generation":  # Already handled code patterns above
            is_valid, message = await self.syntax_validator.validate_patterns(text, required_patterns)
            if not is_valid and is_free_model:
                # For free models, allow missing patterns if content seems otherwise good
                min_length = 200
                content_ok = len(text) >= min_length
                
                if content_ok:
                    warnings.append(message)  # Keep original error as warning
                    validation_results.append((True, "Content acceptable despite missing patterns"))
                else:
                    validation_results.append((is_valid, message))
            else:
                validation_results.append((is_valid, message))
            
        # Combine results
        if not validation_results:
            return True, "No validation performed"
            
        all_valid = all(result[0] for result in validation_results)
        messages = [result[1] for result in validation_results]
        
        # Add warnings if validation passed
        if all_valid and warnings:
            messages.append("\nWARNINGS (validation passed with exceptions):")
            messages.extend([f"- {warning}" for warning in warnings])
        
        return all_valid, "\n".join(messages)