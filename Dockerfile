# syntax=docker/dockerfile:1
FROM python:3.14-slim

# Install build essentials for C extensions
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Install uv (modern Python package manager)
RUN pip install --no-cache-dir uv

# Set work directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY main.py .
COPY src ./src

# Install dependencies (including the project itself)
RUN uv sync --frozen

# Expose port for FastAPI
EXPOSE 8000

# Entrypoint
CMD ["uv", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
