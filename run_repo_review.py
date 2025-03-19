#!/usr/bin/env python
# run_repo_review.py
# Main script to run repository code review

import argparse
import asyncio
import os
from pathlib import Path

from repo_code_review import RepoReviewer

async def main():
    parser = argparse.ArgumentParser(description="Review a code repository with AI assistance")
    
    # Required arguments
    parser.add_argument("--repo", required=True, help="Path to the repository to review")
    
    # Optional arguments
    parser.add_argument("--config", default="config.yml", help="Path to configuration file")
    parser.add_argument("--output", default="./review_output", help="Directory to save review results")
    parser.add_argument("--depth", choices=["basic", "standard", "deep"], default="standard", 
                      help="Review depth (basic, standard, deep)")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of files to review in each batch")
    parser.add_argument("--ignore", action="append", default=None, 
                      help="Patterns to ignore (can be specified multiple times)")
    
    args = parser.parse_args()
    
    print(f"Starting repository review for: {args.repo}")
    print(f"Configuration: {args.config}")
    print(f"Output directory: {args.output}")
    print(f"Review depth: {args.depth}")
    
    reviewer = RepoReviewer(
        config_path=args.config,
        repo_path=args.repo,
        output_dir=args.output,
        max_files_per_batch=args.batch_size,
        review_depth=args.depth
    )
    
    try:
        await reviewer.review_repository()
        
        # Print results location
        abs_output = os.path.abspath(args.output)
        print(f"\nReview completed successfully!")
        print(f"Results saved to: {abs_output}")
        print(f"Main reports:")
        print(f"- Repository overview: {os.path.join(abs_output, 'repository_review.html')}")
        print(f"- Summary report: {os.path.join(abs_output, 'review_summary.html')}")
        print(f"- Individual file reviews: {os.path.join(abs_output, 'file_reviews/')}")
        
    except Exception as e:
        print(f"Error during review: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
