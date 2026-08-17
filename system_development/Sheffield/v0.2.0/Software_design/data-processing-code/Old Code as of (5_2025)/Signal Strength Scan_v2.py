import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

heatmap_dim = (50, 50)
total_required = heatmap_dim[0] * heatmap_dim[1]

def process_data(folder_path):
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

    # Reshape to 100x100
    heatmap_avg_displacement = np.array(average_displacements).reshape(heatmap_dim)
    return heatmap_avg_displacement

# Process data from both folders
heatmap_a = process_data(r"G:\NIST AM DATA\signal strength data\pulser_on (V)")
heatmap_b = process_data(r"G:\NIST AM DATA\signal strength data\pulser_on (H) 2")

# Create subplots
fig, axes = plt.subplots(2, 1, figsize=(10, 15))
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 25

# veritcal
cax1 = axes[0].imshow(heatmap_a, cmap='viridis', interpolation='nearest', vmin=0, vmax=2)
axes[0].set_xlabel('X-axis\n(a)')
axes[0].set_ylabel('Y-axis')
axes[0].xaxis.set_major_locator(MaxNLocator(nbins=5))
axes[0].yaxis.set_major_locator(MaxNLocator(nbins=5))
fig.colorbar(cax1, ax=axes[0], label='signal strength (V)')

# horizontal
cax2 = axes[1].imshow(heatmap_b, cmap='viridis', interpolation='nearest', vmin=0, vmax=2)
axes[1].set_xlabel('X-axis\n(b)')
axes[1].set_ylabel('Y-axis')
axes[1].xaxis.set_major_locator(MaxNLocator(nbins=5))
axes[1].yaxis.set_major_locator(MaxNLocator(nbins=5))
fig.colorbar(cax2, ax=axes[1], label='signal strength (V)')

# Show the figure
plt.tight_layout()
plt.show()