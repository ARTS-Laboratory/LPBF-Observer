# -*- coding: utf-8 -*-
"""
Created on Thu Aug 15 11:11:09 2024

@author: Mumin
"""

import IPython as IP
import numpy as np
import scipy as sp
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as colors 

IP.get_ipython().run_line_magic('reset', '-sf')

plt.close('all')

#%% Load Data

LV_data = np.loadtxt('data-files/LV-data/LV-data_5.txt', delimiter = ',', skiprows = 23)

data = LV_data.copy()[400:500:1]


#%% Create Heatmap

color_list = ['#f8c471', '#f5b041', '#f39c12', '#d68910', '#af601a', '#873600'] 
cmap = colors.ListedColormap(color_list) 

# Heatmap
plt.imshow(data, cmap=cmap, vmin=0, vmax=100, extent=[0, 10, 0, 10]) 
for i in range(10): 
	for j in range(10): 
		plt.annotate(str(data[i][j]), xy=(j+0.5, i+0.5), 
					ha='center', va='center', color='white') 

# Colorbar
cbar = plt.colorbar(ticks=list(range(0, 101, 10)))

plt.title("Heat Map") 
plt.xlabel("X-axis") 
plt.ylabel("Y-axis") 
plt.show()




