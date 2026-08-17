# -*- coding: utf-8 -*-
"""
Created on Mon Feb 24 18:51:47 2025

@author: MWHETHAM
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Folder path
folder_path =r"G:\Measurement24"

# Target heatmap dimensions
heatmap_dim = (86,100)
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

# Reshape to 50x50 grid
heatmap_avg_displacement = np.array(average_displacements).reshape(heatmap_dim)

# Generate X, Y meshgrid for 3D plotting
X = np.arange(heatmap_dim[1])
Y = np.arange(heatmap_dim[0])
X, Y = np.meshgrid(X, Y)
Z = heatmap_avg_displacement  # The average displacement values

# Plot 3D Surface
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')
surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='k')

# Labels and title
ax.set_xlabel('X Index')
ax.set_ylabel('Y Index')
ax.set_zlabel('Average Displacement')
ax.set_title('3D Surface Plot of Signal Return Strength')

# Color bar
fig.colorbar(surf, shrink=0.5, aspect=5)

# Show plot
plt.show()
