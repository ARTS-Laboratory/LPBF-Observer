# -*- coding: utf-8 -*-
"""
Created on Mon Nov 18 16:27:11 2024

@author: mumin
"""

import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

directory = "C:/GitHub/In-situ-monitoring-of-powder-bed-fusion-additive-manufacturing/system_development/Orichalcum/v0.2/Software_design/v2-cover-control/Data Folder/"
print(Path.home())

max_frequencies = []

for i in range(0, 25):
    data_file = f"Test  {i}_001.lvm" if i < 10 else f"Test {i}_001.lvm"
    file_path = Path(directory, data_file)
    
    data = pd.read_csv(file_path, delimiter=',', skiprows=21, comment=';', header=0)
    
    column_data = data.iloc[:,1]
               
    fft_data = np.fft.fft(column_data)
    sample_rate = 100
    n = len(fft_data)
    freqs = np.fft.fftfreq(n, d=sample_rate)
    
    fft_magnitudes = np.abs(fft_data)
    
    positive_freqs = freqs[:n // 2]
    positive_magnitudes = fft_magnitudes[:n // 2]
    max_freq = positive_freqs[np.argmax(positive_magnitudes)]
    
    max_frequencies.append(max_freq)
    #print(f'Frequencies = {max_freq}')

freq_matrix = np.array(max_frequencies).reshape(5, 5)
print(freq_matrix)

plt.imshow(freq_matrix, cmap='viridis', interpolation='nearest')
plt.colorbar(label='Frequency (Hz)')
plt.title('Maximum Frequencies at Scanned Points')
plt.xticks(np.arange(5), [f"X{i+1}" for i in range(5)])
plt.yticks(np.arange(5), [f"Y{i+1}" for i in range(5)])
plt.show()
        