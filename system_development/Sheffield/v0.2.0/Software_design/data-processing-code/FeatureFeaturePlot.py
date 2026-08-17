import os
import numpy as np
import pandas as pd
import re
import matplotlib.pyplot as plt
from scipy.stats import skew, kurtosis
import time

start_time = time.time()

folder_path = r"C:\Users\MADHAMI\Desktop\Vibration Scan 4"
print(f"\nReading files from:", folder_path)
#%% label points

def is_machined(x, y):
    return (0 <= x <= 3) and (0 <= y <= 24)

def is_welded(x, y):
    return (4 <= x <= 10) and (4 <= y <= 10)

feature_1 = []   # RMS
feature_2 = []   # Skew
labels = []

#%% read each file

for filename in os.listdir(folder_path):
    match = re.search(r'point-(\d+)-(\d+)', filename)
    if match:
        x = int(match.group(1))
        y = int(match.group(2))

        if is_machined(x, y) or is_welded(x, y):

            file_path = os.path.join(folder_path, filename)

            #load data
            data = pd.read_csv(file_path, skiprows=22)
            signal = data.iloc[:, 1].values # 1 for velocity column, 2 for signal column

            # calculate features (RMS, Skew, StDev, Mean, Kurtosis)
            rms = np.sqrt(np.mean(signal**2))
            skewness = skew(signal)
            stdv = np.std(signal)
            kurt = kurtosis(signal)

            feature_1.append(skewness)
            feature_2.append(kurt)

            if is_machined(x, y):
                labels.append("machined")
            else:
                labels.append("welded")

#automatic name writing
feature_1_name = "Skewness"
feature_2_name = "Kurtosis"
plot_name = f"{feature_1_name} vs {feature_2_name}"

# convert to numpy arrays
feature_1 = np.array(feature_1)
feature_2 = np.array(feature_2)
labels = np.array(labels)

#%% plot
plt.figure(figsize=(8, 6))
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 16

# separate by label
machined_mask = labels == "machined"
welded_mask = labels == "welded"

plt.scatter(feature_1[machined_mask],
            feature_2[machined_mask],
            color='blue',
            label='Machined',
            alpha=0.7)

plt.scatter(feature_1[welded_mask],
            feature_2[welded_mask],
            color='red',
            label='Welded',
            alpha=0.7)

plt.xlabel(feature_1_name)
plt.ylabel(feature_2_name)
plt.title(plot_name)
plt.legend()
plt.grid(True)

plt.tight_layout()

save_path = os.path.join(
    r"C:\Users\MADHAMI\Dropbox\2026 SPIE Defense Paper\Making-figures\feature-plots",
    plot_name + ".png"
)
plt.savefig(save_path, format='png', bbox_inches='tight')

plt.show()

#%%
end_time = time.time()
print(f"\nRuntime: {end_time - start_time:.3f} seconds")
