#!/usr/bin/env bash
# Starts the Shiny server bound to 0.0.0.0 on $PORT (default 8000) so the
# port published with `docker run -p HOST:CONTAINER` actually reaches it.
set -euo pipefail

PORT="${PORT:-8000}"

echo "pyshiny: starting on 0.0.0.0:${PORT}"
exec shiny run app.py --host 0.0.0.0 --port "${PORT}"
