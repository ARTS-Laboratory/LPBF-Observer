# -*- coding: utf-8 -*-
"""
Created on Wed Apr 23 10:23:00 2025

@author: MWHETHAM
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
#from mpl_toolkits.mplot3d import Axes3D
from scipy.optimize import curve_fit
#from scipy.ndimage import gaussian_filter

# Folder path
#folder_path = r"G:\Measurement24"
#folder_path = r"F:\NIST AM DATA\signal strength data\pulser_off (H) 2"

# Base directory containing all Meas folders
base_dir = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment4(NEW)"
folder_names = [f"Meas({i:02}of12)" for i in range(1, 3)]

heatmap_dim = (100, 100)
total_required = heatmap_dim[0] * heatmap_dim[1]

# This will store the sum of displacements
accumulated_displacements = np.zeros(total_required)
# Track how many valid (non-NaN) contributions per index
counts = np.zeros(total_required)

for folder_name in folder_names:
    print('starting next folder')
    folder_path = os.path.join(base_dir, folder_name)
    if not os.path.isdir(folder_path):
        print(f"Skipping missing folder: {folder_path}")
        continue

    displacements = []

    for file in sorted(os.listdir(folder_path)):
        file_path = os.path.join(folder_path, file)
        try:
            data = pd.read_csv(file_path, skiprows=24, header=None)
            displacement = data.values[:, 1]
            avg_disp = np.mean(displacement)
            displacements.append(avg_disp)
        except Exception as e:
            print(f"Error in {file_path}: {e}")
            displacements.append(np.nan)

    # Pad or trim to target size
    if len(displacements) < total_required:
        displacements += [np.nan] * (total_required - len(displacements))
    elif len(displacements) > total_required:
        displacements = displacements[:total_required]

    displacements = np.array(displacements)
    mask = ~np.isnan(displacements)

    # Accumulate only valid values
    accumulated_displacements[mask] += displacements[mask]
    counts[mask] += 1

# Final average (avoiding divide-by-zero)
with np.errstate(invalid='ignore'):
        average_displacements = accumulated_displacements / counts

# Reshape to heatmap format
average_heatmap = average_displacements.reshape(heatmap_dim)
print("Final averaged displacement heatmap shape:", average_heatmap.shape)


# Reshape to 86x100 grid
heatmap_avg_displacement = np.array(average_displacements).reshape(heatmap_dim)

# Apply Gaussian smoothing
#Z_smooth = gaussian_filter(heatmap_avg_displacement, sigma=2)

# Generate X, Y meshgrid for 3D plotting
X = np.arange(heatmap_dim[1])
Y = np.arange(heatmap_dim[0])
X, Y = np.meshgrid(X, Y)
Z = heatmap_avg_displacement  # The average displacement values

# Flatten the arrays to 1D for polynomial fitting
X_flat = X.flatten()
Y_flat = Y.flatten()
Z_flat = Z.flatten()

# Filter out NaN values
mask = ~np.isnan(Z_flat)  # Create a mask where Z_flat is not NaN
X_flat_valid = X_flat[mask]
Y_flat_valid = Y_flat[mask]
Z_flat_valid = Z_flat[mask]

# Define a 2D polynomial function for fitting
def poly_2d(x, y, a, b, c, d, e, f):
    return a * x**2 + b * y**2 + c * x * y + d * x + e * y + f

# Fit the polynomial to the data
popt, _ = curve_fit(lambda xy, a, b, c, d, e, f: poly_2d(xy[0], xy[1], a, b, c, d, e, f),
                    (X_flat_valid, Y_flat_valid), Z_flat_valid)

# Create a grid of fitted Z values
Z_fit = poly_2d(X, Y, *popt)

'''
#heatmap
plt.figure(figsize=(10, 8))
plt.imshow(heatmap_avg_displacement, cmap='viridis', interpolation='nearest', vmin=0, vmax=2)
plt.colorbar(label='Average Displacement')
plt.title('100x100 Signal Strength Heatmap with Pulser Off')
plt.xlabel('X')
plt.ylabel('Y')
plt.show()
'''

# Plot 3D Surface
fig = plt.figure(figsize=(12, 8))
plt.rcParams['font.size'] = 15
ax = fig.add_subplot(111, projection='3d')

# Original surface plot
###surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='k', alpha=0.5)
scatter = ax.scatter(X_flat_valid, Y_flat_valid, Z_flat_valid, c=Z_flat_valid, cmap='viridis', s=10)

# Fitted polynomial surface plot
Z_fit_flat = poly_2d(X_flat_valid, Y_flat_valid, *popt)
###ax.plot_surface(X, Y, Z_fit, color='r', alpha=0.5, edgecolor='k')

# Labels and title
ax.set_xlabel('X Index')
ax.set_ylabel('Y Index')
ax.set_zlabel('Signal Strength')
#ax.set_title('3D Surface Plot with Polynomial Fit')

# Color bar
###fig.colorbar(surf, shrink=0.5, aspect=5)
ax.scatter(X_flat_valid, Y_flat_valid, Z_fit_flat, color='r', s=2, alpha=0.5)

# Show plot
plt.show()
