# Devcontainer Configuration

This document describes the devcontainer setup for the LLM Metadata project, providing an isolated Claude Code development environment. This README is designed to be complete enough to reproduce the setup from scratch.

## Specifications (from prompt-config-devcontainer.md)

### Container Requirements
- **Name**: `claude-dev`
- **User**: `devuser` with sudo privileges
- **Compose file**: `.devcontainer/docker-compose.devcontainer.yml`
- **Environment**: Loads `.env` file via CLI `--env-file` flag
- **Claude Code**: Always starts with `--dangerously-skip-permissions`
- **VS Code**: Python development extensions

### File System Isolation
- **NEVER** volume mount the workspace folder to the container
- Volume mount specific folders for data persistence (`data/`)
- Use named volume for `.venv` (inside workspace volume)
- Volume mount Claude config/skills/history (`./.claude`, `~/.claude`)
- Launch Jupyter server on startup with config from `.env`

### Network Isolation
- **NEVER** share network with host
- Egress controlled through whitelist rules via `init-firewall.sh` (optional)
- Allow access to Docker internal services (GROBID, Qdrant)
- New service `claude-dev-reverse-proxy` (nginx) for secure API access
- Pass environment variables explicitly through docker-compose

---

## Implementation Details

### Dockerfile (`Dockerfile`)

**Base Image:** `python:3.12-slim`

**System Packages:**
```
git, curl, wget, sudo, zsh, fzf, less, procps, man-db, unzip, gnupg2, jq,
nano, vim, build-essential, openssh-client, iptables, ipset, iproute2,
dnsutils, aggregate
```

**Additional Tools:**
- GitHub CLI (`gh`) - for GitHub API access
- git-delta (v0.18.2) - for better diff output
- Node.js 20 - required for Claude Code
- uv (from `ghcr.io/astral-sh/uv:latest`) - Python package manager
- Claude Code (`@anthropic-ai/claude-code@latest`) - installed globally via npm
- oh-my-zsh - shell framework

**User Setup:**
- Username: `devuser` (UID 1000, GID 1000)
- Shell: `/bin/zsh`
- Sudo: passwordless for all commands
- Firewall sudo: specific rule for `/usr/local/bin/init-firewall.sh`

**Environment Variables:**
```bash
TZ=America/New_York
SHELL=/bin/zsh
EDITOR=nano
VISUAL=nano
DEVCONTAINER=true
```

**Shell Configuration:**
- Claude alias: `alias claude="claude --dangerously-skip-permissions"`
- Command history persisted to `/commandhistory/.bash_history`

**Scripts Copied to `/usr/local/bin/`:**
- `init-firewall.sh` - network egress whitelist
- `init-workspace.sh` - git clone + venv setup

**CRLF Handling:** All scripts have `sed -i 's/\r$//'` applied for Windows compatibility.

---

### Docker Compose (`docker-compose.devcontainer.yml`)

**Networks:**
```yaml
networks:
  claude-dev-network:
    driver: bridge
```

**Service: `claude-dev`**
```yaml
build:
  context: .                           # Project root (NOT .devcontainer/)
  dockerfile: .devcontainer/Dockerfile
  args:
    CLAUDE_CODE_VERSION: latest

container_name: claude-dev

cap_add:
  - NET_ADMIN                          # Required for iptables firewall
  - NET_RAW                            # Required for iptables firewall

networks:
  - claude-dev-network                 # For reverse proxy
  - default                            # For GROBID/Qdrant access

command: sleep infinity
```

**Environment Variables (`claude-dev`):**
| Variable | Value | Source |
|----------|-------|--------|
| `GROBID_URL` | `http://grobid:8070` | Hardcoded |
| `QDRANT_URL` | `http://qdrant:6333` | Hardcoded |
| `OPENAI_API_BASE` | `http://claude-dev-reverse-proxy:8080/v1` | Hardcoded |
| `JUPYTER_PORT` | `${JUPYTER_PORT:-8881}` | From .env |
| `JUPYTER_TOKEN` | `${JUPYTER_TOKEN}` | From .env |
| `JUPYTER_URL` | `${JUPYTER_URL:-http://localhost:8881}` | From .env |
| `ALLOW_IMG_OUTPUT` | `${ALLOW_IMG_OUTPUT:-true}` | From .env |
| `GIT_REPO_URL` | `${GIT_REPO_URL:-git@github.com:your-org/llm_metadata.git}` | From .env |
| `ENABLE_FIREWALL` | `${ENABLE_FIREWALL:-true}` | From .env |

