# FastAPI API Service Docker Container
# Using Python 3.12 base image for consistency
FROM python:3.12-slim

# Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src/foamai-server

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Basic utilities
    curl \
    wget \
    git \
    # Required for building Python packages
    gcc \
    g++ \
    build-essential \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create API user (non-root for security)
RUN groupadd -r apiuser && useradd -r -g apiuser -m -d /home/apiuser apiuser

# Install UV package manager system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy the foamai-server directory from the build context
# The build context is set to "." (root of the repo) in the workflow
COPY src/foamai-server/ ./src/foamai-server/

# Create virtual environment and install dependencies
WORKDIR /app/src/foamai-server

# Step 1: Create virtual environment with Python 3.12
RUN python -m venv .venv

# Step 2: Upgrade pip in the virtual environment
RUN .venv/bin/python -m pip install --upgrade pip setuptools wheel

# Step 3: Install dependencies using uv that's already installed globally
RUN /root/.local/bin/uv pip install --python .venv/bin/python -e .

# Create necessary directories and set permissions
RUN mkdir -p /data /tmp/foamai

# Give ownership to apiuser
RUN chown -R apiuser:apiuser /app \
    && chown -R apiuser:apiuser /data \
    && chown -R apiuser:apiuser /tmp/foamai

# Switch to apiuser (non-root)
USER apiuser

# Update PATH for the apiuser to include the virtual environment
ENV PATH="/app/src/foamai-server/.venv/bin:$PATH"

# Expose FastAPI port
EXPOSE 8000

# Health check to ensure API is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Command to run the FastAPI application with the correct module path
CMD ["uvicorn", "foamai_server.main:app", "--host", "0.0.0.0", "--port", "8000"] 