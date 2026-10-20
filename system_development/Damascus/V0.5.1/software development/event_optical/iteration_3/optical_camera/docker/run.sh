#!/usr/bin/env bash
set -euo pipefail
optical_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
image="${OPTICAL_DOCKER_IMAGE:-lpbf-optical:0.2}"
command_name="${1:---list}"
case "$command_name" in
    build)
        shift
        for archive in spinnaker-4.4.0.246-noble-amd64-pkg.tar.gz spinnaker_python-4.4.0.246-cp312-cp312-linux_x86_64.tar.gz; do
            gzip -t "$optical_root/vendor/$archive"
        done
        exec docker buildx build --load --platform linux/amd64 \
            --file "$optical_root/docker/Dockerfile" --tag "$image" "$@" "$optical_root"
        ;;
    --check|--list|single|sequence|serve|test) ;;
    *) echo 'Usage: bash docker/run.sh {build|--check|--list|single|sequence|serve|test} [options]' >&2; exit 2 ;;
esac
if [[ $# -eq 0 ]]; then set -- --list; fi
run_uid="${SUDO_UID:-$(id -u)}"
run_gid="${SUDO_GID:-$(id -g)}"
options=(run --rm --init --stop-timeout 30 --user "$run_uid:$run_gid" --env HOME=/tmp)
case "$command_name" in
    single|sequence|serve)
        if [[ ! -d "$optical_root/data" ]]; then
            mkdir -p "$optical_root/data"
            if [[ -n "${SUDO_UID:-}" ]]; then chown "$run_uid:$run_gid" "$optical_root/data"; fi
        fi
        options+=(--network host
            --mount "type=bind,source=$optical_root/data,target=/data"
            --mount "type=bind,source=$optical_root/config,target=/settings,readonly")
        shift
        set -- "$command_name" --config /settings/camera.toml "$@"
        if [[ "$command_name" == serve ]]; then options+=(-i); fi
        ;;
    --list) options+=(--network host) ;;
esac
exec docker "${options[@]}" "$image" "$@"
