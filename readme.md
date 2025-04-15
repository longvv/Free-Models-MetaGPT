# Enhanced Free Models MetaGPT

A robust implementation that uses MetaGPT with multiple free models from OpenRouter, optimizing each stage of the development workflow with specialized models while adding fault tolerance, validation, and intelligent memory management.

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
| **Requirements Analysis** | deepseek-r1-distill-llama-70b | Gemma 3 27B | The large 70B model offers significantly better understanding of complex requirements |
| **System Design** | Gemma 3 27B | deepseek-r1-distill-llama-70b | Gemma is efficient for architectural decisions, with the larger model as powerful backup |
| **Implementation Planning** | deepseek-r1-distill-llama-70b | Gemma 3 27B | Large model for planning with Gemma's capabilities as backup |
| **Code Generation** | olympiccoder-32b | Gemma 3 27B | OlympicCoder specialized for code generation with Gemma as reliable backup |
| **Code Review** | olympiccoder-32b | Gemma 3 27B | Using a code-specific model for review improves feedback quality |

## Features

- **Free Models Only**: Uses only models with free access tiers on OpenRouter
- **Fault Tolerance**: Automatic failover to backup models when primary models are unavailable
- **Enhanced Context Management**: Smart chunking and retrieval for efficient use of context windows
- **Validation System**: Validates outputs for syntax, structure, and consistency
- **Async Processing**: Processes independent tasks in parallel when possible
- **Smart Caching**: Reduces API calls through intelligent result caching
- **Custom Prompting**: Optimized prompts for each development stage
- **MetaGPT Integration**: Works seamlessly with the MetaGPT framework
- **Repository Code Review**: Advanced code review capabilities for entire repositories

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
   
   Alternatively, you can add your API key directly to the `config.yml` file.

4. Install optional dependencies for enhanced features:
   ```bash
   # For vector-based memory system (highly recommended)
   pip install sentence-transformers
   ```

5. Verify your API key and available models:
   ```bash
   python check_api_key.py
   python test_openrouter_models.py
   ```

## Usage

### Software Development Workflow

The main script for software development is `run_free_models_metagpt.py`. It supports various commands and options:

#### List Available Free Models

```bash
python run_free_models_metagpt.py list-models
```

This command shows all available free models from OpenRouter that you can use with your API key.

#### Update Configuration

```bash
python run_free_models_metagpt.py update-config
```

Updates your `config.yml` with the latest available free models, ensuring your configuration stays current.

#### Run a Project (Standard Sequential Mode)

```bash
python run_free_models_metagpt.py run --idea "Create a simple blog website with user authentication and post creation functionality"
```

This executes tasks in sequence, which is more reliable but slower.

#### Run a Project (Parallel Mode for Faster Processing)

```bash
python run_free_models_metagpt.py run --idea "Create a simple blog website with user authentication" --parallel
```

Executes independent tasks in parallel for faster results, but may occasionally lead to less coherence between stages.

#### Additional Options

```bash
python run_free_models_metagpt.py run --help
```

Shows all available options for running projects.

### Repository Code Review

The system also includes advanced repository code review capabilities:

```bash
python run_repo_review.py --repo /path/to/repository --depth standard
```

Options for the repository review:

- `--repo`: Path to the repository to review (required)
- `--config`: Path to configuration file (default: "config.yml")
- `--output`: Directory to save review results (default: "./review_output")
- `--depth`: Review depth, choices are "basic", "standard", or "deep" (default: "standard")
- `--batch-size`: Number of files to review in each batch (default: 5)
- `--ignore`: Specify additional patterns to ignore (can be used multiple times)

The repo review generates comprehensive HTML reports including:
- Repository-level overview
- Individual file reviews
- Summary report with key findings and recommendations

Note: The repository review automatically respects `.gitignore` files and skips common non-code directories like `node_modules`, `.git`, `__pycache__`, etc. You can specify additional patterns to ignore using the `--ignore` option.

## Configuration

The `config.yml` file allows for extensive customization:

### Task-Model Mapping

Configure which models to use for each development stage:

```yaml
TASK_MODEL_MAPPING:
  requirements_analysis:
    primary:
      model: "deepseek/deepseek-chat-v3-0324:free"
      temperature: 0.1
      max_tokens: 128000
      context_window: 128000
      system_prompt: "You are a skilled product manager analyzing project requirements..."
    backup:
      model: "deepseek/deepseek-chat-v3-0324:free"
      temperature: 0.1
      max_tokens: 128000
      context_window: 128000
      system_prompt: "You are a skilled product manager..."
    validation:
      schema: "requirements_schema.json"
      required_sections: ["Functional Requirements", "Non-Functional Requirements", "Constraints"]
```

### Memory System

Configure how context is managed between models:

