#!/usr/bin/env bash
set -euo pipefail
case "${1:---list}" in
    --check|--list) exec python /app/discover.py "$@" ;;
    single|sequence|serve) exec python /app/capture.py "$@" ;;
    test) exec python -m unittest discover -s /app/tests -v ;;
    *) echo 'Commands: --check, --list, single, sequence, serve, test' >&2; exit 2 ;;
esac
