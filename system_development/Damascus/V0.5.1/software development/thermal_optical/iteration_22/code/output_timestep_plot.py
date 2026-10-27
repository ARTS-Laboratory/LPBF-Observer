# -*- coding: utf-8 -*-
"""
Created on Fri Oct 23 11:15:57 2026

@author: MADHAMI
"""

import os
import re
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------------
# USER INPUTS
# -----------------------------------

#folder_path = r"C:\Users\killedar\OneDrive - University of South Carolina\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_20\data\raw\test_6"
folder_path = r"C:\OpticalTestFolder\test_1"

# Number of files to analyze (None = all files)
num_files = None

# -----------------------------------
# READ FILE NAMES
# -----------------------------------

timestamps = []

for filename in os.listdir(folder_path):

    # Match filenames like optical_0000.bin
    match = re.match(r"^optical_(\d+)\.bin$", filename, re.IGNORECASE)

    if match:
        timestamp = int(match.group(1))
        timestamps.append(timestamp)

# Sort timestamps chronologically
timestamps = np.sort(timestamps)

# Limit number of files
if num_files is not None:
    timestamps = timestamps[:num_files]

# -----------------------------------
# CALCULATE TIME STEPS
# -----------------------------------

# Difference between consecutive timestamps (ms)
dt = np.diff(timestamps)

# Image number (starting at image 2)
image_number = np.arange(2, len(timestamps) + 1)

# -----------------------------------
# STATISTICS
# -----------------------------------

if len(dt) == 0:
    raise ValueError("At least two matching image files are required.")

print(f"Number of images analyzed: {len(timestamps)}")
print(f"Average time step: {np.mean(dt):.3f} ms")
print(f"Minimum time step: {np.min(dt):.3f} ms")
print(f"Maximum time step: {np.max(dt):.3f} ms")
print(f"Standard deviation: {np.std(dt):.3f} ms")

# -----------------------------------
# PLOT TIME STEP FLUCTUATIONS
# -----------------------------------

plt.figure(figsize=(12, 5))

plt.plot(image_number, dt, '-o',
         markersize=3,
         linewidth=1,
         color='blue',
         label='Actual Time Step')

plt.axhline(np.mean(dt),
            color='red',
            linestyle='--',
            linewidth=1.5,
            label=f'Average = {np.mean(dt):.2f} ms')

plt.xlabel("Image Number")
plt.ylabel("Time Step (ms)")
plt.title("Optical Camera Acquisition Time Step Fluctuations")

plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()