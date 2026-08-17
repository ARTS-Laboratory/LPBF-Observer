import os
import numpy as np
import pandas as pd
import re
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
import seaborn as sns
import time

start_time = time.time()

folder_path = r"C:\Users\MADHAMI\Desktop\Signal Scan 2"

# ---- DEFINE WELD SQUARES (ADJUST IF NEEDED) ----
weld_ranges = [
    (6, 11, 6, 11),     # top-left
    (13, 18, 6, 11),    # top-right
    (6, 11, 13, 18),    # bottom-left
    (13, 18, 13, 18)    # bottom-right
]

def is_weld(x, y):
    for x1, x2, y1, y2 in weld_ranges:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return True
    return False

weld_signals = []
machine_signals = []
point_series = {}

for filename in os.listdir(folder_path):
    match = re.search(r'point-(\d+)-(\d+)', filename)
    if match:
        x = int(match.group(1))
        y = int(match.group(2))

        file_path = os.path.join(folder_path, filename)
        data = pd.read_csv(file_path, skiprows=22)
        signal = data.iloc[:, 2].values

        # Store every point
        point_series[filename] = signal

        if is_weld(x, y):
            weld_signals.append(signal)
        else:
            machine_signals.append(signal)

print("Weld points:", len(weld_signals))
print("Machine points:", len(machine_signals))

# Safety check
if len(weld_signals) == 0 or len(machine_signals) == 0:
    raise ValueError("Check weld_ranges — no points detected.")

# Trim all signals to same length
min_length_all = min(len(s) for s in point_series.values())

for key in point_series:
    point_series[key] = point_series[key][:min_length_all]

weld_signals = [s[:min_length_all] for s in weld_signals]
machine_signals = [s[:min_length_all] for s in machine_signals]

# Convert to arrays
weld_array = np.array(weld_signals)
machine_array = np.array(machine_signals)

# Mean signals
mean_weld = np.mean(weld_array, axis=0)
mean_machine = np.mean(machine_array, axis=0)

# Pearson correlation
corr, pval = pearsonr(mean_weld, mean_machine)

print("\nMean Weld vs Mean Machine Correlation:", corr)
print("P-value:", pval)

end_time = time.time()
print(f"\nRuntime: {end_time - start_time:.3f} seconds")

#%%
df = pd.DataFrame(point_series)
correlation_matrix = df.corr(method='pearson')

plt.figure(figsize=(10, 8))

plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 12

sns.heatmap(
    correlation_matrix,
    cmap='viridis',
    vmin=-1,
    vmax=1,
    square=True,
    cbar_kws={'label': 'Pearson Correlation Coefficient'}
)

plt.title("Pearson Correlation Coefficient Matrix")
plt.tight_layout()
plt.show()
