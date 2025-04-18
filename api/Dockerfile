FROM --platform=linux/arm64 python:3.10-slim

WORKDIR /app

# Install dependencies
COPY api/requirements.txt api-requirements.txt
COPY requirements.txt metagpt-requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential curl git && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r api-requirements.txt && \
    pip install --no-cache-dir -r metagpt-requirements.txt && \
    apt-get purge -y --auto-remove gcc build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app

# Create required directories
RUN mkdir -p /app/workspace /app/workflows

# Create workflow file if it doesn't exist
RUN mkdir -p /app/workflows && echo '\
# Example collaborative workflow for MetaGPT\n\
name: collaborative_workflow\n\
tasks:\n\
  - name: requirements_analysis\n\
    type: collaborative\n\
    model: deepseek/deepseek-chat-v3-0324:free\n\
    participants: [requirements_analysis, domain_expert, user_advocate]\n\
  - name: system_design\n\
    type: collaborative\n\
    model: deepseek/deepseek-chat-v3-0324:free\n\
    participants: [architect, developer, security_expert]\n\
  - name: implementation_planning\n\
    type: collaborative\n\
    model: deepseek/deepseek-chat-v3-0324:free\n\
    participants: [project_manager, developer, qa_engineer]\n\
' > /app/workflows/collaborative_workflow.yml

# Expose API port
EXPOSE 8000

# Command to run the application
WORKDIR /app/api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
