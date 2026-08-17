import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

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
trigger_filename = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\trigger_1-000-000-"
ldv_1 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(90)-000-000-"
ldv_3 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(88)-000-000-"
ldv_5 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(86)-000-000-"
ldv_7 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(84)-000-000-"

# Load data
time_ldv1, signal_ldv1 = load_waveform(ldv_1, fs)
time_ldv3, signal_ldv3 = load_waveform(ldv_3, fs)
time_ldv5, signal_ldv5 = load_waveform(ldv_5, fs)
time_ldv7, signal_ldv7 = load_waveform(ldv_7, fs)


time_trigger, signal_trigger = load_waveform(trigger_filename, fs)

rows = 5

#make figure
plt.figure(figsize=(20, 12))
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 20

# Receiver Output
plt.subplot(rows, 1, 1)
plt.plot(time_trigger * 1e6, signal_trigger, color='m')
plt.ylim(bottom=-1, top=1)
plt.xlabel("Time (μs)\n(a)")
plt.ylabel("Amplitude (V)")
plt.grid()

# LDV 1
plt.subplot(rows, 1, 2)
plt.plot(time_ldv1 * 1e6, signal_ldv1, color='c')
plt.ylim(bottom=-0.35, top=0.35)
plt.xlabel("Time (μs)\n(b)")
plt.ylabel("Amplitude (V)")
plt.grid()

# LDV 3
plt.subplot(rows, 1, 3)
plt.plot(time_ldv3 * 1e6, signal_ldv3, color='c')
plt.ylim(bottom=-0.35, top=0.35)
plt.xlabel("Time (μs)\n(c)")
plt.ylabel("Amplitude (V)")
plt.grid()

# LDV 5
plt.subplot(rows, 1, 4)
plt.plot(time_ldv5 * 1e6, signal_ldv5, color='c')
plt.ylim(bottom=-0.35, top=0.35)
plt.xlabel("Time (μs)\n(d)")
plt.ylabel("Amplitude (V)")
plt.grid()

# LDV 7
plt.subplot(rows, 1, 5)
plt.plot(time_ldv7 * 1e6, signal_ldv7, color='c')
plt.ylim(bottom=-0.35, top=0.35)
plt.xlabel("Time (μs)\n(e)")
plt.ylabel("Amplitude (V)")
plt.grid()

# Adjust layout and show plot
plt.tight_layout()
plt.show()
