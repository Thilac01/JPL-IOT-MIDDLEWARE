FROM python:3.11-slim-bookworm

WORKDIR /app

# Force IPv4 for apt and install runtime tools
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4 && \
    apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    iproute2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user & group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create logs and data directory with correct permissions
RUN mkdir -p /app/logs /app/data && chown -R appuser:appgroup /app

# Copy application source code
COPY --chown=appuser:appgroup . /app

# Switch to unprivileged user
USER appuser

# Expose HTTP port
EXPOSE 8000

# Docker Healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Default execution using Uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
