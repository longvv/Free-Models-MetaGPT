# Enhanced Free Models MetaGPT

A robust implementation to use MetaGPT with multiple free models from OpenRouter, optimizing each stage of the development workflow with specialized models while adding fault tolerance, validation, and intelligent memory management.

## Overview

This project extends MetaGPT to work with free AI models available through OpenRouter. It employs several advanced techniques to maximize the effectiveness of these models:

1. **Smart Dispatcher**: Efficiently routes tasks to the most appropriate models with automatic failover
2. **Enhanced Memory System**: Uses chunking and vector retrieval to maximize context window usage
3. **Validation System**: Ensures outputs meet quality standards before proceeding to the next stage
4. **Rate Limiting & Circuit Breaking**: Prevents API rate limit issues and handles failures gracefully
5. **Task-Specific Model Optimization**: Uses specialized models for each development stage

## Model Role Specialization

| Role | Primary Model | Backup Model | Rationale |
|------|---------------|--------------|-----------|
| **Requirements Analysis** | Llama 3 8B | Mistral 7B | Llama 3 8B has better instruction-following for structured requirements |
| **System Design** | Mistral 7B | Llama 3 8B | Mistral tends to be more concise for architectural decisions |
| **Implementation Planning** | Llama 3 8B | Phi-2 | Llama 3 has better planning capabilities for complex tasks |
| **Code Generation** | CodeLlama 7B | WizardCoder | CodeLlama is specifically trained for coding tasks |
| **Code Review** | CodeLlama 7B | Mistral 7B | Using a code-specific model for review improves feedback quality |

## Features

- **Free Models Only**: Uses only models with free access tiers on OpenRouter
- **Fault Tolerance**: Automatic failover to backup models when primary models are unavailable
- **Enhanced Context Management**: Smart chunking and retrieval for efficient use of context windows
- **Validation System**: Validates outputs for syntax, structure, and consistency
- **Async Processing**: Processes independent tasks in parallel when possible
- **Smart Caching**: Reduces API calls through intelligent result caching
- **Custom Prompting**: Optimized prompts for each development stage
- **MetaGPT Integration**: Works seamlessly with the MetaGPT framework

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/enhanced-free-models-metagpt.git
   cd enhanced-free-models-metagpt
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your OpenRouter API key:
   ```bash
   export OPENROUTER_API_KEY=your_api_key_here
   ```

4. Install optional dependencies for enhanced features:
   ```bash
   # For vector-based memory system
   pip install sentence-transformers
   ```

5. Update the configuration file with available free models:
   ```bash
   python run_free_models_metagpt.py update-config
   ```

## Usage

### List Available Free Models

```bash
python run_free_models_metagpt.py list-models
```

### Run a Project (Standard Sequential Mode)

```bash
python run_free_models_metagpt.py run --idea "Create a simple blog website with user authentication and post creation functionality"
```

### Run a Project (Parallel Mode for Faster Processing)

```bash
python run_free_models_metagpt.py run --idea "Create a simple blog website with user authentication" --parallel
```

### Additional Options

```bash
python run_free_models_metagpt.py run --help
```

## Configuration

The enhanced `config.yml` allows for extensive customization:

- **Task Model Mapping**: Primary and backup models for each task
- **Memory System**: Chunking strategy and vector retrieval settings
- **Rate Limiting**: Controls for API request frequency
- **Validation System**: Syntax, schema, and consistency validation
- **Workflow Stages**: Customizable workflow stages

## How It Works

### Key Components

1. **Enhanced Task Orchestrator**: Manages workflow with validation and parallel processing
2. **Enhanced OpenRouter Adapter**: Handles model selection, rate limiting, and circuit breaking
3. **Enhanced Memory System**: Intelligently manages context between stages
4. **Validation System**: Ensures quality at each step of the process

### Advanced Features

- **Smart Chunking**: Breaks documents into overlapping chunks to fit within model context windows
- **Vector-Based Retrieval**: Uses embeddings to find the most relevant context for each query
- **Circuit Breaker Pattern**: Prevents hammering failing API endpoints
- **Exponential Backoff**: Intelligently handles rate limits
- **Schema Validation**: Validates outputs against JSON schemas

## Directory Structure

```
.
├── config.yml                     # Enhanced configuration file
├── enhanced_openrouter_adapter.py # Enhanced OpenRouter integration
├── enhanced_memory.py             # Vector-based memory system
├── enhanced_task_orchestrator.py  # Advanced task orchestration
├── validators.py                  # Output validation system
├── metagpt_integration.py         # Integration with MetaGPT
├── run_free_models_metagpt.py     # Main script
├── schemas/                       # Validation schemas
└── workspace/                     # Output directory
    ├── requirements_doc.txt
    ├── design_doc.txt
    ├── implementation_plan.txt
    ├── source_code.txt
    ├── review_comments.txt
    └── project_summary.md
```

## Advantages Over The Original Implementation

1. **Fault Tolerance**: Gracefully handles API failures and rate limits
2. **Efficient Context Management**: Makes better use of limited context windows
3. **Validation**: Ensures higher quality outputs at each stage
4. **Parallel Processing**: Faster execution for independent tasks
5. **Smart Caching**: Reduces redundant API calls

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
