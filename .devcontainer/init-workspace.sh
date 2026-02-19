#!/bin/bash
set -euo pipefail

default_branch="${GIT_DEFAULT_BRANCH:-main}"

# Initialize workspace on first run in-place (works even if /workspace is not empty)
if [ ! -f /workspace/.git/config ]; then
    echo "First run: initializing repository in /workspace..."
    git -C /workspace init

    if git -C /workspace remote get-url origin >/dev/null 2>&1; then
        git -C /workspace remote set-url origin "${GIT_REPO_URL}"
    else
        git -C /workspace remote add origin "${GIT_REPO_URL}"
    fi

    git -C /workspace fetch --prune origin

    if ! git -C /workspace show-ref --verify --quiet "refs/remotes/origin/${default_branch}"; then
        if git -C /workspace show-ref --verify --quiet "refs/remotes/origin/master"; then
            default_branch="master"
        else
            echo "Workspace initialization failed: remote branch origin/${default_branch} not found"
            exit 1
        fi
    fi

    git -C /workspace checkout -B "$default_branch"
    git -C /workspace reset --hard "origin/${default_branch}"
    git -C /workspace clean -fd -e .claude/

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
        elif git -C /workspace show-ref --verify --quiet "refs/remotes/origin/${default_branch}"; then
            git -C /workspace branch --set-upstream-to="origin/${default_branch}" "$current_branch" >/dev/null 2>&1 || true
            echo "Set git upstream: ${current_branch} -> origin/${default_branch}"
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
