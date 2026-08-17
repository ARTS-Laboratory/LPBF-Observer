import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# Load and process data
def load_waveform(filename, fs):
    with open(filename, 'r') as file:
        lines = file.readlines()

    # Find the header end
    for i, line in enumerate(lines):
        if '***End_of_Header***' in line:
            data_start = i + 2  # Skip the header end line and empty row
            break

    # Read the data into a dataframe
    data = []
    for line in lines[data_start:]:
        try:
            values = line.strip().split(',')
            if len(values) >= 2:
                data.append([float(values[0]), float(values[1])])
        except ValueError:
            continue  # Skip non-numeric rows

    data = pd.DataFrame(data, columns=['Time', 'Signal'])

    time = data['Time'].values / fs  # Adjust time scale
    signal = data['Signal'].values

    return time, signal


fs = 2500000000  # Sampling frequency (Hz)

# file names
ldv_filename = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment9\point-009-034-"
trigger_filename = r"C:\Users\mwhetham\Desktop\signal strength data\wfms\point-000-000-"

# Load data
time_ldv, signal_ldv = load_waveform(ldv_filename, fs)
time_trigger, signal_trigger = load_waveform(trigger_filename, fs)

#make figure
plt.figure(figsize=(10, 10))
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 25

# Receiver Output
plt.subplot(2, 1, 1)
plt.plot(time_trigger * 1e6, signal_trigger, color='m')
plt.xlabel("time (μs)\n(a)")
plt.ylabel("pulse amplitude (V)")
plt.gca().yaxis.set_major_locator(MaxNLocator(nbins=4))
plt.grid()

# LDV velocity
plt.subplot(2, 1, 2)
plt.plot(time_ldv * 1e6, signal_ldv, color='c')
plt.xlabel("time (μs)\n(b)")
plt.ylabel("pulse amplitude (V)")
plt.gca().yaxis.set_major_locator(MaxNLocator(nbins=3))
plt.grid()

# Adjust layout and show plot
plt.tight_layout()
plt.show()
