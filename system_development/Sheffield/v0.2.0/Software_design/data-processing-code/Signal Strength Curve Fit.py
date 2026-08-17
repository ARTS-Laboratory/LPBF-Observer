# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 16:07:11 2025

@author: mumin
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.ndimage import gaussian_filter
from numpy.polynomial.polynomial import Polynomial

# Folder path
folder_path = r"C:\Users\mwhetham\Desktop\signal strength data\LayerScanV6 Experiments\Experiment5"

# Target heatmap dimensions
heatmap_dim = (100,100)
total_required = heatmap_dim[0] * heatmap_dim[1]

average_displacements = []

# Loop through each file in the directory
for file in sorted(os.listdir(folder_path)):  # Sorting ensures consistent ordering
    file_path = os.path.join(folder_path, file)
    
    try:
        # Read the file
        data = pd.read_csv(file_path, skiprows=24, header=None)
        
        displacement = data.values[:, 1]  # Displacement column
        
        # Compute average displacement
        avg_displacement = np.mean(displacement)
        average_displacements.append(avg_displacement)

    except Exception as e:
        print(f"Error processing {file}: {e}")

# Handle cases where we have too many or too few files
if len(average_displacements) < total_required:
    # Pad with NaNs if there are fewer values than needed
    average_displacements += [np.nan] * (total_required - len(average_displacements))
elif len(average_displacements) > total_required:
    # Trim extra values if more than needed
    average_displacements = average_displacements[:total_required]

# Reshape to heatmap grid
heatmap_avg_displacement = np.array(average_displacements).reshape(heatmap_dim)

# Apply Gaussian smoothing
Z_smooth = gaussian_filter(heatmap_avg_displacement, sigma=2)  # Adjust sigma for more/less smoothing

# Generate X, Y meshgrid for 3D plotting
X = np.arange(heatmap_dim[1])
Y = np.arange(heatmap_dim[0])

# Reshape X, Y into 1D arrays
X_flat = X.flatten()
Y_flat = Y.flatten()
Z_flat = Z_smooth.flatten()

# Stack the X and Y arrays
XY = np.vstack([X_flat, Y_flat])

# Fit a 2nd degree polynomial (quadratic)
# This fits Z = a + b*X + c*Y + d*X^2 + e*Y^2 + f*XY
coeffs = np.polyfit(XY.T, Z_flat, deg=2)

# coeffs will now contain the coefficients for the polynomial surface
a, b, c, d, e, f = coeffs

print(f"Fitted coefficients for the polynomial surface:")
print(f"a: {a}")
print(f"b: {b}")
print(f"c: {c}")
print(f"d: {d}")
print(f"e: {e}")
print(f"f: {f}")
