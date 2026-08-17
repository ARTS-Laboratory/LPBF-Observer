#input: file folder, heatmap dimensions
#operation: FFT of velocity data
#output: relative power of the max frequencies
#figure: heatmap of max frequencies

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

directory = r"C:\Users\mwhetham\Desktop\signal strength data\LayerScanV6 Experiments\Experiment2"
print(directory)
fs = 2.5e9  # Sampling frequency in Hz

heatmap = np.full((30,30), np.nan)  # Use NaN for missing data

def load_signal(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Skip header
    for i, line in enumerate(lines):
        if '***End_of_Header***' in line:
            data_start = i + 2
            break

    data = []
    for line in lines[data_start:]:
        try:
            values = line.strip().split(',')
            if len(values) >= 2:
                data.append(float(values[2]))  # signal only
        except ValueError:
            continue

    return np.array(data)

def max_fft_peak(signal):
    fft_vals = np.fft.rfft(signal)
    fft_mag = np.abs(fft_vals)
    return np.max(fft_mag)

# Read files and populate heatmap
for filename in os.listdir(directory):
    if filename.startswith("point-") and filename.endswith("-"):
        parts = filename.split('-')
        try:
            x = int(parts[1])
            y = int(parts[2])
        except ValueError:
            continue

        filepath = os.path.join(directory, filename)
        signal = load_signal(filepath)
        peak = max_fft_peak(signal)
        heatmap[y, x] = peak  # y is row, x is column

# Plot heatmap
plt.figure(figsize=(10, 8))
plt.imshow(heatmap, origin='lower', cmap='hot', aspect='equal')
plt.colorbar(label='Max FFT Magnitude')
#plt.title('FFT_Cube4_Scan V')
plt.xlabel('X Coordinate')
plt.ylabel('Y Coordinate')
plt.tight_layout()
plt.show()
