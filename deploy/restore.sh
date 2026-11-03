#!/usr/bin/env bash
# Restores /data from Object Storage. Usage: ./restore.sh [finchart-YYYYMMDD-HHMMSS.tar.gz|latest]
set -euo pipefail
cd "$(dirname "$0")"

docker compose run --rm backup python -m finchart_api.backup list
read -r -p "Restore '${1:-latest}' and replace current data? [y/N] " answer
[[ "$answer" == "y" ]] || exit 1

docker compose stop app
docker compose run --rm backup python -m finchart_api.backup restore "${1:-latest}"
docker compose start app
