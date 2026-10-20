import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Times New Roman"

def _read_column(rows, column_name):
    values = []

    for row in rows:
        value = row.get(column_name, "")

        try:
            values.append(float(value))
        except (TypeError, ValueError):
            values.append(math.nan)

    return values


def plot_telemetry(h5_file, output_folder):
    """
    Find the telemetry CSV associated with an HDF5 recording and
    save a diagnostic graph in the reconstruction output folder.
    """
    h5_file = Path(h5_file)
    output_folder = Path(output_folder)

    output_folder.mkdir(parents=True, exist_ok=True)

    telemetry_csv = h5_file.with_name(
        f"{h5_file.stem}_stream_telemetry.csv"
    )

    if not telemetry_csv.exists():
        print(
            "Telemetry CSV not found. Skipping telemetry plot:\n"
            f"{telemetry_csv}\n"
        )
        return None

    with telemetry_csv.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    if not rows:
        print(
            "Telemetry CSV contains no samples. "
            "Skipping telemetry plot.\n"
        )
        return None

    time_s = _read_column(
        rows,
        "elapsed_seconds",
    )

    camera_rate_mevs = [
        value / 1_000_000
        for value in _read_column(
            rows,
            "camera_event_rate_ev_s",
        )
    ]

    recorded_rate_mevs = [
        value / 1_000_000
        for value in _read_column(
            rows,
            "recorded_event_rate_ev_s",
        )
    ]

    link_throughput_gbps = [
        value * 8 / 1_000_000_000
        for value in _read_column(
            rows,
            "link_throughput_B_s",
        )
    ]

    host_payload_gbps = [
        value * 8 / 1_000_000_000
        for value in _read_column(
            rows,
            "host_payload_rate_B_s",
        )
    ]

    incomplete_buffers = _read_column(
        rows,
        "incomplete_buffers",
    )

    get_buffer_errors = _read_column(
        rows,
        "get_buffer_errors",
    )

    figure, axes = plt.subplots(
        3,
        1,
        figsize=(12, 9),
        sharex=True,
    )

    figure.suptitle(
        f"EVS Stream Telemetry\n{h5_file.stem}"
    )

    # Event rates
    axes[0].plot(
        time_s,
        camera_rate_mevs,
        label="camera event rate",
        color="tab:blue",
    )

    axes[0].plot(
        time_s,
        recorded_rate_mevs,
        label="recorded event rate",
        color="tab:green",
    )

    axes[0].set_ylabel("million events/s")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    # Network throughput
    axes[1].plot(
        time_s,
        link_throughput_gbps,
        label="Camera-reported link throughput",
        color="tab:orange",
    )

    axes[1].plot(
        time_s,
        host_payload_gbps,
        label="Recorded XYTP payload throughput",
        color="tab:cyan",
    )

    axes[1].axhline(
        2.5,
        color="tab:red",
        linestyle="--",
        label="2.5 GbE camera-link limit",
    )

    axes[1].set_ylabel("Throughput (Gb/s)")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    # Stream errors
    axes[2].step(
        time_s,
        incomplete_buffers,
        where="post",
        label="incomplete buffers",
        color="tab:purple",
    )

    axes[2].step(
        time_s,
        get_buffer_errors,
        where="post",
        label="get_buffer errors",
        color="tab:red",
    )
    
    axes[2].set_xlabel("elapsed recording time (s)")
    axes[2].set_ylabel("cumulative count")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    figure.tight_layout()

    output_file = output_folder / "stream_telemetry_plot.png"

    figure.savefig(
        output_file,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)

    print(f"Telemetry plot saved to:\n{output_file}\n")

    return output_file