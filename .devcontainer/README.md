# Devcontainer Configuration

This document describes the devcontainer setup for the LLM Metadata project, providing an isolated Claude Code development environment.

## Specifications (from prompt-config-devcontainer.md)

### Container Requirements
- **Name**: `claude-dev`
- **User**: `devuser` with sudo privileges
- **Compose file**: `.devcontainer/docker-compose.devcontainer.yml`
- **Environment**: Loads `.env` file for environment variables
- **Claude Code**: Always starts with `--dangerously-skip-permissions`
- **VS Code**: Relevant Python extensions, remove unnecessary ones

### File System Isolation
- **NEVER** volume mount the workspace folder to the container
- Volume mount specific folders for data persistence (e.g., `data/`, qdrant storage)
- Volume mount `.venv` or install dependencies directly in container
- Volume mount Claude config/skills/history (`./.claude`, `~/.claude`)
- Launch Jupyter server on startup with config from `.env`

### Network Isolation
- **NEVER** share network with host
- Egress controlled through whitelist rules via `init-firewall.sh`
- Allow access to specific host services if necessary
- New service `claude-dev-reverse-proxy` (nginx) for secure API access
- Pass environment variables explicitly through docker-compose

---

## Implementation

### Architecture

Uses the **compose overlay** pattern:

```
docker-compose.yml                              # Base services (GROBID, Qdrant)
.devcontainer/docker-compose.devcontainer.yml  # Adds claude-dev + reverse proxy
.devcontainer/devcontainer.json                # VS Code integration
.devcontainer/Dockerfile                       # Python 3.12, uv, Node.js, Claude Code
.devcontainer/init-firewall.sh                 # Outbound traffic whitelist
.devcontainer/init-workspace.sh                # Git clone + venv setup
.devcontainer/claude-dev-reverse-proxy.conf    # nginx config for API proxy
```

### File Structure

```
.devcontainer/
├── Dockerfile                      # Container image (devuser, zsh, tools)
├── devcontainer.json               # VS Code devcontainer config
├── docker-compose.devcontainer.yml # Service definitions (paths relative to project root)
├── init-firewall.sh                # Network egress whitelist
├── init-workspace.sh               # Workspace initialization (git clone, venv)
├── claude-dev-reverse-proxy.conf   # nginx config for API proxy
├── prompt-config-devcontainer.md   # Original specifications
└── README.md                       # This file
```

### Services & Networks

| Service | Purpose | Networks |
|---------|---------|----------|
| `claude-dev` | Main development container | claude-dev-network, default |
| `claude-dev-reverse-proxy` | OpenAI API proxy (injects API key) | claude-dev-network |
| `grobid` | PDF parsing service | default |
| `qdrant` | Vector database | default |

The container connects to **both** networks:
- `claude-dev-network`: For reverse proxy communication
- `default`: For GROBID/Qdrant access

### Volume Mounts

| Type | Source | Target | Purpose |
|------|--------|--------|---------|
| Named | `workspace` | `/workspace` | Git repo, source, builds (NOT host-mounted) |
| Named | `uv-cache` | `/home/devuser/.cache/uv` | Python package cache |
| Named | `command-history` | `/commandhistory` | Shell history |
| Bind | `./data` | `/workspace/data` | Shared datasets |
| Bind | `./.claude` | `/workspace/.claude` | Claude project settings |

### Environment Variables

**Container (`claude-dev`):**
- `GROBID_URL=http://grobid:8070`
- `QDRANT_URL=http://qdrant:6333`
- `OPENAI_API_BASE=http://claude-dev-reverse-proxy:8080/v1` (NO API key!)
- `GIT_REPO_URL` - SSH format for git clone
- `JUPYTER_PORT`, `JUPYTER_TOKEN`, `JUPYTER_URL`
- `ENABLE_FIREWALL` - Set to `false` to disable firewall (default: `true`)

**Reverse Proxy (`claude-dev-reverse-proxy`):**
- `OPENAI_API_KEY` - Injected into Authorization header, never reaches container

### Startup Sequence

| Step | Hook | What it does |
|------|------|--------------|
| 1 | Container start | `sleep infinity` (keeps container running) |
| 2 | `postStartCommand` | Runs firewall if `ENABLE_FIREWALL=true` (default) |
| 3 | `postAttachCommand` | `/usr/local/bin/init-workspace.sh` + Jupyter startup |

**Why postAttachCommand for workspace init?**
- VS Code's SSH agent forwarding only available after attach
- Git clone requires SSH access for private repos

### Firewall Whitelist

Only these destinations are allowed:

| Category | Domains |
|----------|---------|
| GitHub | API, web, git (via IP ranges from `/meta`) |
| Anthropic | `api.anthropic.com`, `sentry.io`, `statsig.anthropic.com`, `statsig.com` |
| Data APIs | `zenodo.org`, `api.openalex.org`, `api.unpaywall.org` |
| Python | `pypi.org`, `files.pythonhosted.org` |
| VS Code | `marketplace.visualstudio.com`, `vscode.blob.core.windows.net`, `update.code.visualstudio.com` |
| npm | `registry.npmjs.org` |
| Docker | All internal networks (`172.16.0.0/12`) |

