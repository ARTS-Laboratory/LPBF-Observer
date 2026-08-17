# reconstruct waveform at one point of velocity data

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, filtfilt

# Load the LabVIEW file
filename = r"C:\Users\MADHAMI\Desktop\Vibration Scan B\point-000-000-"

with open(filename, 'r') as file:
    lines = file.readlines()

# Find the header end
for i, line in enumerate(lines):
    if '***End_of_Header***' in line:
        data_start = i + 1
        break

# Read the data
data = []
for line in lines[data_start:]:
    try:
        values = line.strip().split(',')
        if len(values) >= 2:
            data.append([float(values[0]), float(values[2])])
    except ValueError:
        continue

data = pd.DataFrame(data, columns=['Sample', 'Velocity'])

# ---- Signal Parameters ----
fs = 2.5e9  # Sampling frequency (Hz)
cutoff = 2.3e6

time = data['Sample'].values / fs
signal = data['Velocity'].values

# ===============================
# High-Pass Filter Design
# ===============================

nyquist = 0.5 * fs
normal_cutoff = cutoff / nyquist

# 4th order Butterworth high-pass filter
b, a = butter(N=4, Wn=normal_cutoff, btype='high', analog=False)

# Zero-phase filtering (no phase distortion)
filtered_signal = filtfilt(b, a, signal)

# ===============================
# Plot Results
# ===============================

plt.figure(figsize=(12, 6))

plt.subplot(2, 1, 1)
plt.plot(time * 1e6, signal)
plt.title("Original Signal")
plt.ylabel("Amplitude")

plt.subplot(2, 1, 2)
plt.plot(time * 1e6, filtered_signal)
plt.title("High-Pass Filtered Signal (> 2 MHz)")
plt.xlabel("Time (µs)")
plt.ylabel("Amplitude")

plt.tight_layout()
plt.show()
