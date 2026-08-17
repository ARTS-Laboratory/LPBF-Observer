# -*- coding: utf-8 -*-
"""
Created on Wed Aug  7 13:17:08 2024

@author: mumin
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors 

# Generate random data 
data = np.random.randint(0, 100, size=(8, 8)) 

# Create a custom color map 
# with blue and green colors 
colors_list = ['#0099ff', '#33cc33'] 
cmap = colors.ListedColormap(colors_list) 

# Plot the heatmap with custom colors and annotations 
plt.imshow(data, cmap=cmap, vmin=0, vmax=100, extent=[0, 8, 0, 8]) 
for i in range(8): 
	for j in range(8): 
		plt.annotate(str(data[i][j]), xy=(j+0.5, i+0.5), 
					ha='center', va='center', color='white') 

# Add colorbar 
cbar = plt.colorbar(ticks=[0, 50, 100]) 
cbar.ax.set_yticklabels(['Low', 'Medium', 'High']) 

# Set plot title and axis labels 
plt.title("Customized heatmap with annotations") 
plt.xlabel("X-axis") 
plt.ylabel("Y-axis") 

# Display the plot 
plt.show() 
