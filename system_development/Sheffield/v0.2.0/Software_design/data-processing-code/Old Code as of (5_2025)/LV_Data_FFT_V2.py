import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Folder path
folder_path = r"C:\Users\mwhetham\Desktop\LayerV5Data\Test5(NEW)"
max_frequencies = []
average_amplitudes = []
# Loop through each file in the directory
for file in os.listdir(folder_path):
    file_path = os.path.join(folder_path, file)
    
    try:
        # Read the file
        data = pd.read_csv(file_path, skiprows=24, header=None)
        print(f"Data preview from {file}:")
        print(data.head())
        
        time = data.values[:, 0]  # Time column
        displacement = data.values[:, 1]  # Displacement column
        
        # Plot raw signal
      #  plt.figure(figsize=(10, 4))
       # plt.plot(time, displacement)
       # plt.title(f"Raw Displacement Signal from {file}")
       # plt.xlabel('Time (s)')
       # plt.ylabel('Displacement')
      #  plt.grid(True)
        

        # Sampling interval and rate
        dt = 2.5E-9
        sampling_rate = 1 / dt
        print(f"Sampling rate for {file}: {sampling_rate} Hz")
        
        # FFT computation
        fft_result = np.fft.fft(displacement)
        n = len(displacement)
        freqs = np.fft.fftfreq(n, d=dt)
        
        # Positive half spectrum
        positive_freqs = freqs[:n//2]
        positive_fft = np.abs(fft_result)[:n//2]
        
        # Max frequency
        max_freq = positive_freqs[np.argmax(positive_fft)]
        max_frequencies.append(max_freq)
        
        avg_amplitude = np.max(displacement)
        average_amplitudes.append(avg_amplitude)
        # Plot FFT spectrum
       # plt.figure(figsize=(10, 6))
       # plt.plot(positive_freqs, np.log(positive_fft + 1e-10))
       # plt.title(f"FFT of {file}")
        #plt.xlabel('Frequency (Hz)')
       # plt.ylabel('Log(Amplitude)')
       # plt.grid(True)
        
        
        print(f"Max frequency (vibration) from {file}: {max_freq} Hz")
    except Exception as e:
        print(f"Error processing {file}: {e}")

# Heatmap generation
# Assuming the max frequencies correspond to files in order, reshape for visualization
num_files = len(max_frequencies)
heatmap_data = np.array(max_frequencies).reshape(-1, int(np.sqrt(num_files)))  # Adjust based on file count

num_files = len(max_frequencies)
heatmap_size = int(np.sqrt(num_files))  # Assumes roughly square arrangement

# Reshape max_frequencies and average_amplitudes for visualization
heatmap_max_freq = np.array(max_frequencies).reshape(-1, heatmap_size)
heatmap_avg_amplitude = np.array(average_amplitudes).reshape(-1, heatmap_size)

plt.figure(figsize=(10, 8))
plt.imshow(heatmap_data, cmap='hot', interpolation='nearest')
plt.colorbar(label='Max Frequency (Hz)')
plt.title('Heatmap of Maximum Frequencies')
plt.xlabel('File Index (X)')
plt.ylabel('File Index (Y)')
plt.show()


plt.figure(figsize=(10, 8))
plt.imshow(heatmap_avg_amplitude, cmap='cool', interpolation='nearest')
plt.colorbar(label='Average Amplitude')
plt.title('Heatmap of Average Amplitudes')
plt.xlabel('File Index (X)')
plt.ylabel('File Index (Y)')
plt.show()