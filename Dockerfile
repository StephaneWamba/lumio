# Django application Dockerfile - Optimized with uv
FROM python:3.12-slim AS builder

# Install uv (Rust-based package manager - 10-100x faster than pip)
RUN pip install uv

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files and source code
COPY pyproject.toml uv.lock* ./
COPY apps ./apps
COPY config ./config
COPY manage.py ./

# Install dependencies with uv
# --system avoids virtualenv overhead (Docker is already isolated)
RUN uv pip install --system -e . --no-cache

# Runtime stage - minimal image
FROM python:3.12-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Create app user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Collect static files without migrations
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Run Gunicorn with optimized settings
CMD ["gunicorn", \
     "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--worker-connections", "1000", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
