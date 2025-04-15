#!/usr/bin/env python
# repo_code_review.py
# Code review workflow for an entire repository

import os
import yaml
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import markdown

from repository_loader import RepositoryLoader
from enhanced_openrouter_adapter import EnhancedOpenRouterAdapter
from enhanced_memory import EnhancedMemorySystem

class RepoReviewer:
    """Code review for entire repositories using AI models."""
    
    def __init__(self, 
                config_path: str,
                repo_path: str,
                output_dir: str = "./review_output",
                max_files_per_batch: int = 5,
                review_depth: str = "basic"):
        """Initialize the repository reviewer.
        
        Args:
            config_path: Path to configuration file
            repo_path: Path to repository to review
            output_dir: Directory to save review results
            max_files_per_batch: Maximum number of files to review in a batch
            review_depth: Review depth (basic, standard, deep)
        """
        self.config_path = config_path
        self.repo_path = repo_path
        self.output_dir = Path(output_dir)
        self.max_files_per_batch = max_files_per_batch
        self.review_depth = review_depth
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        # Initialize OpenRouter adapter
        self.adapter = EnhancedOpenRouterAdapter(self.config)
        
        # Initialize memory system
        memory_config = self.config.get("MEMORY_SYSTEM", {})
        self.memory = EnhancedMemorySystem(memory_config)
        
        # Initialize repository loader
        self.repo_loader = RepositoryLoader(repo_path)
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def review_repository(self) -> Dict[str, Any]:
        """Review the entire repository.
        
        Returns:
            Review results dictionary
        """
        print(f"Analyzing repository: {self.repo_path}")
        repo_info = self.repo_loader.analyze_repository()
        
        # Save repository info
        with open(self.output_dir / "repo_info.json", 'w') as f:
            json.dump(repo_info, f, indent=2)
            
        print(f"Repository structure:")
        print(f"- Total files: {len(repo_info['files'])}")
        print(f"- File types: {repo_info['file_counts']}")
        print(f"- Total lines: {repo_info['total_lines']}")
        
        # First, generate repository-level review
        print("Generating repository-level review...")
        repo_level_review = await self._generate_repo_level_review(repo_info)
        
        # Save repository-level review
        with open(self.output_dir / "repository_review.md", 'w') as f:
            f.write(repo_level_review)
            
        # Generate HTML version
        with open(self.output_dir / "repository_review.html", 'w') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Repository Review</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; color: #333; }}
                    pre {{ background-color: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }}
                    code {{ font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; }}
                    h1, h2, h3, h4 {{ margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; }}
                    h1 {{ padding-bottom: .3em; font-size: 2em; border-bottom: 1px solid #eaecef; }}
                    h2 {{ padding-bottom: .3em; font-size: 1.5em; border-bottom: 1px solid #eaecef; }}
                    h3 {{ font-size: 1.25em; }}
                    h4 {{ font-size: 1em; }}
                    blockquote {{ padding: 0 1em; color: #6a737d; border-left: 0.25em solid #dfe2e5; }}
                    table {{ border-collapse: collapse; margin: 20px 0; }}
                    table, th, td {{ border: 1px solid #ddd; }}
                    th, td {{ padding: 12px 15px; text-align: left; }}
                    tr:nth-child(even) {{ background-color: #f6f8fa; }}
                </style>
            </head>
            <body>
                {markdown.markdown(repo_level_review, extensions=['fenced_code', 'tables'])}
            </body>
            </html>
            """)
            
        # Group files by extension
        files_by_ext = {}
        for file_info in repo_info["files"]:
            ext = os.path.splitext(file_info["path"])[1].lower()
            if ext not in files_by_ext:
                files_by_ext[ext] = []
            files_by_ext[ext].append(file_info["path"])
            
        # Prioritize file review
        prioritized_files = self._prioritize_files(repo_info)
        
        # Review files in batches
        file_reviews = {}
        total_files = len(prioritized_files)
        
        for i in range(0, total_files, self.max_files_per_batch):
            batch = prioritized_files[i:i + self.max_files_per_batch]
            print(f"Reviewing batch {i//self.max_files_per_batch + 1}/{(total_files + self.max_files_per_batch - 1)//self.max_files_per_batch}...")
            
            batch_reviews = await self._review_file_batch(batch)
            file_reviews.update(batch_reviews)
            
            # Save interim results
            with open(self.output_dir / "file_reviews.json", 'w') as f:
                json.dump(file_reviews, f, indent=2)
        
        # Generate final summary report
        print("Generating final summary report...")
        summary_report = await self._generate_summary_report(repo_info, file_reviews)
        
        # Save summary report
        with open(self.output_dir / "review_summary.md", 'w') as f:
            f.write(summary_report)
            
        # Generate HTML version
        with open(self.output_dir / "review_summary.html", 'w') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Review Summary</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif; line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; color: #333; }}
                    pre {{ background-color: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }}
                    code {{ font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; }}
                    h1, h2, h3, h4 {{ margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; }}
                    h1 {{ padding-bottom: .3em; font-size: 2em; border-bottom: 1px solid #eaecef; }}
                    h2 {{ padding-bottom: .3em; font-size: 1.5em; border-bottom: 1px solid #eaecef; }}
                    h3 {{ font-size: 1.25em; }}
                    h4 {{ font-size: 1em; }}
                    blockquote {{ padding: 0 1em; color: #6a737d; border-left: 0.25em solid #dfe2e5; }}
                    table {{ border-collapse: collapse; margin: 20px 0; }}
                    table, th, td {{ border: 1px solid #ddd; }}
                    th, td {{ padding: 12px 15px; text-align: left; }}
                    tr:nth-child(even) {{ background-color: #f6f8fa; }}
                </style>
            </head>
            <body>
                {markdown.markdown(summary_report, extensions=['fenced_code', 'tables'])}
            </body>
            </html>
            """)
            
        print(f"Review completed. Results saved to {self.output_dir}")
        return {"repo_info": repo_info, "file_reviews": file_reviews}
        
    def _prioritize_files(self, repo_info: Dict[str, Any]) -> List[str]:
        """Prioritize files for review based on repository analysis.
        
        Args:
            repo_info: Repository information
            
        Returns:
            Prioritized list of file paths
        """
        # Basic prioritization - could be improved with more sophisticated analysis
        # Currently prioritizes:
        # 1. Python/JavaScript/TypeScript files
        # 2. More imports/dependencies first
        # 3. Shorter files before very long files
        
        file_scores = []
        for file_info in repo_info["files"]:
            path = file_info["path"]
            ext = os.path.splitext(path)[1].lower()
            
            # Base score - prioritize by extension
            if ext in ['.py', '.js', '.ts', '.jsx', '.tsx']:
                base_score = 100
            elif ext in ['.go', '.java', '.c', '.cpp', '.cs']:
                base_score = 90
            elif ext in ['.html', '.css', '.scss', '.sass']:
                base_score = 80
            elif ext in ['.md', '.txt', '.json', '.yml', '.yaml']:
                base_score = 70
            else:
                base_score = 50
                
            # Adjust by number of imports
            import_score = len(file_info.get("imports", [])) * 5
            
            # Adjust by line count (prefer medium-sized files)
            lines = file_info["lines"]
            if lines < 50:
                size_score = 10
            elif lines < 200:
                size_score = 20
            elif lines < 500:
                size_score = 15
            else:
                size_score = max(0, 30 - (lines // 500))  # Gradually reduce score for very large files
                
            # Calculate total score
            total_score = base_score + import_score + size_score
            file_scores.append((path, total_score))
            
        # Sort by score (descending) and return paths
        return [path for path, score in sorted(file_scores, key=lambda x: x[1], reverse=True)]
        
    async def _generate_repo_level_review(self, repo_info: Dict[str, Any]) -> str:
        """Generate repository-level review.
        
        Args:
            repo_info: Repository information
            
        Returns:
            Repository-level review text
        """
        # Get code review task config
        task_config = self.config.get("TASK_MODEL_MAPPING", {}).get("code_review", {})
        primary_config = task_config.get("primary", {})
        backup_config = task_config.get("backup", {})
        
        # Create a summary of the repository structure
        repo_summary = f"""
    Repository Overview:
    - Total files: {len(repo_info['files'])}
    - File types: {json.dumps(repo_info['file_counts'], indent=2)}
    - Total lines of code: {repo_info['total_lines']}
    - Dependencies: {repo_info['dependencies']}
    """

        if repo_info.get("git"):
            repo_summary += f"""
    Git Information:
    - Remote: {repo_info['git']['remote']}
    - Branch: {repo_info['git']['branch']}
    - Last commit: {repo_info['git']['last_commit']}
    """

        # Sample up to 10 files for the high-level review
        sample_files = []
        for file_info in sorted(repo_info['files'], key=lambda x: x["lines"], reverse=True)[:10]:
            path = file_info["path"]
            content = self.repo_loader.load_file_content(path)
            if content:
                sample_files.append({
                    "path": path,
                    "content": content[:2000] + "..." if len(content) > 2000 else content
                })
        
        # Create repository review prompt
        prompt = f"""
    You are conducting a high-level code review of an entire code repository. Please analyze the repository structure and sample files provided to give an overall assessment.

    {repo_summary}

    Sample files (first 2000 characters of up to 10 files):
    """

        for sample in sample_files:
            prompt += f"\n\n--- {sample['path']} ---\n{sample['content']}"
            
        prompt += """

    Please provide a comprehensive repository-level review including:

    1. **Repository Structure Assessment**: Evaluate the organization and structuring of the codebase.
    2. **Code Quality Overview**: General assessment of code quality based on the samples.
    3. **Architecture Insights**: Inferences about the architecture and design patterns used.
    4. **Potential Issues**: Major issues or red flags visible from the high-level review.
    5. **Improvement Recommendations**: Suggestions for improving the codebase.
    6. **Dependency Analysis**: Assessment of the dependencies and their management.
    7. **Review Plan**: Suggested approach for a more detailed review of this codebase.

    Format your review as a well-structured Markdown document with appropriate headings and sections.
    """

        # Print authentication information for debugging
        print(f"Using API key (first 5 chars): {self.adapter.api_key[:5]}...")
        print(f"Using models from config - primary: {primary_config.get('model')}, backup: {backup_config.get('model')}")
        
        # Generate repository review using the configured models
        messages = [
            {"role": "system", "content": primary_config.get("system_prompt", "You are a code reviewer focused on quality and correctness.")},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.adapter.generate_completion(
            messages=messages,
            task_config=task_config,
            timeout=300  # Longer timeout for repository-level review
        )
        
        return response["choices"][0]["message"]["content"]
        
    async def _review_file_batch(self, file_paths: List[str]) -> Dict[str, str]:
        """Review a batch of files.
        
        Args:
            file_paths: List of file paths to review
            
        Returns:
            Dictionary mapping file paths to review text
        """
        # Get code review task config
        task_config = self.config.get("TASK_MODEL_MAPPING", {}).get("code_review", {})
        backup_config = task_config.get("backup", {})
        
        # Use more reliable mistral model
        code_review_task_config = self.config.get("TASK_MODEL_MAPPING", {}).get("code_review", {})
        if code_review_task_config:
            review_task_config = {
                "primary": code_review_task_config.get("primary", {
                    "model": "google/gemini-2.5-pro-exp-03-25:free",  # Default if not in config
                    "temperature": 0.1,
                    "max_tokens": 1000000
                }),
                "backup": code_review_task_config.get("backup", backup_config)
            }
        else:
            # Fallback if no code review config found
            review_task_config = {
                "primary": {
                    "model": "deepseek/deepseek-chat-v3-0324:free",  # Default to a common free model
                    "temperature": 0.1,
                    "max_tokens": 128000
                },
                "backup": backup_config
            }
        
        # Prepare review prompts based on depth
        if self.review_depth == "basic":
            review_instructions = """
    Please review this code file and provide:
    1. **Overview**: Brief description of what the code does
    2. **Main Issues**: 3-5 most important issues or concerns
    3. **Quick Wins**: 2-3 easy improvements that could be made
    """
        elif self.review_depth == "standard":
            review_instructions = """
    Please provide a thorough code review including:
    1. **Code Quality**: Assess the overall quality, readability, and maintainability
    2. **Issues**: Identify bugs, anti-patterns, and code smells
    3. **Security Concerns**: Note any security vulnerabilities
    4. **Performance Considerations**: Highlight potential performance issues
    5. **Refactoring Opportunities**: Suggest improvements and refactorings
    6. **Best Practices**: Comment on adherence to best practices for the language/framework
    """
        else:  # deep
            review_instructions = """
    Please provide an extremely detailed code review including:
    1. **Functionality Analysis**: Detailed explanation of what the code does and how
    2. **Architecture Assessment**: Evaluate the design patterns and architecture
    3. **Code Quality**: In-depth analysis of readability, maintainability, and complexity
    4. **Issues**: Comprehensive list of bugs, anti-patterns, and code smells
    5. **Security Analysis**: Detailed security audit including potential vulnerabilities
    6. **Performance Optimization**: Thorough performance analysis with specific recommendations
    7. **Refactoring Plan**: Step-by-step refactoring suggestions with code examples
    8. **Testing Assessment**: Evaluation of test coverage and testing approach
    9. **Documentation Review**: Analysis of comments and documentation quality
    10. **Standards Compliance**: Evaluation against language/framework best practices
    """
        
        results = {}
        for file_path in file_paths:
            print(f"  Reviewing file: {file_path}")
            
            # Load file content
            content = self.repo_loader.load_file_content(file_path)
            if not content:
                results[file_path] = "Error: Could not load file content"
                continue
                
            # Create file review prompt
            prompt = f"""
    Please review the following code file:

    File path: {file_path}

    ```
    {content}
    ```

    {review_instructions}

    Format your review as Markdown with appropriate headings and code examples where relevant.
    """

            # Generate file review
            messages = [
                {"role": "system", "content": backup_config.get("system_prompt", "You are a code reviewer focused on quality and correctness.")},
                {"role": "user", "content": prompt}
            ]
            
            try:
                response = await self.adapter.generate_completion(
                    messages=messages,
                    task_config=code_review_task_config
                )
                
                review = response["choices"][0]["message"]["content"]
                results[file_path] = review
                
                # Save individual file review
                file_review_dir = self.output_dir / "file_reviews"
                file_review_dir.mkdir(exist_ok=True)
                
                # Create sanitized filename
                safe_filename = file_path.replace("/", "_").replace("\\", "_")
                
                with open(file_review_dir / f"{safe_filename}.md", 'w') as f:
                    f.write(f"# Code Review: {file_path}\n\n{review}")
                    
            except Exception as e:
                print(f"  Error reviewing file {file_path}: {str(e)}")
                results[file_path] = f"Error: {str(e)}"
                
        return results
        
    async def _generate_summary_report(self, repo_info: Dict[str, Any], file_reviews: Dict[str, str]) -> str:
        """Generate summary report of the repository review.
        
        Args:
            repo_info: Repository information
            file_reviews: Dictionary mapping file paths to review text
            
        Returns:
            Summary report text
        """
        # Get code review task config
        task_config = self.config.get("TASK_MODEL_MAPPING", {}).get("code_review", {})
        
        # Create a summary of the review process
        summary = f"""
# Repository Review Summary

## Overview
- Repository reviewed: {os.path.basename(self.repo_path)}
- Total files analyzed: {len(repo_info['files'])}
- Files reviewed: {len(file_reviews)}
- Review depth: {self.review_depth}
- Review date: {os.path.getmtime(self.output_dir)}

## File Type Distribution
```json
{json.dumps(repo_info['file_counts'], indent=2)}
```

## Review Highlights
        
"""

        # Create summary prompt
        prompt = f"""
You've conducted a code review of {len(file_reviews)} files in a repository. Based on the individual file reviews below, please synthesize an overall summary report.

Repository Info:
```json
{json.dumps(repo_info, indent=2)}
```

The file reviews have been conducted and I need you to create a synthesis of the key findings and recommendations. Focus on identifying patterns across files, major issues that appear in multiple places, and prioritized recommendations for the entire codebase.

Your summary should include:

1. **Key Findings**: Major issues found across multiple files
2. **Common Patterns**: Recurring problems or anti-patterns
3. **Strengths**: Aspects of the codebase that are well-designed
4. **Priority Issues**: What should be addressed first and why
5. **Improvement Roadmap**: Suggested steps to improve the codebase in order of priority
6. **Risk Assessment**: Evaluation of technical debt and security concerns

Format your summary as a comprehensive Markdown document with clear sections and subsections.
"""

        # Generate summary
        messages = [
            {"role": "system", "content": task_config.get("primary", {}).get("system_prompt", "You are a code reviewer focused on quality and correctness.")},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.adapter.generate_completion(
            messages=messages,
            task_config=task_config,
            timeout=300  # Longer timeout for summary
        )
        
        return summary + response["choices"][0]["message"]["content"]

async def main():
    parser = argparse.ArgumentParser(description="Repository Code Review using AI")
    parser.add_argument("--repo", required=True, help="Path to repository to review")
    parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    parser.add_argument("--output", default="./review_output", help="Directory to save review results")
    parser.add_argument("--depth", choices=["basic", "standard", "deep"], default="standard", 
                      help="Review depth (basic, standard, deep)")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of files to review in each batch")
    
    args = parser.parse_args()
    
    reviewer = RepoReviewer(
        config_path=args.config,
        repo_path=args.repo,
        output_dir=args.output,
        max_files_per_batch=args.batch_size,
        review_depth=args.depth
    )
    
    await reviewer.review_repository()

if __name__ == "__main__":
    asyncio.run(main())
