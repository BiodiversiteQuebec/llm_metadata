Edit devcontainer config for workspace.

* Dev container setup for claude development environment with isolation and services are done with docker-compose.
* Dev container should be named `claude-dev`.
    * Should start from .devcontainer/docker-compose.devcontainer.yml file. 
    * Should load .env file for environment variables.
    * Claude should always start as --dangerously-skip-permissions
    * To be operated from vscode devcontainer. Should install relevant VSCode extensions for Python development and remove unnecessary ones.
* Workspace should have file systeme isolation.
    * NEVER volume mount the workspace folder to the `claude-dev` container.
    * Volume mount specific folders for relevant data persistence. (e.g., data/, qdrant storage, etc)
    * RECOMMEND Volume mount .venv or virtual environment folder for python dependencies or install dependencies directly in the container.
    * Create a user `devuser` in the `claude-dev` container with sudo privileges for development.
    * Volume mount claude development config, skills, mcp servers and development history (./.claude, ~/.claude, etc)
    * Launch Jupyter server on startup. Pass jupyter config to docker-compose file # Jupyter lab token, JUPYTER_PORT, JUPYTER_URL, JUPYTER_TOKEN, ALLOW_IMG_OUTPUT from .env file.
* Workspace should have network isolation.
    * NEVER share network with host.
    * OPTIONAL Egress from the `claude-dev` container controlled through whitelist rules only from the '.devcontainer/init-firewall.sh' script managed by devuser. Script should be run at container startup.
    * Allow access to specific services running on host (e.g., databases, etc) if necessary.
    * New service `claude-dev-reverse-proxy` nginx to handle reverse proxying requests from claude-dev to host services requiring secure access (openai api, etc). Store nginx config in .devcontainer/claude-dev-reverse-proxy.conf. Pass explicitly the environment variables necessary for reverse proxying through docker-compose file for claude-dev-reverse-proxy service and claude-dev service.
* Remove any vscode devcontainer.json startup commands that are not necessary for this setup.

Propose other relevant configurations that would enhance the development experience in this devcontainer setup for this workspace.