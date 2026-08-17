# -*- coding: utf-8 -*-
"""
Created on Sun Mar  9 17:19:07 2025

@author: MWHETHAM
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.ndimage import gaussian_filter

# Folder path
folder_path = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment4(NEW)\Meas(12of12)"

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
X, Y = np.meshgrid(X, Y)

# Plot Smoothed 3D Surface
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')
surf = ax.plot_surface(X, Y, Z_smooth, cmap='viridis', edgecolor='none')

# Labels and title
ax.set_xlabel('X-axis')
ax.set_ylabel('Y-axis')
ax.set_zlabel('average displacement (V)')

# Color bar
fig.colorbar(surf, shrink=1, aspect=5)

# Show plot
plt.show()

