# Devcontainer Configuration

## Architecture

Uses the **compose overlay** pattern:

```
docker-compose.yml                          # Base services (GROBID, Qdrant)
.devcontainer/docker-compose.devcontainer.yml  # Adds app service for dev
.devcontainer/devcontainer.json                # VS Code integration
.devcontainer/Dockerfile                       # Python 3.12, uv, Node.js, Claude Code
.devcontainer/init-firewall.sh                 # Outbound traffic whitelist
```

The root `docker-compose.yml` is not modified and remains usable independently.

## What starts automatically

| Step | Runs when | What it does |
|---|---|---|
| `postCreateCommand` | First build only | `uv sync --all-extras` — installs all Python deps into `/workspace/.venv` |
| `postStartCommand` | Every container start | Sets up firewall, then starts Jupyter Lab if not already running |

## Services & ports

| Port | Service | Access from container |
|---|---|---|
| `${JUPYTER_PORT}` (default 8881) | Jupyter Lab | `localhost:8881` |
| 8070 | GROBID | `http://grobid:8070` (via Docker network) |
| 6333 | Qdrant | `http://qdrant:6333` (via Docker network) |
| 4200 | Prefect Dashboard | `localhost:4200` (when running) |
| 8000, 8080 | Dev servers | Available for ad-hoc use |

Inside the container, `GROBID_URL` and `QDRANT_URL` are automatically set to the Docker service names (not `localhost`).

## Environment variables

All variables from the project root `.env` are loaded into the container via `env_file`. This includes `OPENAI_API_KEY`, `JUPYTER_PORT`, `JUPYTER_TOKEN`, etc.

## Firewall

Controlled by the `ENABLE_FIREWALL` env var in `.env` (defaults to `true`). Set to `false` to disable:

```env
ENABLE_FIREWALL=false
```

When enabled, the container runs a **whitelist-only outbound firewall** (`init-firewall.sh`). Only these destinations are allowed:

- **GitHub** (API, web, git — via IP ranges from `/meta`)
- **Anthropic** (`api.anthropic.com`, `sentry.io`, `statsig.anthropic.com`)
- **OpenAI** (`api.openai.com`)
- **Data APIs** (`zenodo.org`, `api.openalex.org`, `api.unpaywall.org`)
- **Python packages** (`pypi.org`, `files.pythonhosted.org`)
- **VS Code** (marketplace, updates)
- **npm** (`registry.npmjs.org`)
- **Docker host network** (auto-detected)
- **localhost / DNS**

To add a new domain, append it to the `for domain in ...` loop in `init-firewall.sh`.

## Named volumes

| Volume | Mounted at | Purpose |
|---|---|---|
| `venv` | `/workspace/.venv` | Isolates Linux venv from host Windows venv |
| `uv-cache` | `/home/dev/.cache/uv` | Speeds up dependency installs across rebuilds |
| `command-history` | `/commandhistory` | Persists shell history across container restarts |

## Claude Code

The `claude` command is aliased to `claude --dangerously-skip-permissions`.

Host `~/.claude` is bind-mounted into the container for persistent settings. On Linux/Mac, edit the `mounts` entry in `devcontainer.json` to use `${localEnv:HOME}` instead of `${localEnv:USERPROFILE}`.

## Rebuilding

From the VS Code command palette: **Dev Containers: Rebuild Container**.

To rebuild without cache: **Dev Containers: Rebuild Container Without Cache**.