**Note:** `OPENAI_API_KEY` is intentionally NOT passed to the container.

**Volumes (`claude-dev`):**
| Type | Source | Target | Purpose |
|------|--------|--------|---------|
| Named | `workspace` | `/workspace` | Git repo, source, .venv (NOT host-mounted) |
| Bind | `./data` | `/workspace/data` | Shared datasets (synced with host) |
| Bind | `./.claude` | `/workspace/.claude` | Claude project settings |
| Named | `uv-cache` | `/home/devuser/.cache/uv` | Python package cache |
| Named | `command-history` | `/commandhistory` | Shell history |

**Ports:**
| Host | Container | Service |
|------|-----------|---------|
| `${JUPYTER_PORT:-8881}` | `${JUPYTER_PORT:-8881}` | Jupyter Lab |
| `4200` | `4200` | Prefect Dashboard |

**Service: `claude-dev-reverse-proxy`**
```yaml
image: nginx:alpine
container_name: claude-dev-reverse-proxy

networks:
  - claude-dev-network

environment:
  OPENAI_API_KEY: ${OPENAI_API_KEY}    # Only the proxy has the API key

volumes:
  - .devcontainer/claude-dev-reverse-proxy.conf:/etc/nginx/templates/default.conf.template:ro

healthcheck:
  test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

### VS Code Configuration (`devcontainer.json`)

**Compose Files:**
```json
"dockerComposeFile": [
    "../docker-compose.yml",
    "docker-compose.devcontainer.yml"
]
```

**Extensions:**
- `anthropic.claude-code` - Claude Code
- `ms-python.python` - Python
- `ms-python.vscode-pylance` - Pylance
- `ms-toolsai.jupyter` - Jupyter
- `ms-toolsai.jupyter-renderers` - Jupyter renderers
- `ms-toolsai.jupyter-keymap` - Jupyter keymaps
- `charliermarsh.ruff` - Ruff linter/formatter
- `eamodio.gitlens` - GitLens

**VS Code Settings:**
```json
{
    "python.defaultInterpreterPath": "/workspace/.venv/bin/python",
    "python.envFile": "${workspaceFolder}/.env",
    "python.analysis.extraPaths": ["${workspaceFolder}/src"],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    },
    "jupyter.notebookFileRoot": "${workspaceFolder}",
    "terminal.integrated.defaultProfile.linux": "zsh"
}
```

**Container Environment:**
```json
"containerEnv": {
    "PYTHONPATH": "/workspace/src",
    "UV_LINK_MODE": "copy"
}
```

**Additional Mounts (via devcontainer.json):**
```json
"mounts": [
    "source=${localEnv:USERPROFILE}/.claude,target=/home/devuser/.claude,type=bind,consistency=cached"
]
```
*Note: On Linux/Mac, change `USERPROFILE` to `HOME`.*

**Lifecycle Commands:**
| Hook | Command |
|------|---------|
| `postStartCommand` | Runs firewall if `ENABLE_FIREWALL=true` |
| `postAttachCommand` | Runs `init-workspace.sh` + starts Jupyter |

---

### Workspace Initialization (`init-workspace.sh`)

```bash
#!/bin/bash
set -e

