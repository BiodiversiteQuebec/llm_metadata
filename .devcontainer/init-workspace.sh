#!/bin/bash
set -e

# Initialize workspace on first run
if [ ! -f /workspace/.git/config ]; then
    echo "First run: cloning repository..."
    git clone "${GIT_REPO_URL}" /workspace/temp-clone
    mv /workspace/temp-clone/* /workspace/temp-clone/.* /workspace/ 2>/dev/null || true
    rm -rf /workspace/temp-clone
fi

# Setup venv and install dependencies
if [ ! -d /workspace/.venv ]; then
    echo "Creating virtual environment..."
    uv venv /workspace/.venv
fi

echo "Syncing dependencies..."
uv sync --frozen

echo "Workspace ready!"
