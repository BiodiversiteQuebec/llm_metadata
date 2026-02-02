# Devcontainer Configuration

## Architecture

```
.devcontainer/docker-compose.devcontainer.yml  # Claude development environment + base services (GROBID, Qdrant)
.devcontainer/devcontainer.json                # VS Code integration
.devcontainer/Dockerfile                       # Python 3.12, uv, Node.js, Claude Code
.devcontainer/init-firewall.sh                 # Outbound traffic whitelist
```

## What starts automatically

| Step | Runs when | What it does |
|---|---|---|
| `postCreateCommand` | First build only | `uv sync --all-extras` — installs all Python deps into `/workspace/.venv` |
| container entrypoint | Every container start | Sets up firewall (when enabled) before starting the main process |
| `postStartCommand` | Every container start | Starts Jupyter Lab if not already running |

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

No special `claude` alias is configured in the container.

Host `~/.claude` is bind-mounted into the container for persistent settings. On Linux/Mac, edit the `mounts` entry in `devcontainer.json` to use `${localEnv:HOME}` instead of `${localEnv:USERPROFILE}`.

## Security model

Running Claude Code inside the devcontainer with `--dangerously-skip-permissions` is materially safer than running it directly on the host. The container limits the blast radius of any misinterpreted instruction or hallucinated command.

### What the container isolates

**Filesystem scope.** Claude can only see `/workspace` (the bind-mounted repo) and the container's own filesystem. It cannot access your home directory, SSH keys, browser profiles, credential stores, other project directories, or OS-level configuration on the host.

**Process isolation.** Processes inside the container are namespaced. Claude cannot see or signal host processes, read other users' memory, access the Docker socket, or interact with other running applications.

**Network control.** When `ENABLE_FIREWALL=true`, `init-firewall.sh` restricts outbound traffic to an explicit allowlist (OpenAI, GitHub, Anthropic, data APIs, package registries). This prevents data exfiltration to arbitrary endpoints.

**Privilege boundaries.** VS Code attaches as the `dev` user (UID 1000). The container process starts as root only to apply the firewall rules at boot, then drops privileges for the main command.

### Threat scenarios

| Scenario | Without container | With container |
|---|---|---|
| Prompt injection causes `rm -rf ~` | Destroys home directory | Only affects container filesystem; host home untouched |
| Hallucinated `curl ... \| sh` | Installs malware on host | Confined to ephemeral container; firewall can block it |
| Reads `~/.ssh/id_rsa` or `~/.aws/credentials` | Full access | Files don't exist in container |
| Exfiltrates code to external server | Unrestricted | Firewall allowlist blocks unknown destinations |
| Modifies system packages or configs | Persists on host | Lost on container rebuild |

### What it does NOT protect against

- **The bind-mounted workspace.** Claude has full read/write to the repo. Git is the safety net for accidental or destructive changes.
- **Secrets in environment variables.** `.env` is loaded into the container. Claude can read `OPENAI_API_KEY`, `ZENODO_ACCESS_TOKEN`, etc. via `printenv`. This is inherent to the workflow.
- **Outbound network when firewall is disabled.** With `ENABLE_FIREWALL=false`, Claude can reach any network endpoint.

### The practical tradeoff

Running `--dangerously-skip-permissions` on the host gives Claude the same access as your user account — every file, credential, and network connection you have. The devcontainer reduces this to: one project directory, explicitly declared secrets, and (optionally) a filtered network.

## Rebuilding

From the VS Code command palette: **Dev Containers: Rebuild Container**.

To rebuild without cache: **Dev Containers: Rebuild Container Without Cache**.
