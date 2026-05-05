# Multi-stage Dockerfile for Slate Backend
# Optimized for production deployment with UV

# Stage 1: Base Python image with dependencies
FROM python:3.11-slim as backend-base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV - much faster than pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt requirements-api.txt ./
# Use pip with legacy resolver to handle complex dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt

# Stage 2: Backend application
FROM backend-base as backend

# Copy application code
COPY open_notebook/ /app/open_notebook/
COPY api/ /app/api/
COPY pyproject.toml README.md ./

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# Create data directory
RUN mkdir -p /app/data/uploads

# Expose port
EXPOSE 5055

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5055/api/health || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DATABASE_TYPE=sqlite \
    SQLITE_DB_PATH=/app/data/database.db \
    API_HOST=0.0.0.0 \
    API_PORT=5055

# Run migrations, seed default admin user, and start server
CMD python -m open_notebook.database.async_migrate migrate && \
    python -m open_notebook.database.seeds.default_roles && \
    uvicorn api.main:app --host 0.0.0.0 --port 5055
