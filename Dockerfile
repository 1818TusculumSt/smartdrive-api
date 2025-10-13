# SmartDrive API - MCPO-based REST API Server
# Crawlerless deployment - connects to existing Pinecone + Azure Blob indexes

FROM python:3.11-slim

# Metadata
LABEL maintainer="SmartDrive API"
LABEL description="MCPO-based REST API for SmartDrive semantic search"

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies (API-only, no crawler deps)
RUN pip install --no-cache-dir -r requirements.txt

# Copy only API-related application code
COPY smartdrive_server.py .
COPY embeddings.py .
COPY config.py .
COPY document_storage.py .

# Expose MCPO API port
EXPOSE 8000

# Note: Health check disabled - MCPO may not expose /health by default
# If you need health checks, use docker-compose healthcheck with /docs or /openapi.json

# Run MCPO proxy with SmartDrive MCP server (NO AUTHENTICATION)
CMD ["sh", "-c", "mcpo --port 8000 --host 0.0.0.0 -- python smartdrive_server.py"]
