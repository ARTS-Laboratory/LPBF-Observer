# signal strength 3D scatter from data folder
# saves HTML file of 3D plot

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import plotly.graph_objects as go
import plotly.io as pio
import time

start_time = time.time()

folder_path = r"C:\Users\MADHAMI\Desktop\Signal Scan 2"
print(folder_path)

heatmap_dim = (25,25)
total_required = heatmap_dim[0] * heatmap_dim[1]

average_displacements = []

# Loop through each file in the directory
for file in sorted(os.listdir(folder_path)):  # Sorting ensures consistent ordering
    file_path = os.path.join(folder_path, file)
    
    try:
        # Read the file
        data = pd.read_csv(file_path, skiprows=24, header=None)
        
        displacement = data.values[:, 2]  # Displacement column
        
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

# Reshape to given grid
heatmap_avg_displacement = np.array(average_displacements).reshape(heatmap_dim)

# Apply Gaussian smoothing
Z_smooth = gaussian_filter(heatmap_avg_displacement, sigma=2)

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


#%% generate figure

fig = plt.figure(figsize=(18, 12))
plt.rcParams['font.size'] = 15

# First subplot: original scatter
ax1 = fig.add_subplot(1, 2, 1, projection='3d')
scatter = ax1.scatter(X_flat_valid, Y_flat_valid, Z_flat_valid, c=Z_flat_valid, cmap='viridis', s=10)
ax1.set_xlabel('X Index')
ax1.set_ylabel('Y Index')
ax1.set_zlabel('Signal Strength')
#ax1.set_title('Original Scatter')
#ax1.text2D(0.5, -0.15, '(a)', transform=ax1.transAxes, ha='center')
fig.colorbar(scatter, ax=ax1, shrink=0.3, aspect=10)

# Show plot
plt.tight_layout()
plt.show()

#%% save as HTML

fig_a = go.Figure()

fig_a.add_trace(go.Scatter3d(
    x=X_flat_valid,
    y=Y_flat_valid,
    z=Z_flat_valid,
    mode='markers',
    marker=dict(size=3, color=Z_flat_valid, colorscale='Viridis', colorbar=dict(title='Signal')),
    name='Original Scatter'
))

fig_a.update_layout(
    scene=dict(
        xaxis_title='X Index',
        yaxis_title='Y Index',
        zaxis_title='Signal Strength'
    ),
    margin=dict(l=0, r=0, b=0, t=40),
    title='Scatter'
)

# Export to HTML
pio.write_html(fig_a, file='HTMLs/Signal Scan 2.html', auto_open=True)

#%%
end_time = time.time()
print(f"\nRuntime: {end_time - start_time:.3f} seconds")

