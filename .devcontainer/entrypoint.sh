#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CMD=("sleep" "infinity")

if [ "$#" -eq 0 ]; then
  set -- "${DEFAULT_CMD[@]}"
fi

if [ "$(id -u)" -eq 0 ]; then
  if [ -x "/usr/local/bin/init-firewall.sh" ]; then
    /usr/local/bin/init-firewall.sh
  fi

  target_user="${DEVCONTAINER_USER:-dev}"
  if id "$target_user" >/dev/null 2>&1; then
    if command -v gosu >/dev/null 2>&1; then
      exec gosu "$target_user" "$@"
    fi
  fi
fi

exec "$@"
