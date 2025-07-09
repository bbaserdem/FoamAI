# FastAPI API Service Docker Container
# Based on Ubuntu 22.04 LTS for stability and consistency with other services
FROM ubuntu:22.04

# Avoid timezone prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/home/apiuser/.local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python and essential build tools
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    # Networking and utilities
    curl \
    wget \
    git \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create API user (non-root for security)
RUN groupadd -r apiuser && useradd -r -g apiuser -m -d /home/apiuser apiuser

# Install UV (modern Python package manager)
RUN pip3 install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy project files
COPY ../../pyproject.toml ./
COPY ../../src/ ./src/

# Install Python dependencies using UV
RUN uv sync --no-dev || uv pip install --system fastapi uvicorn[standard]

# Create necessary directories and set permissions
RUN mkdir -p /data \
    && chown -R apiuser:apiuser /app \
    && chown -R apiuser:apiuser /data

# Switch to apiuser (non-root)
USER apiuser

# Create a basic FastAPI application starter
RUN mkdir -p /app/src/foamai/api \
    && echo '#!/usr/bin/env python3' > /app/src/foamai/api/__init__.py \
    && echo 'from fastapi import FastAPI' > /app/src/foamai/api/main.py \
    && echo 'from fastapi.responses import JSONResponse' >> /app/src/foamai/api/main.py \
    && echo '' >> /app/src/foamai/api/main.py \
    && echo 'app = FastAPI(title="FoamAI API", version="0.1.0")' >> /app/src/foamai/api/main.py \
    && echo '' >> /app/src/foamai/api/main.py \
    && echo '@app.get("/ping")' >> /app/src/foamai/api/main.py \
    && echo 'async def ping():' >> /app/src/foamai/api/main.py \
    && echo '    """Health check endpoint."""' >> /app/src/foamai/api/main.py \
    && echo '    return JSONResponse(content="pong")' >> /app/src/foamai/api/main.py \
    && echo '' >> /app/src/foamai/api/main.py \
    && echo '@app.get("/")' >> /app/src/foamai/api/main.py \
    && echo 'async def root():' >> /app/src/foamai/api/main.py \
    && echo '    """Root endpoint."""' >> /app/src/foamai/api/main.py \
    && echo '    return JSONResponse(content={"message": "FoamAI API is running!"})' >> /app/src/foamai/api/main.py

# Expose FastAPI port
EXPOSE 8000

# Health check to ensure API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ping || exit 1

# Command to run the FastAPI application
CMD ["uvicorn", "src.foamai.api.main:app", "--host", "0.0.0.0", "--port", "8000"] 