# Clone repository on first run (if workspace is empty)
if [ ! -f /workspace/.git/config ]; then
    git clone "${GIT_REPO_URL}" /workspace/temp-clone
    mv /workspace/temp-clone/* /workspace/temp-clone/.* /workspace/ 2>/dev/null || true
    rm -rf /workspace/temp-clone
fi

# Create virtual environment if missing
if [ ! -d /workspace/.venv ]; then
    uv venv /workspace/.venv
fi

# Install dependencies (uses pyproject.toml)
uv sync --frozen
```

**Why `postAttachCommand`?** VS Code's SSH agent forwarding is only available after attach, so git clone must run then.

---

### Reverse Proxy (`claude-dev-reverse-proxy.conf`)

```nginx
server {
    listen 8080;

    # Health check endpoint
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }

    # OpenAI API proxy
    location / {
        proxy_pass https://api.openai.com;
        proxy_http_version 1.1;
        proxy_ssl_server_name on;

        # Inject API key (container never sees this)
        proxy_set_header Authorization "Bearer ${OPENAI_API_KEY}";
        proxy_set_header Host api.openai.com;
        proxy_set_header X-Real-IP $remote_addr;

        # Timeouts for long-running completions
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;

        # Allow large request bodies for embeddings
        client_max_body_size 10M;
    }
}
```

**Note:** nginx uses `/etc/nginx/templates/` directory for environment variable substitution at startup.

---

### Firewall (`init-firewall.sh`)

**Default Policies:** DROP all INPUT, OUTPUT, FORWARD

**Always Allowed:**
- DNS (UDP port 53)
- SSH (TCP port 22, for git)
- Localhost
- Docker internal networks (`172.16.0.0/12`)
- Established connections

**Whitelisted Domains:**
| Category | Domains |
|----------|---------|
| GitHub | Dynamic IPs from `api.github.com/meta` |
| Anthropic | `api.anthropic.com`, `sentry.io`, `statsig.anthropic.com`, `statsig.com` |
| Data APIs | `zenodo.org`, `api.openalex.org`, `api.unpaywall.org` |
| Python | `pypi.org`, `files.pythonhosted.org` |
| VS Code | `marketplace.visualstudio.com`, `vscode.blob.core.windows.net`, `update.code.visualstudio.com` |
| npm | `registry.npmjs.org` |

**Note:** `api.openai.com` is NOT whitelisted - access goes through the reverse proxy.

**Verification:** Script tests that `example.com` is blocked and `api.github.com` is accessible.

---

## Required `.env` Variables

```bash
# Git repository (SSH format for VS Code agent forwarding)
GIT_REPO_URL=git@github.com:your-org/llm_metadata.git

# OpenAI API (passed to reverse proxy only, NOT to container)
OPENAI_API_KEY=sk-...

# Jupyter
JUPYTER_PORT=8881
JUPYTER_TOKEN=your-secure-token

# Optional: Disable firewall for debugging (default: true)
ENABLE_FIREWALL=true

# Optional: Allow image output in Jupyter (default: true)
ALLOW_IMG_OUTPUT=true
```

---

## Usage

### Starting via VS Code (Recommended)

1. Open the project in VS Code
2. Press `F1` > "Dev Containers: Reopen in Container"
3. Wait for `postAttachCommand` to complete (git clone, venv setup)

### Starting via CLI

```bash
cd /path/to/llm_metadata
docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml up -d
```

### SSH Agent Forwarding (Windows)

1. Start Windows OpenSSH Agent:
   ```powershell
   Get-Service ssh-agent | Set-Service -StartupType Automatic
   Start-Service ssh-agent
   ```

2. Add your SSH key:
   ```powershell
   ssh-add ~/.ssh/id_ed25519
   ```

VS Code automatically forwards your SSH agent to the container.

---

## Verification Commands

### Basic Checks

```bash
# Check user
docker exec claude-dev whoami
# Expected: devuser

# Check shell
docker exec claude-dev sh -c 'echo $SHELL'
# Expected: /bin/zsh

# Test reverse proxy health
docker exec claude-dev sh -c "curl -s http://claude-dev-reverse-proxy:8080/health"
# Expected: OK

# Verify API key NOT in container
docker exec claude-dev sh -c "printenv | grep OPENAI"
# Expected: Only OPENAI_API_BASE, NOT OPENAI_API_KEY

# Test OpenAI through proxy
docker exec claude-dev sh -c "curl -s http://claude-dev-reverse-proxy:8080/v1/models | head -c 100"
# Expected: JSON with model list

# Test internal services
docker exec claude-dev sh -c "curl -s http://grobid:8070/api/isalive"
# Expected: true

docker exec claude-dev sh -c "curl -s http://qdrant:6333/healthz"
# Expected: healthz check passed
```

### Firewall Verification (ENABLE_FIREWALL=true)

```bash
# Run firewall
docker exec claude-dev sh -c "sudo /usr/local/bin/init-firewall.sh"
# Expected: Completes with "Firewall verification passed" messages

# Test blocking
docker exec claude-dev sh -c "curl --connect-timeout 5 https://example.com" 2>&1
# Expected: Connection refused or timeout

# Test allowed domain
docker exec claude-dev sh -c "curl -s --connect-timeout 5 https://api.github.com/zen"
# Expected: GitHub zen message
```

### Firewall Disabled (ENABLE_FIREWALL=false)

```bash
# Start with firewall disabled
ENABLE_FIREWALL=false docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml up -d claude-dev

# Verify setting
docker exec claude-dev sh -c "printenv ENABLE_FIREWALL"
# Expected: false

# Test unrestricted access
docker exec claude-dev sh -c "curl -s --connect-timeout 5 https://example.com | head -c 100"
# Expected: HTML content (not blocked)

# Services still work
docker exec claude-dev sh -c "curl -s http://grobid:8070/api/isalive"
# Expected: true
```

---

## Rebuilding

**VS Code:**
- `F1` > "Dev Containers: Rebuild Container" (uses cache)
- `F1` > "Dev Containers: Rebuild Container Without Cache" (full rebuild)

**CLI:**
```bash
docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml build --no-cache claude-dev
docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml up -d claude-dev
```

---

## Implementation Learnings

### Issues Encountered and Fixes

1. **Path Resolution in docker-compose**
   - **Issue**: Relative paths resolved from project root when using `-f`
   - **Fix**: All paths relative to project root (`context: .`, `./data`)

2. **Windows CRLF Line Endings**
   - **Issue**: Scripts fail with "No such file or directory" (bash looks for `/bin/bash\r`)
   - **Fix**: `sed -i 's/\r$//'` in Dockerfile after each COPY

3. **ipset Duplicate Entries**
   - **Issue**: DNS returns duplicate IPs, `ipset add` fails
   - **Fix**: Use `ipset add -exist` to silently ignore duplicates

4. **Docker Network Isolation**
   - **Issue**: `claude-dev` couldn't reach GROBID/Qdrant on different network
   - **Fix**: Added `claude-dev` to both `claude-dev-network` and `default` networks

5. **Firewall Blocking Docker Internal Traffic**
   - **Issue**: Only host network allowed, not other Docker subnets
   - **Fix**: Added `172.16.0.0/12` to whitelist

6. **Script Accessibility**
   - **Issue**: Scripts in `.devcontainer/` not accessible from container
   - **Fix**: Copy scripts to `/usr/local/bin/` during build

7. **SSH Agent Timing**
   - **Issue**: Agent not available during `postCreateCommand`
   - **Fix**: Use `postAttachCommand` for git clone

8. **env_file Path Errors**
   - **Issue**: `env_file: ../.env` path resolution failed
   - **Fix**: Use CLI `--env-file .env` instead

---

## Recommendations for Future Versions

### High Priority

1. **Add `.dockerignore`** - Exclude `data/`, `.venv/`, `__pycache__/` from build context

2. **Health Check for claude-dev** - Verify workspace initialization complete

3. **Git Config in Container** - Configure `user.name` and `user.email` in `init-workspace.sh`

### Medium Priority

4. **Pre-commit Hooks** - Install during workspace initialization

5. **Volume Backup** - Document backup/restore for `workspace` volume

### Low Priority

6. **Multi-stage Dockerfile** - Smaller final image

7. **Container Healthcheck** - Better orchestration with dependent services
