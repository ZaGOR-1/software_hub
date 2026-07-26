#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."
exec python -m app.cli create-backup
