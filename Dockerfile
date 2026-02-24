# --- Stage 1: Dependency Resolver (Build Stage) ---
FROM python:3.11-slim-bookworm AS resolver

WORKDIR /app

# Install curl, uv, and ensure PATH is set
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"

# Copy project metadata
COPY pyproject.toml .

# COMPILE: Resolve dependencies and pin them to a requirements.txt file.
RUN uv pip compile pyproject.toml \
    --group dev \
    --output-file requirements.txt 

# --- Stage 2: Minimal Runtime ---
# This stage is clean and small.
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Copy the compiled requirements file from the resolver stage
COPY --from=resolver /app/requirements.txt .

# 1. THE FIX: Use the standard 'pip' command (which is present in the base image)
#    to install the dependencies listed in requirements.txt.
#    We don't need the '--system' flag with pip as we are not using uv.
RUN pip install --no-cache-dir --requirement requirements.txt

# Copy the source code (src/ directory) and configuration files
COPY src/ src/

# Set best practice environment variables
ENV PYTHONUNBUFFERED=1
ENV GITHUB_TOKEN=""

# Expose the application port
EXPOSE 8080

# Command to run the application using uvicorn.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
