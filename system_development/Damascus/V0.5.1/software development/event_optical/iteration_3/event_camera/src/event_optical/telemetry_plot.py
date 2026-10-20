"""Plot recorder telemetry offline; never imports HAL or opens a camera."""
import argparse
import csv
import math
from pathlib import Path


def plot(path, output=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path = Path(path)
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError('Telemetry file has no samples')
    def column(key, scale=1):
        return [float(row[key]) * scale if row.get(key) else math.nan for row in rows]
    x = column('elapsed_seconds')
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    axes[0].plot(x, column('payload_rate_B_s', 1/2**20), label='Consumed RAW payload')
    axes[0].set_ylabel('MiB/s')
    axes[1].plot(x, column('decoded_cd_event_rate_ev_s', 1e-6), label='Decoded CD events (optional)')
    axes[1].set_ylabel('Million events/s')
    for key in ('nic_rx_errors_delta', 'nic_rx_dropped_delta', 'host_udp_rcvbuf_errors_delta'):
        axes[2].step(x, column(key), where='post', label=key)
    axes[2].set_ylabel('Change since start')
    axes[2].set_xlabel('Elapsed host time (s)')
    for axis in axes:
        axis.grid(alpha=.3)
        axis.legend()
    fig.suptitle(path.parent.name)
    fig.tight_layout()
    output = Path(output) if output else path.with_name('stream_telemetry_plot.png')
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(plot(args.csv, args.output))


if __name__ == '__main__': main()
