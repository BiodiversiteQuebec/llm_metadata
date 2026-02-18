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

# Configure git upstream defaults inside the dev container
if git -C /workspace rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git config --global push.autoSetupRemote true

    current_branch="$(git -C /workspace branch --show-current 2>/dev/null || true)"
    if [ -n "$current_branch" ] && ! git -C /workspace rev-parse --abbrev-ref "${current_branch}@{upstream}" >/dev/null 2>&1; then
        if git -C /workspace show-ref --verify --quiet "refs/remotes/origin/${current_branch}"; then
            git -C /workspace branch --set-upstream-to="origin/${current_branch}" "$current_branch" >/dev/null 2>&1 || true
            echo "Set git upstream: ${current_branch} -> origin/${current_branch}"
        elif git -C /workspace show-ref --verify --quiet "refs/remotes/origin/main"; then
            git -C /workspace branch --set-upstream-to="origin/main" "$current_branch" >/dev/null 2>&1 || true
            echo "Set git upstream: ${current_branch} -> origin/main"
        fi
    fi
fi

echo "Syncing dependencies..."
uv sync --frozen

echo "Workspace ready!"