```yaml
MEMORY_SYSTEM:
  chunk_size: 1000  # Approx token size per chunk
  overlap: 100      # Overlap between chunks 
  vector_db:
    embedding_model: "all-MiniLM-L6-v2"  # Local embedding model
    similarity_threshold: 0.75
  cache:
    enabled: true
    ttl_seconds: 3600  # Cache lifetime
  context_strategy: "smart_selection"  # Options: full, summary, smart_selection
```

### Rate Limiting

Control API request frequency to avoid hitting limits:

```yaml
RATE_LIMITING:
  requests_per_minute: 10
  max_parallel_requests: 2
  backoff_strategy: "exponential"
  initial_backoff_seconds: 1
  max_backoff_seconds: 60
```

### Workflow Stages

Define the sequence of tasks in your development workflow:

```yaml
WORKFLOW_STAGES:
  - task: "requirements_analysis"
    input: "user_idea"
    output: "requirements_doc"
    
  - task: "system_design"
    input: "requirements_doc"
    output: "design_doc"
```

### Validators

Configure validation criteria for each stage:

```yaml
VALIDATORS:
  syntax:
    enabled: true
    retry_on_failure: true
    max_retries: 3
  
  consistency:
    enabled: true
    retry_on_failure: true
    consistency_threshold: 0.8
    
  schema:
    enabled: true
    retry_on_failure: true
    schema_dir: "./schemas/"
```

## How It Works

### Key Components

1. **Enhanced Task Orchestrator**: Manages workflow with validation and parallel processing
   - Source: `enhanced_task_orchestrator.py`
   - Handles task execution, validation, and manages the flow of information between stages

2. **Enhanced OpenRouter Adapter**: Handles model selection, rate limiting, and circuit breaking
   - Source: `enhanced_openrouter_adapter.py`
   - Manages API calls, rotates models when needed, and implements fallback strategies

3. **Enhanced Memory System**: Intelligently manages context between stages
   - Source: `enhanced_memory.py`
   - Uses vector embeddings (when available) or keyword-based retrieval to maintain context

4. **Validation System**: Ensures quality at each step of the process
   - Source: `validators.py`
   - Validates syntax, schema compliance, and consistency between stages

### Advanced Features

- **Smart Chunking**: Breaks documents into overlapping chunks to fit within model context windows
- **Vector-Based Retrieval**: Uses embeddings to find the most relevant context for each query
- **Circuit Breaker Pattern**: Prevents hammering failing API endpoints
- **Exponential Backoff**: Intelligently handles rate limits
- **Schema Validation**: Validates outputs against JSON schemas

## Directory Structure

```
.
├── config.yml                     # Configuration file
├── check_api_key.py               # API key verification tool
├── enhanced_memory.py             # Memory system
├── enhanced_openrouter_adapter.py # OpenRouter integration
├── enhanced_task_orchestrator.py  # Task orchestration
├── metagpt_integration.py         # MetaGPT integration
├── readme.md                      # Documentation
├── repo_code_review.py            # Repository code review
├── repository_loader.py           # Repository analysis
├── requirements.txt               # Dependencies
├── run_free_models_metagpt.py     # Main script for software development
├── run_repo_review.py             # Main script for repository reviews
├── test_openrouter_api.py         # API testing tool
├── test_openrouter_models.py      # Model testing tool
├── validators.py                  # Validation system
└── workspace/                     # Output directory (created on first run)
```

## Troubleshooting

### API Key Issues

If you encounter authentication errors:

1. Verify your API key with `python check_api_key.py`
2. Ensure the key is correctly set in `config.yml` or as an environment variable
3. Check if you have access to the models by running `python test_openrouter_models.py`

### Model Availability

Free model availability can change. If certain models aren't working:

1. Run `python test_openrouter_models.py` to see which models are currently available
2. Update your configuration with `python run_free_models_metagpt.py update-config`

### Rate Limiting

If you hit rate limits:

1. Reduce the `requests_per_minute` setting in `config.yml`
2. Increase `initial_backoff_seconds` and `max_backoff_seconds` for more gradual retries

## Advanced Usage

### Working with Large Repositories

For very large repositories, use batch processing and consider ignoring non-essential files:

```bash
python run_repo_review.py --repo /path/to/large/repo --batch-size 3 --depth basic --ignore "**/*.min.js" --ignore "**/dist/**"
```

This processes fewer files at once, uses a simpler review depth, and skips minified JavaScript files and distribution directories. The repository loader already honors `.gitignore` files and has built-in patterns for common directories to skip (like `node_modules` and `__pycache__`).

### Customizing Prompts

You can customize the system prompts for each model in `config.yml`:

```yaml
system_prompt: "You are a software architect designing systems. Based on the requirements, create a high-level architecture with components, interfaces, and data flows. Be concise and focus on the most important design decisions."
```

### MetaGPT Integration

Export your project to MetaGPT format for compatibility with MetaGPT tools:

```python
from metagpt_integration import MetaGPTIntegration

integration = MetaGPTIntegration("./workspace")
metagpt_dir = integration.export_to_metagpt("./metagpt_export")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.