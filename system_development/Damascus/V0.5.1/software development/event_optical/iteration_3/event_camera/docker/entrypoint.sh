#!/usr/bin/env bash
set -euo pipefail
command_name="${1:-help}"
if [[ $# -gt 0 ]]; then shift; fi
export HOME="${HOME:-/tmp}"

prepare_lucid() {
    if [[ "$(uname -m)" != x86_64 ]]; then
        echo 'This LUCID package requires an x86_64 Linux container.' >&2
        exit 2
    fi
    for directory in lib64 GenICam/library/lib/Linux64_x64 Metavision/lib Metavision/hal_plugin; do
        if [[ ! -d "$ARENA_ROOT/$directory" ]]; then
            echo "Missing Linux Arena SDK directory: $ARENA_ROOT/$directory. Mount ArenaSDK_Linux_x64 at /sdk/arena (read-only)." >&2
            exit 2
        fi
    done
    local plugin="$ARENA_ROOT/Metavision/hal_plugin/liblucid_imx63x_plugin5.so.1.0.10"
    if [[ ! -f "$plugin" ]]; then
        echo "Expected tested LUCID release plugin: $plugin. Other SDK/plugin versions need compatibility validation." >&2
        exit 2
    fi
    local plugin_directory
    plugin_directory="$(mktemp -d /tmp/event-optical-lucid.XXXXXX)"
    ln -s "$plugin" "$plugin_directory/liblucid_imx63x_plugin5.so"
    export MV_HAL_PLUGIN_PATH="$plugin_directory"
    export MV_HAL_PLUGIN_SEARCH_MODE=PLUGIN_PATH_ONLY
    export LD_LIBRARY_PATH="$OPENEB_ROOT/lib:$OPENEB_ROOT/lib64:$ARENA_ROOT/lib64:$ARENA_ROOT/GenICam/library/lib/Linux64_x64:$ARENA_ROOT/Metavision/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    # Initialize GenTL before Python/OpenEB: preserve the validated shutdown fix.
    export LD_PRELOAD="libgentl.so.1${LD_PRELOAD:+:$LD_PRELOAD}"
}

case "$command_name" in
    help|-h|--help)
        cat <<'EOF'
Event Optical (Python 3.12 / patched OpenEB 5.2)
  check                                  Check bindings, paths, and build manifest
  validate [--recording /data/PATH.raw]   Native EVT3 boundary regression
  reconstruct /data/PATH.raw [options]   PNG modes and curated H5
  analyze /data/PATH.raw [--plot]         Offline event-rate CSV/summary
  telemetry-plot /data/PATH.csv          Plot host recording telemetry
  record --list                         List cameras (mounted Linux Arena SDK)
  record --config /settings/recorder.toml --serial ID [--duration 5]
  camera-info --serial ID                Inspect camera controls (same SDK mount)
  ip-config /list                       Arena IP utility (same SDK mount)
  test                                  Unit tests (does not open a camera)
Offline default output directories: /data/reconstructions and /data/analysis.
Camera recording default output: /data/recordings.
EOF
        ;;
    check)
        exec python /app/docker/check_environment.py "$@"
        ;;
    validate)
        exec python /app/scripts/test_evt3_boundary.py "$@"
        ;;
    reconstruct)
        exec python -u -m event_optical.reconstruction --output-root /data/reconstructions "$@"
        ;;
    analyze)
        exec python -u -m event_optical.event_analysis --output-root /data/analysis "$@"
        ;;
    telemetry-plot)
        exec python -u -m event_optical.telemetry_plot "$@"
        ;;
    record)
        prepare_lucid
        exec python -u -m event_optical.recorder "$@"
        ;;
    camera-info)
        prepare_lucid
        exec python -u /app/scripts/inspect_camera_controls.py --output /data/debug/camera-controls.json "$@"
        ;;
    ip-config)
        prepare_lucid
        exec "$ARENA_ROOT/Utilities/IpConfigUtility" "$@"
        ;;
    test)
        exec python -m unittest discover -s /app/tests -p 'test_*.py' -v "$@"
        ;;
    *)
        echo "Unknown command: $command_name. Run the image with 'help'." >&2
        exit 2
        ;;
esac
