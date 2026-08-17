import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.fftpack import fft

# Load the LabVIEW file
filename = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment9\point-009-034-"
with open(filename, 'r') as file:
    lines = file.readlines()

# Find the header end
for i, line in enumerate(lines):
    if '***End_of_Header***' in line:
        data_start = i + 2  # Skip the header end line and empty row
        break

# Read the data into a dataframe, skipping bad rows
data = []
for line in lines[data_start:]:
    try:
        values = line.strip().split(',')
        if len(values) >= 2:
            data.append([float(values[0]), float(values[1])])
    except ValueError:
        continue  # Skip non-numeric rows

data = pd.DataFrame(data, columns=['Time', 'Signal'])

time = data['Time'].values  # First column is time
signal = data['Signal'].values  # Second column is the waveform

# Perform FFT
N = len(signal)  # Number of samples
T = (2500000000)  # Sampling interval
freqs = np.fft.fftfreq(N, d=T)
y_fft = fft(signal)
amplitudes = np.abs(y_fft)[:N // 2]  # Take only positive frequencies
freqs = freqs[:N // 2]  # Positive half of the frequency spectrum

# Plot frequency spectrum
plt.figure(figsize=(10, 5))
plt.plot(freqs, amplitudes)
plt.xlabel("Frequency (Hz)")
plt.ylabel("Amplitude")
plt.title("Frequency Spectrum")
plt.grid()
plt.show()

# Extract dominant frequencies
threshold = 0.05 * max(amplitudes)  # Set a threshold
peaks = freqs[amplitudes > threshold]
print("Dominant frequencies:", peaks)
