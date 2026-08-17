import numpy as np
from scipy.stats import skew
import pandas as pd
import os

# File paths
file_paths = [
 #   r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\trigger-000-000-"
    r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\ldv_1-000-000-",
    r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\ldv_3-000-000-",
    r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\ldv_5-000-000-",
    r"C:\Users\mwhetham\Desktop\Trigger (pulser) and Wave Signal (LDV) read from PXI\ldv_7-000-000-"
]

labels = [ "b", "c", "d", "e"]

# Collect stats
results = []

for label, path in zip(labels, file_paths):
    try:
        
        """
        full_data = np.loadtxt(path, delimiter=',', skiprows=22)
        data_column = full_data[:, 1]  # Only use second column
        abs_max = np.max(np.abs(data_column))
        mean_val = np.mean(data_column)
        skew_val = skew(data_column)
        results.append([label, abs_max, mean_val, skew_val])
        """
        full_data = np.loadtxt(path, delimiter=',', skiprows=22)
        filtered = full_data[(full_data[:, 0] >= 25000) & (full_data[:, 0] <= 100000)]
        data_column = filtered[:, 1]  # Use second column from filtered rows
        abs_max = np.max(np.abs(data_column))
        mean_val = np.mean(data_column)
        skew_val = skew(data_column)
        results.append([label, abs_max, mean_val, skew_val])
       # """
    except Exception as e:
        print(f"Error reading {path}: {e}")
        results.append([label, np.nan, np.nan, np.nan])

# Display in table
df = pd.DataFrame(results, columns=["Label", "Absolute Max", "Mean", "Skew"])
print(df.to_string(index=False))
