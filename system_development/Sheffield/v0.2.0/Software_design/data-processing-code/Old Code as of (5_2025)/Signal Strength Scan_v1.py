import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Folder path

folder_path = r"C:\Users\mwhetham\Desktop\signal strength data\LayerScanV6 Experiments\Experiment7Cube"
# Target heatmap dimensions
heatmap_dim = (120,120)


total_required = heatmap_dim[0] * heatmap_dim[1]

average_displacements = []

# Loop through each file in the directory
i = 0
for file in sorted(os.listdir(folder_path)):  # Sorting ensures consistent ordering
    file_path = os.path.join(folder_path, file)
    
    try:
        # Read the file
        data = pd.read_csv(file_path, skiprows=24, header=None)
        
        displacement = data.values[:, 1]  # Displacement column
        
        # Compute average displacement
        avg_displacement = np.mean(displacement)
        if  avg_displacement >= 1.8:
            velocity = data.values[:, 2]
            time= data.values[:,0]
            #plt.figure(figsize=(10, 5))
           # plt.plot(time, velocity, label="Waveform")
            #plt.xlabel("Time (μs)")
           # plt.ylabel("Amplitude")
            #plt.title("Wave")
           # plt.legend()
           # plt.grid()
            #plt.show()
            print('this one')
        #else:
            #avg_displacement = 0 
        average_displacements.append(avg_displacement)
        print (i)
        i = i + 1

    except Exception as e:
        print(f"Error processing {file}: {e}")

# Handle cases where we have too many or too few files
if len(average_displacements) < total_required:
    # Pad with NaNs if there are fewer values than needed
    average_displacements += [np.nan] * (total_required - len(average_displacements))
elif len(average_displacements) > total_required:
    # Trim extra values if more than needed
    average_displacements = average_displacements[:total_required]

# Reshape to 51x51
heatmap_avg_displacement = np.array(average_displacements).reshape(heatmap_dim)

# Plot heatmap of average displacements
plt.figure(figsize=(10, 8))
plt.imshow(heatmap_avg_displacement, cmap='viridis', interpolation='nearest', vmin=0, vmax=2)
plt.colorbar(label='Average Displacement')
plt.title('100x100 Signal Strength Heatmap with Pulser Off')
plt.xlabel('X')
plt.ylabel('Y')
plt.show()
