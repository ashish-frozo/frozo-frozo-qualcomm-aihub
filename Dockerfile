# Stage 1: Build
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install hatch for building the package
RUN pip install --no-cache-dir hatch

# Copy project files
COPY pyproject.toml README.md ./
COPY edgegate ./edgegate

# Build the wheel
RUN hatch build -t wheel

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy the wheel from builder
COPY --from=builder /app/dist/*.whl .

# Install the package and its dependencies
RUN pip install --no-cache-dir *.whl

# Copy alembic for migrations
COPY alembic ./alembic
COPY alembic.ini .
COPY prestart.sh .
RUN chmod +x prestart.sh

# Create data directory for local storage (if used)
RUN mkdir -p data/artifacts data/signing_keys

# Expose API port
EXPOSE 8000

# Use prestart script to run migrations
ENTRYPOINT ["./prestart.sh"]

# Default command (can be overridden for worker)
# Use PORT env var for Railway compatibility, default to 8000
CMD uvicorn edgegate.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
