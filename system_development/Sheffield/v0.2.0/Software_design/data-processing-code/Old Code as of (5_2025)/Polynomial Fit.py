import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.optimize import curve_fit
from scipy.ndimage import gaussian_filter

# Folder path
#folder_path = r"G:\Measurement24"
#folder_path = r"F:\NIST AM DATA\signal strength data\pulser_off (H) 2"
folder_path = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment6"

# Target heatmap dimensions
#heatmap_dim = (86, 100)
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

# Reshape to 86x100 grid
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

# Define a 2D polynomial function for fitting
def poly_2d(x, y, a, b, c, d, e, f):
    return a * x**2 + b * y**2 + c * x * y + d * x + e * y + f

# Fit the polynomial to the data
popt, _ = curve_fit(lambda xy, a, b, c, d, e, f: poly_2d(xy[0], xy[1], a, b, c, d, e, f),
                    (X_flat_valid, Y_flat_valid), Z_flat_valid)

# Create a grid of fitted Z values
Z_fit = poly_2d(X, Y, *popt)

# Plot 3D Surface
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')

# Original surface plot
surf = ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='k', alpha=0.5)

# Fitted polynomial surface plot
ax.plot_surface(X, Y, Z_fit, color='r', alpha=0.5, edgecolor='k')

# Labels and title
ax.set_xlabel('X Index')
ax.set_ylabel('Y Index')
ax.set_zlabel('Average Displacement')
ax.set_title('3D Surface Plot with Polynomial Fit')

# Color bar
fig.colorbar(surf, shrink=0.5, aspect=5)

# Show plot
plt.show()
