#FFT on log scale of velocity data at a point

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq

# --- User Settings ---
CSV_FILE = r"C:\Users\mwhetham\Desktop\signal strength data\Cube4 Scan_V\point-099-099-"
SAMPLING_RATE = 2500000000  # Hz, change this to your desired sampling rate
X_AXIS_SCALE = 'log'  # Options: 'linear', 'log'
X_MIN = None # Set to a number or None
X_MAX = None 
Y_MIN = None
Y_MAX = None

# --- Load Data ---
data = pd.read_csv(CSV_FILE, skiprows=24, header=None)
y = data.iloc[:, 1].values  #use signal data
n = len(y)

# --- FFT Computation ---
y_fft = fft(y)
frequencies = fftfreq(n, d=1/SAMPLING_RATE)

# Only take the positive half
mask = frequencies > 0
frequencies = frequencies[mask]
amplitude = np.abs(y_fft[mask]) * 2 / n

# --- Plot Results ---
plt.figure()
if X_AXIS_SCALE == 'log':
    plt.semilogx(frequencies, amplitude)
else:
    plt.plot(frequencies, amplitude)

plt.xlabel('Frequency (Hz)')
plt.ylabel('Amplitude')
plt.title('point (99,99)')
plt.grid(True, which='both')

if X_MIN is not None or X_MAX is not None:
    plt.xlim(left=X_MIN, right=X_MAX)
if Y_MIN is not None or Y_MAX is not None:
    plt.ylim(bottom=Y_MIN, top=Y_MAX)

plt.show()