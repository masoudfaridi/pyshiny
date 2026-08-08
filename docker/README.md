# Docker

Everything needed to containerize and run the dashboard. Two ways to do it
-- pick whichever you have installed. Both build the same image, publish
the same configurable port, and persist the SQLite database in `../db` on
the host so accounts survive restarts and rebuilds.

## Option A -- docker compose (recommended)

```bash
cd docker
docker compose up --build -d
```

Runs on port `8000` by default. Use a different port without editing any
file:

```bash
PORT=9000 docker compose up --build -d
```

or copy `docker/.env.example` to `docker/.env` and set `PORT` there once.

Stop it:

```bash
docker compose down
```

## Option B -- plain `docker` (no compose needed)

From the project root:

```bash
bash docker/run.sh          # port 8000
bash docker/run.sh 9000     # port 9000
```

This builds the image and runs it detached in one step. Re-running the
script rebuilds and replaces the previous container.

## Files here

| File | Purpose |
|---|---|
| `Dockerfile` | Builds the image (Python 3.12-slim, deps, non-root user, healthcheck). |
| `entrypoint.sh` | Starts Shiny bound to `0.0.0.0:$PORT` inside the container. |
| `docker-compose.yml` | One-command build + run, port set via `$PORT`. |
| `.env.example` | Copy to `.env` to set a default `PORT` for compose. |
| `run.sh` | One-command build + run using plain `docker build` / `docker run`. |

See the "Docker" section in the main `README.md` for more detail (health
checks, why the database is a volume, changing the port, etc.).
