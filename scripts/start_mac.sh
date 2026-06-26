#!/usr/bin/env bash
set -e

CONTAINER_NAME="finally-app"
IMAGE_NAME="finally"
DB_VOLUME="finally-data"

# Parse flags
BUILD=false
for arg in "$@"; do
  [[ "$arg" == "--build" ]] && BUILD=true
done

# Check .env exists
if [[ ! -f .env ]]; then
  echo "Error: .env file not found. Copy .env.example to .env and fill in your API key."
  exit 1
fi

# Remove existing container (running or stopped) — always attempt, ignore errors
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Build image if needed
if $BUILD || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
  echo "Building Docker image..."
  docker build -t "$IMAGE_NAME" .
fi

# Run container
echo "Starting FinAlly..."
docker run -d \
  --name "$CONTAINER_NAME" \
  -p 8000:8000 \
  -v "${DB_VOLUME}:/app/db" \
  --env-file .env \
  "$IMAGE_NAME"

echo ""
echo "FinAlly is running at http://localhost:8000"
echo "Run './scripts/stop_mac.sh' to stop."
