#input: velocity data at a point
#operation: reconstructs waveform and performs FFT
#figure: waveform plot and FFT plot

import numpy as np
import matplotlib.pyplot as plt

def load_lvm_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Find second ***End_of_Header*** line
    header_count = 0
    for i, line in enumerate(lines):
        if '***End_of_Header***' in line:
            header_count += 1
            if header_count == 2:
                data_start = i + 15000
                break

    # Read data (expecting: time, signal1, signal2, comment)
    time = []
    signal = []

    for line in lines[data_start:]:
        parts = line.strip().split(',')
        if len(parts) >= 2:
            try:
                t = float(parts[0])
                s = float(parts[2])  # Use column 3 (index 2)
                time.append(t)
                signal.append(s)
            except ValueError:
                continue

    return np.array(time), np.array(signal)

def plot_lvm_time_series(filepath, fs, t_min=None, t_max=None, title="Time Series", ylabel="Amplitude (V)"):
    time, signal = load_lvm_file(filepath)
    time = time / fs  # Convert X_Value to seconds using sampling rate

    # Apply cutoffs
    mask = np.ones_like(time, dtype=bool)
    if t_min is not None:
        mask &= time >= t_min
    if t_max is not None:
        mask &= time <= t_max

    # Plot
    plt.figure(figsize=(12, 4))
    plt.plot(time[mask], signal[mask], color='blue')
    plt.xlabel("Time (s)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    #plt.show()
    
def plot_lvm_time_series_with_fft(filepath, fs, t_min=None, t_max=None, title="Time and Frequency Domain", ylabel="Amplitude (V)"):
    time, signal = load_lvm_file(filepath)
    time = time / fs

    # Apply time cutoffs
    mask = np.ones_like(time, dtype=bool)
    if t_min is not None:
        mask &= time >= t_min
    if t_max is not None:
        mask &= time <= t_max

    time_filtered = time[mask]
    signal_filtered = signal[mask]

    # Compute FFT in dB
    N = len(signal_filtered)
    fft_vals = np.fft.rfft(signal_filtered)
    fft_freqs = np.fft.rfftfreq(N, d=1/fs)
    fft_magnitude_db = 20 * np.log10(np.abs(fft_vals) + 1e-12)

    # Plot Time and FFT
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Time-domain plot
    ax1.plot(time_filtered, signal_filtered, color='blue')
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel(ylabel)
    ax1.set_title(f"{title} - Time Domain")
    ax1.grid(True)

    # Frequency-domain plot (log-log)
    ax2.plot(fft_freqs, fft_magnitude_db, color='red')
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Magnitude (dB)")
    ax2.set_title(f"{title} - FFT {filename}")
    ax2.set_xscale('log')
    ax2.set_xlim(left=1e3, right=fs/2)  # avoid log(0)
    ax2.grid(True, which='both', linestyle='--')

    plt.tight_layout()
    plt.show()

fs = 2.5e9  # Sampling rate (Hz)
filename = r"C:\Users\mwhetham\Desktop\signal strength data\LayerScanV6 Experiments\Experiment2\point-016-016-"

# Plot with optional time window from 0.5 µs to 1.5 µs
plot_lvm_time_series(filename, fs, t_min=2e-5, t_max=8e-5)
plot_lvm_time_series_with_fft(filename, fs, t_min=6e-5, t_max=8e-5)

