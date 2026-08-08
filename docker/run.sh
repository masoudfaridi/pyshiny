#!/usr/bin/env bash
# One-command dockerize-and-run, no docker-compose required.
#
# Usage (from anywhere -- the script finds the project root itself):
#   bash docker/run.sh            # runs on port 8000
#   bash docker/run.sh 9000       # runs on port 9000
#   ./docker/run.sh 9000          # same, if it's executable
#
# Builds the image, then runs it detached with the SQLite database
# persisted in ./db on the host (so accounts survive restarts/rebuilds).
# Re-running this script rebuilds and replaces the previous container.
set -euo pipefail

PORT="${1:-8000}"
IMAGE_NAME="adminlte-shiny-dashboard"
CONTAINER_NAME="adminlte-shiny-dashboard"

# Resolve the project root (parent of this script's directory) regardless
# of where the script is called from, so `docker build` gets the right
# context no matter the current working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

mkdir -p "${PROJECT_ROOT}/db"

echo "==> Building image '${IMAGE_NAME}' ..."
docker build -f "${SCRIPT_DIR}/Dockerfile" -t "${IMAGE_NAME}" "${PROJECT_ROOT}"

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    echo "==> Removing previous container '${CONTAINER_NAME}' ..."
    docker rm -f "${CONTAINER_NAME}" > /dev/null
fi

echo "==> Starting container on port ${PORT} ..."
docker run -d \
    --name "${CONTAINER_NAME}" \
    -e "PORT=${PORT}" \
    -p "${PORT}:${PORT}" \
    -v "${PROJECT_ROOT}/db:/app/db" \
    --restart unless-stopped \
    "${IMAGE_NAME}"

echo
echo "==> Dashboard running at: http://localhost:${PORT}"
echo "==> Logs:   docker logs -f ${CONTAINER_NAME}"
echo "==> Stop:   docker stop ${CONTAINER_NAME}"
