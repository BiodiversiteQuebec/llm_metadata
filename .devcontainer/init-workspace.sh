#!/bin/bash
set -euo pipefail

TEMP_CLONE_DIR="/workspace/temp-clone"

promote_temp_clone() {
    if [ ! -d "$TEMP_CLONE_DIR" ]; then
        return
    fi

    shopt -s dotglob nullglob
    for item in "$TEMP_CLONE_DIR"/*; do
        name="$(basename "$item")"

        if [ "$name" = "." ] || [ "$name" = ".." ]; then
            continue
        fi

        if [ "$name" = ".claude" ] && [ -e "/workspace/.claude" ]; then
            continue
        fi

        mv "$item" /workspace/
    done
    shopt -u dotglob nullglob

    rmdir "$TEMP_CLONE_DIR" 2>/dev/null || true
}

# Initialize workspace on first run, and recover gracefully from partial setup
if [ ! -f /workspace/.git/config ]; then
    if [ -f "$TEMP_CLONE_DIR/.git/config" ]; then
        echo "Recovering from partial clone..."
        promote_temp_clone
    else
        echo "First run: cloning repository..."
        rm -rf "$TEMP_CLONE_DIR"
        git clone "${GIT_REPO_URL}" "$TEMP_CLONE_DIR"
        promote_temp_clone
    fi

    if [ ! -f /workspace/.git/config ]; then
        echo "Workspace initialization failed: repository not available at /workspace"
        exit 1
    fi
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
if [ -f /workspace/uv.lock ]; then
    uv sync --frozen
else
    uv sync
fi

echo "Workspace ready!"
