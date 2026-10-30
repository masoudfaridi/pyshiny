# syntax=docker/dockerfile:1
#
# Build context for this Dockerfile is the PROJECT ROOT (one level above
# this file), not the docker/ folder itself -- see docker-compose.yml
# (context: ..) and docker/run.sh, which both invoke `docker build`
# correctly. If you build manually, do it from the project root:
#
#   docker build -f docker/Dockerfile -t pyshiny .
#
FROM python:3.12-slim

LABEL org.opencontainers.image.title="pyshiny" \
      org.opencontainers.image.description="Shiny for Python AdminLTE-style dashboard with SQLite-backed RBAC auth"

# System packages:
#   fonts-dejavu-core -- gives the login CAPTCHA (auth/captcha.py) a real
#                        TrueType font. Without it, Pillow silently falls
#                        back to a tiny bitmap font -- the app still works,
#                        the CAPTCHA is just uglier and harder to read.
#   curl               -- used by the HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so this layer stays cached across
# rebuilds that only touch application code (app.py, auth/, tabs/, static/).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY . .

# db/ holds the SQLite files that auth/core.py creates automatically on
# first run (a superadmin with a random password, printed in `docker logs`
# and saved to db/initial_superadmin_password.txt). It's meant to be mounted
# as a volume -- see docker-compose.yml and docker/run.sh -- so accounts
# survive container restarts and rebuilds.
#
# Run as a non-root user. The application code stays owned by root (read-only
# for the app user); only db/ is writable.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/db \
    && chown appuser:appuser /app/db \
    && chmod 700 /app/db

COPY docker/entrypoint.sh /entrypoint.sh
# Strip Windows line endings (a CRLF checkout would make the entrypoint fail).
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

USER appuser

# The port Shiny listens on INSIDE the container. Override at `docker run`
# time with `-e PORT=9000` (entrypoint.sh reads this at startup) -- whatever
# value you pick, publish the same port with `-p PORT:PORT`. docker/run.sh
# and docker-compose.yml both do this for you automatically from a single
# PORT value, so you never have to edit this file to change ports.
ENV PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Interface language: "en" (English, LTR) or "fa" (Persian, RTL). Override with
# `-e APP_LANG=fa` (docker/run.sh and docker-compose.yml pass it through).
ENV APP_LANG=en
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
