Edit devcontainer config for workspace.

* Should load .env file for environment variables.
* Should start from .devcontainer/docker-compose.devcontainer.yml file.
* Devcontainer should have access to internet.
* Pass jupyter config to docker-compose file # Jupyter lab token, JUPYTER_PORT, JUPYTER_URL, JUPYTER_TOKEN, ALLOW_IMG_OUTPUT from .env file.
* Should install necessary python packages from requirements.txt in the devcontainer using uvx.
* Claude should always start as --dangerously-skip-permissions
* Should install relevant VSCode extensions for Python development and remove unnecessary ones.
* Volume mount the workspace folder.
* Volume mount the ~/.claude folder for persistent Claude settings.
* Set up port forwarding for common development ports (e.g., 8000, 8080).
* Jupyter server should be accessible from the host machine.

Propose other relevant configurations that would enhance the development experience in this devcontainer setup for this workspace.