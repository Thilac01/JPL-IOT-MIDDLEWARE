#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

APP_NAME="jpl-iot-middleware"
IMAGE_NAME="jpl-iot-middleware:latest"
HOST_PORT="${APP_PORT:-8001}"
CONTAINER_PORT=8000

echo "=========================================="
echo " Starting Production Deployment: ${APP_NAME}"
echo "=========================================="

# 1. Environment Setup & Auto-Creation
if [ ! -f .env ]; then
    echo "[!] .env file not found."
    if [ -f .env.example ]; then
        echo "[+] Copying .env.example to .env..."
        cp .env.example .env
    else
        echo "[+] Creating fresh .env file..."
        touch .env
    fi
fi

# Ensure essential default values exist in .env if not set
echo "[1/5] Configuring environment variables..."

# Function to set key-value in .env if missing or empty
set_default_env() {
    local key="$1"
    local default_val="$2"
    if ! grep -q "^${key}=" .env || [ -z "$(grep "^${key}=" .env | cut -d'=' -f2)" ]; then
        echo "${key}=${default_val}" >> .env
        echo "    Added default: ${key}=${default_val}"
    fi
}

set_default_env "APP_NAME" "JPL Security & IoT Middleware"
set_default_env "ENVIRONMENT" "production"
set_default_env "LOG_LEVEL" "INFO"
set_default_env "APP_PORT" "8001"
set_default_env "DEBUG" "false"
set_default_env "LOG_ROTATION_BYTES" "10485760"

# Generate strong random keys for SECRET_KEY and API_KEY if blank/missing
if ! grep -q "^SECRET_KEY=" .env || [ -z "$(grep "^SECRET_KEY=" .env | cut -d'=' -f2)" ]; then
    RANDOM_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')
    echo "SECRET_KEY=${RANDOM_SECRET}" >> .env
    echo "    Generated new SECRET_KEY"
fi

if ! grep -q "^API_KEY=" .env || [ -z "$(grep "^API_KEY=" .env | cut -d'=' -f2)" ]; then
    RANDOM_API_KEY=$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')
    echo "API_KEY=${RANDOM_API_KEY}" >> .env
    echo "    Generated new API_KEY"
fi

# 2. Sanitize .env file
echo "[2/5] Sanitizing .env (stripping comments & trailing spaces)..."
sed -i 's/[[:space:]]*#.*//' .env
sed -i 's/[[:space:]]*$//' .env
sed -i '/^[[:space:]]*$/d' .env  # Remove blank lines

# 3. Build Docker Image
echo "[3/5] Building Docker image '${IMAGE_NAME}'..."
docker build -t "${IMAGE_NAME}" .

# 4. Cleanup Stale Containers
echo "[4/5] Cleaning up existing instances..."
if docker ps -a --format '{{.Names}}' | grep -q "^${APP_NAME}$"; then
    echo "    Stopping and removing old container '${APP_NAME}'..."
    docker rm -f "${APP_NAME}"
fi

# 5. Run Container
echo "[5/5] Launching container on host port ${HOST_PORT}..."
docker run -d \
  --name "${APP_NAME}" \
  --restart unless-stopped \
  --env-file .env \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  "${IMAGE_NAME}"

# 6. Verify Deployment Health
echo "=========================================="
echo "Verifying server startup..."
sleep 4

if [ "$(docker inspect -f '{{.State.Running}}' "${APP_NAME}")" = "true" ]; then
    echo "=========================================="
    echo " SUCCESS: ${APP_NAME} is live!"
    echo " Base URL: http://localhost:${HOST_PORT}"
    echo " Health Check: http://localhost:${HOST_PORT}/healthz"
    echo "=========================================="
else
    echo "ERROR: Container failed to start. Logs:"
    docker logs "${APP_NAME}"
    exit 1
fi