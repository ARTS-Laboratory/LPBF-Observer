# signal strength 3D scatter and 3D polynomial fit
# saves HTML files of interactive plots

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.optimize import curve_fit
from scipy.ndimage import gaussian_filter
import plotly.graph_objects as go
import plotly.io as pio
import timeit

start = timeit.timeit()*1000

folder_path = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment Steel Sheet 2"
print(folder_path)

heatmap_dim = (40,40)
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

#%%

fig = plt.figure(figsize=(20, 12))
plt.rcParams['font.size'] = 15

# First subplot: original scatter
ax1 = fig.add_subplot(1, 2, 1, projection='3d')
scatter = ax1.scatter(X_flat_valid, Y_flat_valid, Z_flat_valid, c=Z_flat_valid, cmap='viridis', s=10)
ax1.set_xlabel('X Index')
ax1.set_ylabel('Y Index')
ax1.set_zlabel('Signal Strength')
#ax1.set_title('Original Scatter')
ax1.text2D(0.5, -0.15, '(a)', transform=ax1.transAxes, ha='center')
fig.colorbar(scatter, ax=ax1, shrink=0.5, aspect=10)

# Second subplot: polynomial fit
ax2 = fig.add_subplot(1, 2, 2, projection='3d')
Z_fit_flat = poly_2d(X_flat_valid, Y_flat_valid, *popt)
scatter_fit = ax2.scatter(X_flat_valid, Y_flat_valid, Z_fit_flat, color='r', s=2, alpha=0.5)
ax2.set_xlabel('X Index')
ax2.set_ylabel('Y Index')
#ax2.set_zlabel('Signal Strength')
#ax2.set_title('Polynomial Fit')
ax2.text2D(0.5, -0.02, '(b)', transform=ax2.transAxes, ha='center')

# Show plot
plt.tight_layout()
plt.show()

#%%

fig_a = go.Figure()
fig_b = go.Figure()

fig_a.add_trace(go.Scatter3d(
    x=X_flat_valid,
    y=Y_flat_valid,
    z=Z_flat_valid,
    mode='markers',
    marker=dict(size=3, color=Z_flat_valid, colorscale='Viridis', colorbar=dict(title='Signal')),
    name='Original Scatter'
))

# Second subplot: polynomial fit
Z_fit_flat = poly_2d(X_flat_valid, Y_flat_valid, *popt)
fig_b.add_trace(go.Scatter3d(
    x=X_flat_valid,
    y=Y_flat_valid,
    z=Z_fit_flat,
    mode='markers',
    marker=dict(size=2, color='red', opacity=0.5),
    name='Polynomial Fit'
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

fig_b.update_layout(
    scene=dict(
        xaxis_title='X Index',
        yaxis_title='Y Index',
        zaxis_title='Signal Strength'
    ),
    margin=dict(l=0, r=0, b=0, t=40),
    title='PolyFit'
)

# Export to HTML
pio.write_html(fig_a, file='HTMLs/Scatter_SteelSheet2.html', auto_open=True)
pio.write_html(fig_b, file='HTMLs/PolyFit_Steet Sheet2.html', auto_open=True)

#%%
end = timeit.timeit()*1000
print('Runtime =', end - start)

