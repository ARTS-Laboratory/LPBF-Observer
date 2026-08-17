import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Folder path
folder_path = r"C:\Users\mwhetham\Desktop\signal strength data\Experiment4(NEW)\Meas(02of12)"
max_frequencies = []

# Loop through each file in the directory
for file in os.listdir(folder_path):
    file_path = os.path.join(folder_path, file)
    
    try:
        # Read the file (pandas will attempt to read most text-based files, such as CSV, TXT, etc.)
        # We assume the first column is time and the second column is displacement
        data = pd.read_csv(file_path, skiprows=24, header=None)  # header=None to avoid incorrect parsing
        
        # Check the first few rows to understand the structure of the data
        print(f"Data preview from {file}:")
        print(data.head())
        
        # Assuming the first column is time and the second column is displacement
        time = data.values[:, 0]  # Time column
        displacement = data.values[:, 1]  # Displacement column
        
        # Visualize the raw displacement signal
        plt.figure(figsize=(10, 4))
        plt.plot(time, displacement)
        plt.title(f"Raw Displacement Signal from {file}")
        plt.xlabel('Time (s)')
        plt.ylabel('Displacement')
        plt.grid(True)
        plt.show()

        # Calculate the sampling interval (assuming uniform time intervals)
        # Sampling rate = 1 / (Time difference between consecutive samples)
        dt = np.mean(np.diff(time))  # Mean time interval between consecutive samples
        sampling_rate = 1 / dt
        print(f"Sampling rate for {file}: {sampling_rate} Hz")
        
        # Apply FFT to the displacement signal
        fft_result = np.fft.fft(displacement)
        
        # Compute the frequencies corresponding to the FFT result
        n = len(displacement)  # Number of data points
        freqs = np.fft.fftfreq(n, d=dt)  # Frequency axis
        
        # Only keep the positive half of the spectrum (real frequencies)
        positive_freqs = freqs[:n//2]
        positive_fft = np.abs(fft_result)[:n//2]  # Magnitudes of the FFT
        
        # Find the frequency with the maximum magnitude
        max_freq = positive_freqs[np.argmax(positive_fft)]
        max_frequencies.append(max_freq)
        
        # Plot the FFT (frequency spectrum)
        plt.figure(figsize=(10, 6))
        plt.plot(positive_freqs, np.log(positive_fft + 1e-10))  # Log scale for better visualization
        plt.title(f"FFT of {file}")
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Log(Amplitude)')
        plt.grid(True)
        plt.show()
        
        # Print results for each file
        print(f"Max frequency (vibration) from {file}: {max_freq} Hz")
    except Exception as e:
        print(f"Error processing {file}: {e}")

# Optional: Print the list of all maximum frequencies
print("List of maximum vibration frequencies from all files:")
print(max_frequencies)
