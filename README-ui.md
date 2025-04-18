# MetaGPT Chat Visualization

This lightweight visualization creates a visual team chat interface for MetaGPT. The system allows you to see the different AI agents in MetaGPT interacting with each other in a familiar chat UI, making it easier to follow the conversation flow between different roles.

## Architecture

The system consists of the following components:

1. **Web UI**: A lightweight web interface that displays the conversation
2. **FastAPI Server**: Handles both serving the UI and integrating with MetaGPT
3. **MetaGPT**: The underlying multi-agent framework

The visualizer is designed to be simple and compatible with all architectures, including Apple Silicon (M1/M2).

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- MetaGPT installed (`pip install metagpt`)

### Running the Visualization

1. Start the visualization server with the unified runner:

```bash
python run_all.py
```

2. Your browser will automatically open to http://localhost:8088

3. Optional parameters:
   - `--port 8088`: Change the port (default: 8088)
   - `--no-browser`: Don't automatically open browser

## Using the Visualization

### Loading Existing Output

There are three ways to visualize MetaGPT conversations:

1. **Load Sample**: Click the "Load Sample" button to see a demo conversation

2. **Upload JSON**: Use the "Load from Output JSON" button to upload an existing `output.json` file

3. **Run MetaGPT**: Use the interface to run MetaGPT directly:
   - Click "Run MetaGPT" to run with a default prompt
   - Enter a custom prompt in the text field and click "Submit"

### API Endpoints

The visualization server provides several endpoints:

- `GET /output.json`: Get the current MetaGPT output
- `POST /api/run_metagpt`: Run MetaGPT with a custom prompt
- `POST /api/run_metagpt_default`: Run MetaGPT with a default prompt
- `GET /health`: Health check endpoint

## Customizing the Visualization

### Modifying Role Colors and Icons

You can customize the appearance of each role by editing the `ROLES` object in `visualization/index.html`.

### Adding New Roles

If you add new roles to MetaGPT, make sure to update the role mappings in:
1. `visualization/index.html` - Add to the `ROLES` object
2. Update the `OUTPUT_TO_ROLE_MAP` object to map MetaGPT output keys to roles

## Troubleshooting

- **Server won't start**: Ensure you have all dependencies installed with `pip install fastapi uvicorn jinja2`
- **MetaGPT not running**: Verify MetaGPT is installed with `pip install metagpt`
- **UI not showing messages**: Check the browser console for any JavaScript errors
- **Empty output.json**: Ensure your MetaGPT run completed successfully

## Additional Features

### Command Line Options

The unified runner (`run_all.py`) provides several command-line options:

```bash
python run_all.py --help
```

Available options:
- `--port PORT`: Set the server port (default: 8088)
- `--no-browser`: Don't automatically open the browser

### Environment Integration

The visualization server integrates with your local MetaGPT installation, allowing you to:

1. Run MetaGPT directly from the UI
2. View results immediately in the team chat visualization
3. Experiment with different prompts without leaving the browser
