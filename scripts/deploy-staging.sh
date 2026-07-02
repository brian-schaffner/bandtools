#!/usr/bin/env bash
# Canonical entry point: deploy Band Tools to staging.
exec "$(dirname "$0")/deploy/staging.sh" "$@"
