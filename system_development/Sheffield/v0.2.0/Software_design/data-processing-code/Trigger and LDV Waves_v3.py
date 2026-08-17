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
ldv_1 = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment9\point-009-034-"
#ldv_3 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(88)-000-000-"
#ldv_5 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(86)-000-000-"
#ldv_7 = r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\Wave signals (NEW)\ldv(84)-000-000-"

# Load data
time_ldv1, signal_ldv1 = load_waveform(ldv_1, fs)
#time_ldv3, signal_ldv3 = load_waveform(ldv_3, fs)
#time_ldv5, signal_ldv5 = load_waveform(ldv_5, fs)
#time_ldv7, signal_ldv7 = load_waveform(ldv_7, fs)

time_trigger, signal_trigger = load_waveform(trigger_filename, fs)

rows = 5

# Primary axis for LDV signals
fig, ax1 = plt.subplots(figsize=(20, 6))
ax1.plot(time_ldv1 * 1e6, signal_ldv1, label='LDV 1 (90°)', color='c')
#ax1.plot(time_ldv3 * 1e6, signal_ldv3, label='LDV 3 (88°)', color='b')
#ax1.plot(time_ldv5 * 1e6, signal_ldv5, label='LDV 5 (86°)', color='g')
#ax1.plot(time_ldv7 * 1e6, signal_ldv7, label='LDV 7 (84°)', color='r')
ax1.set_ylabel("LDV Amplitude (V)")
ax1.set_ylim(-0.4, 0.4)
ax1.grid(True)
ax1.legend(loc='upper left')

# Secondary axis for trigger signal
ax2 = ax1.twinx()
ax2.plot(time_trigger * 1e6, signal_trigger, label='Trigger', color='m', linestyle='--')
ax2.set_ylabel("Trigger Amplitude (V)")
ax2.set_ylim(-1, 1)
ax2.legend(loc='upper right')

# Common x-axis
ax1.set_xlabel("Time (μs)")

plt.title("Receiver Output vs LDV Data at Different")
plt.tight_layout()
plt.show()