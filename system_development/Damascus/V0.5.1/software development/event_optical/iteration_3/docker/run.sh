#!/usr/bin/env bash
# Linux convenience wrapper: resolve project paths and quote bind mounts with spaces.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
image="${EVENT_DOCKER_IMAGE:-lpbf-event-optical:0.1}"
command_name="${1:-help}"
if [[ "$command_name" == build ]]; then
    shift
    exec docker buildx build --load --platform linux/amd64 \
        --file "$project_root/docker/Dockerfile" --tag "$image" "$@" "$project_root"
fi
if [[ $# -eq 0 ]]; then set -- help; fi
# Preserve the invoking user's file ownership and SDK location under sudo.
invoking_uid="${SUDO_UID:-$(id -u)}"
invoking_gid="${SUDO_GID:-$(id -g)}"
invoking_home="$HOME"
if [[ -n "${SUDO_UID:-}" ]]; then
    invoking_home="$(getent passwd "$invoking_uid" | cut -d: -f6)"
    if [[ -z "$invoking_home" ]]; then
        echo "Cannot resolve home directory for UID $invoking_uid; pass ARENA_ROOT explicitly." >&2
        exit 2
    fi
fi
data_root="${EVENT_DATA_DIR:-$project_root/data}"
settings_root="${EVENT_CONFIG_DIR:-$project_root/config}"
if [[ ! -d "$data_root" ]]; then
    mkdir -p "$data_root"
    if [[ -n "${SUDO_UID:-}" ]]; then
        chown "$invoking_uid:$invoking_gid" "$data_root"
    fi
fi
data_root="$(cd -- "$data_root" && pwd)"
settings_root="$(cd -- "$settings_root" && pwd)"
options=(run --rm --init --stop-timeout 30 --user "$invoking_uid:$invoking_gid" --env HOME=/tmp
    --mount "type=bind,source=$data_root,target=/data"
    --mount "type=bind,source=$settings_root,target=/settings,readonly")
case "$command_name" in
    record|camera-info|ip-config)
        arena_root="${ARENA_ROOT:-$invoking_home/opt/arena/ArenaSDK_Linux_x64}"
        if [[ ! -d "$arena_root" ]]; then
            echo "Linux Arena SDK not found: $arena_root. Set ARENA_ROOT to the extracted SDK directory." >&2
            exit 2
        fi
        arena_root="$(cd -- "$arena_root" && pwd)"
        options+=(--network host --mount "type=bind,source=$arena_root,target=/sdk/arena,readonly")
        ;;
esac
exec docker "${options[@]}" "$image" "$@"
