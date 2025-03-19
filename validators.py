# validators.py
# Validation system for model outputs

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
        
    async def validate_code(self, code: str, language: str = "python") -> Tuple[bool, str]:
        """Validate code syntax.
        
        Args:
            code: Code to validate
            language: Programming language
            
        Returns:
            Tuple of (is_valid, message)
        """
        if language == "python":
            try:
                compile(code, "<string>", "exec")
                return True, "Python syntax is valid"
            except SyntaxError as e:
                return False, f"Python syntax error: {str(e)}"
                
        elif language == "javascript" or language == "js":
            # Simple JavaScript syntax validation
            # This is very basic and only catches some common errors
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
        
    async def validate_text_structure(self, text: str, required_sections: List[str]) -> Tuple[bool, str]:
        """Validate that text contains required sections.
        
        Args:
            text: Text to validate
            required_sections: List of section names that must be present
            
        Returns:
            Tuple of (is_valid, message)
        """
        missing_sections = []
        
        for section in required_sections:
            # Check for markdown header patterns or just the section name
            pattern = re.compile(f"(^|\n)#+\s*{re.escape(section)}|{re.escape(section)}:", re.IGNORECASE)
            if not pattern.search(text):
                missing_sections.append(section)
                
        if missing_sections:
            return False, f"Missing required sections: {', '.join(missing_sections)}"
            
        return True, "All required sections present"
        
    async def validate_patterns(self, text: str, required_patterns: List[str]) -> Tuple[bool, str]:
        """Validate that text contains required string patterns.
        
        Args:
            text: Text to validate
            required_patterns: Patterns that must be present
            
        Returns:
            Tuple of (is_valid, message)
        """
        missing_patterns = []
        
        for pattern in required_patterns:
            if pattern not in text:
                missing_patterns.append(pattern)
                
        if missing_patterns:
            return False, f"Missing required patterns: {', '.join(missing_patterns)}"
            
        return True, "All required patterns present"


class SchemaValidator:
    """Validator for checking output against JSON schemas."""
    
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
        """Validate text against a schema.
        
        Args:
            text: Text to validate
            schema_name: Name of schema file
            
        Returns:
            Tuple of (is_valid, message)
        """
        schema = self._load_schema(schema_name)
        if not schema:
            return False, f"Schema '{schema_name}' not found"
            
        # Try to extract JSON from the text
        try:
            # Look for JSON patterns
            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            match = json_pattern.search(text)
            
            if match:
                # JSON found in code block
                json_text = match.group(1)
            else:
                # Try to see if the whole text is JSON
                json_text = text
                
            # Parse the JSON
            data = json.loads(json_text)
            
            # Validate against schema
            jsonschema.validate(data, schema)
            return True, "Validation successful"
            
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
            
        except jsonschema.exceptions.ValidationError as e:
            return False, f"Schema validation error: {str(e)}"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
            

class ConsistencyValidator:
    """Validator for checking consistency between outputs."""
    
    def __init__(self):
        """Initialize the consistency validator."""
        pass
        
    async def validate_requirements_design(self, requirements: str, design: str) -> Tuple[bool, str]:
        """Validate that design addresses all requirements.
        
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
                
        # Allow some missing terms
        coverage_ratio = 1 - (len(missing_terms) / len(key_terms)) if key_terms else 1
        
        if coverage_ratio < 0.8:  # Threshold for consistency
            return False, f"Design may not address all requirements. Missing terms: {', '.join(missing_terms)}"
            
        return True, f"Design appears to address requirements (coverage: {coverage_ratio:.2f})"
        
    async def validate_design_implementation(self, design: str, implementation: str) -> Tuple[bool, str]:
        """Validate that implementation follows design.
        
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
                
        if missing_components:
            return False, f"Implementation plan may be missing components from design: {', '.join(missing_components)}"
            
        return True, "Implementation plan appears to follow design"
        
    async def validate_implementation_code(self, implementation: str, code: str) -> Tuple[bool, str]:
        """Validate that code implements the implementation plan.
        
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
                
        if missing_elements:
            return False, f"Code may not implement all planned elements: {', '.join(missing_elements)}"
            
        return True, "Code appears to implement the plan"


class ValidationSystem:
    """Combined validation system for model outputs."""
    
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
        """Validate text based on task and configuration.
        
        Args:
            text: Text to validate
            task_name: Name of the task
            validation_config: Validation configuration for the task
            
        Returns:
            Tuple of (is_valid, message)
        """
        validation_results = []
        
        # Syntax validation
        if task_name == "code_generation" and self.config.get("syntax", {}).get("enabled", True):
            # Determine language from text or config
            language = "python"  # Default
            if "```python" in text:
                language = "python"
            elif "```javascript" in text or "```js" in text:
                language = "javascript"
                
            is_valid, message = await self.syntax_validator.validate_code(text, language)
            validation_results.append((is_valid, message))
            
        # Schema validation
        schema_name = validation_config.get("schema")
        if schema_name and self.config.get("schema", {}).get("enabled", True):
            is_valid, message = await self.schema_validator.validate(text, schema_name)
            validation_results.append((is_valid, message))
            
        # Required sections validation
        required_sections = validation_config.get("required_sections", [])
        if required_sections:
            is_valid, message = await self.syntax_validator.validate_text_structure(text, required_sections)
            validation_results.append((is_valid, message))
            
        # Required patterns validation
        required_patterns = validation_config.get("required_patterns", [])
        if required_patterns:
            is_valid, message = await self.syntax_validator.validate_patterns(text, required_patterns)
            validation_results.append((is_valid, message))
            
        # Consistency validation
        # This would require access to previous outputs
        # Not implemented in this example
        
        # Combine results
        if not validation_results:
            return True, "No validation performed"
            
        all_valid = all(result[0] for result in validation_results)
        messages = [result[1] for result in validation_results]
        
        return all_valid, "\n".join(messages)