**Note:** `api.openai.com` is NOT in the whitelist - access goes through the reverse proxy.

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

### Required `.env` Variables

```bash
# Git repository (SSH format for VS Code agent forwarding)
GIT_REPO_URL=git@github.com:your-org/llm_metadata.git

# OpenAI API (passed to reverse proxy only)
OPENAI_API_KEY=sk-...

# Jupyter
JUPYTER_PORT=8881
JUPYTER_TOKEN=your-token

# Optional: Disable firewall for debugging (default: true)
ENABLE_FIREWALL=true
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

## Implementation Learnings

### Issues Encountered and Fixes

1. **Path Resolution in docker-compose**
   - **Issue**: Relative paths resolved from project root when using `-f`, not from `.devcontainer/`
   - **Fix**: All paths in `docker-compose.devcontainer.yml` are relative to project root
   - **Example**: `context: .` not `context: ..`, `./data` not `../data`

2. **Windows CRLF Line Endings**
   - **Issue**: Shell scripts copied with CRLF fail with "No such file or directory" (bash looks for `/bin/bash\r`)
   - **Fix**: Added `sed -i 's/\r$//'` in Dockerfile after each COPY

3. **ipset Duplicate Entries**
   - **Issue**: DNS can return duplicate IPs, causing `ipset add` to fail
   - **Fix**: Use `ipset add -exist` to silently ignore duplicates

4. **Docker Network Isolation**
   - **Issue**: `claude-dev` on `claude-dev-network` couldn't reach GROBID/Qdrant on `default` network
   - **Fix**: Added `claude-dev` to both networks in docker-compose

5. **Firewall Blocking Docker Internal Traffic**
   - **Issue**: Firewall only allowed detected host network (172.20.0.0/24), not other Docker networks (172.19.0.0/16)
   - **Fix**: Added `172.16.0.0/12` to whitelist (covers all Docker default networks)

6. **Script Accessibility in Container**
   - **Issue**: `init-workspace.sh` referenced from `.devcontainer/` path but `.devcontainer/` not mounted
   - **Fix**: Copy scripts into image at `/usr/local/bin/` during build

7. **postCreateCommand vs postAttachCommand**
   - **Issue**: SSH agent forwarding not available during `postCreateCommand` (runs before VS Code attaches)
   - **Fix**: Moved git clone to `postAttachCommand` (runs after VS Code attaches and forwards SSH agent)

8. **env_file Path in docker-compose**
   - **Issue**: `env_file: ../.env` caused path resolution errors
   - **Fix**: Removed `env_file` from compose, use `--env-file .env` CLI flag instead

---

## Recommendations for Future Versions

### High Priority

1. **Add `.dockerignore`**
   - Exclude `data/`, `.venv/`, `*.pyc`, `__pycache__/` from build context
   - Significantly reduces build time

2. **Health Check for claude-dev**
   - Add health check to verify workspace initialization complete
   - Enable `depends_on` with `condition: service_healthy`

3. **Git Config in Container**
   - Configure `user.name` and `user.email` for commits from container
   - Can be done in `init-workspace.sh`

### Medium Priority

4. **Pre-commit Hooks**
   - Install pre-commit during workspace initialization
   - Ensures code quality in isolated environment

5. **Volume Backup Documentation**
   - Document how to backup/restore `workspace` named volume
   - Important since source code lives in Docker volume

### Low Priority

7. **Multi-stage Dockerfile**
   - Separate build deps from runtime
   - Smaller final image

8. **Container Healthcheck**
   - Add healthcheck for `claude-dev` service
   - Better orchestration with dependent services

---

## Verification Commands

```bash
# Check user
docker exec claude-dev whoami
# Expected: devuser

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

# Run firewall (after container start)
docker exec claude-dev sh -c "sudo /usr/local/bin/init-firewall.sh"
# Expected: Completes with "Firewall verification passed" messages

# Test firewall blocking (when ENABLE_FIREWALL=true)
docker exec claude-dev sh -c "curl --connect-timeout 5 https://example.com" 2>&1
# Expected: Connection refused or timeout (blocked by firewall)
```

### Verification: Firewall Disabled (ENABLE_FIREWALL=false)

```bash
# Start container with firewall disabled
ENABLE_FIREWALL=false docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml up -d claude-dev

# Verify ENABLE_FIREWALL is false
docker exec claude-dev sh -c "printenv ENABLE_FIREWALL"
# Expected: false

# Test unrestricted internet access
docker exec claude-dev sh -c "curl -s --connect-timeout 5 https://example.com | head -c 100"
# Expected: HTML content from example.com (not blocked)

# Verify internal services still work
docker exec claude-dev sh -c "curl -s http://grobid:8070/api/isalive"
# Expected: true

docker exec claude-dev sh -c "curl -s http://qdrant:6333/healthz"
# Expected: healthz check passed

docker exec claude-dev sh -c "curl -s http://claude-dev-reverse-proxy:8080/health"
# Expected: OK
```

## Rebuilding

From VS Code command palette:
- **Dev Containers: Rebuild Container** - Uses cache
- **Dev Containers: Rebuild Container Without Cache** - Full rebuild

From CLI:
```bash
docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml build --no-cache claude-dev
docker compose --env-file .env -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml up -d claude-dev
```
