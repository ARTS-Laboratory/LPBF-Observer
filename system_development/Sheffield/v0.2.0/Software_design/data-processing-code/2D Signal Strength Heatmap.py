# signal strength 2D heatmap

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import time

start_time = time.time()
#%%
# Folder containing CSV files
folder_path = r"C:\Users\MADHAMI\Desktop\Signal Scan 2"
print("Reading files from:", folder_path)

heatmap_dim = (25, 25)
total_required = heatmap_dim[0] * heatmap_dim[1]

average_displacements = []

# ---- Read and Process Files ----
for file in sorted(os.listdir(folder_path)):
    file_path = os.path.join(folder_path, file)
    
    try:
        data = pd.read_csv(file_path, skiprows=22, header=None)
        displacement = data.values[:, 2]
        avg_displacement = np.mean(displacement)
        average_displacements.append(avg_displacement)

    except Exception as e:
        print(f"Error processing {file}: {e}")

# ---- Adjust Data Length ----
if len(average_displacements) < total_required:
    average_displacements += [np.nan] * (total_required - len(average_displacements))
elif len(average_displacements) > total_required:
    average_displacements = average_displacements[:total_required]

# ---- Reshape to Grid ----
heatmap_data = np.array(average_displacements).reshape(heatmap_dim)

#%% Generate Figure

plt.figure(figsize=(14, 6))
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 18
plt.imshow(heatmap_data, cmap='viridis', origin='lower')
#plt.title("Reflective Tape Scan")
plt.xlabel("X Index")
plt.ylabel("Y Index")
plt.colorbar(label="Signal Strength")

plt.tight_layout()
plt.show()

end_time = time.time()
print(f"\nRuntime: {end_time - start_time:.3f} seconds")

