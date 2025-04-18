# Use an official Python runtime as a parent image
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY visualization/requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the visualization server code
COPY visualization/ /app/

# Expose the port the server runs on
EXPOSE 8088

# Run the visualization server
CMD ["python", "/app/server.py"]
