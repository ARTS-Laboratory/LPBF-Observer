# -*- coding: utf-8 -*-
"""
Created on Tue Aug  6 16:14:31 2024

@author: mumin
"""

# importing the modules 
import numpy as np 
import seaborn as sns 
import matplotlib.pyplot as plt 
	
# generating 2-D 10x10 matrix of random numbers 
# from 1 to 100 
data = np.random.randint(low=1, 
						high=100, 
						size=(10, 10)) 
	
# plotting the heatmap 
hm = sns.heatmap(data=data, 
				annot=True) 
	
# displaying the plotted heatmap 
plt.show()
