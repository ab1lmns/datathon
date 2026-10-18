#!/usr/bin/env bash
# Use an existing wheelhouse; this command never contacts package indexes.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo 'Usage: install_offline.sh /path/to/wheels /path/to/new-venv' >&2
  exit 2
fi
wheelhouse=$(cd "$1" && pwd)
target=$2
if [ -e "$target" ]; then
  echo 'Target already exists; choose a new environment.' >&2
  exit 2
fi
script_dir=$(cd "$(dirname "$0")" && pwd)
python3.12 -m venv "$target"
"$target/bin/python" -m pip install --no-index --find-links="$wheelhouse" -r "$script_dir/../requirements-service.txt"
"$target/bin/python" -m pip check
