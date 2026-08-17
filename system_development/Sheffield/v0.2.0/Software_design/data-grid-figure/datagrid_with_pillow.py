# -*- coding: utf-8 -*-
"""
Created on Wed Jul 31 10:04:02 2024

@author: mumin
"""

#import pandas as pd
from PIL import Image
import IPython as IP

IP.get_ipython().run_line_magic('reset', '-sf')

#df = pd.read_csv('file_name.csv')

dim = (100, 100)
w, h = dim
colors = ['#BCBDEF', '#6820B0', '#4FEEF6']

#background
bg = Image.new("RGB", (w*10, h*10))

#generate layers
layers = {}

for i in range(1, 11):
    color_index = (i - 1) % len(colors)
    color = colors[color_index]
    layers[f'lay{i}'] = Image.new("RGB", dim, color)

# Determine size of base image
num_layers = len(layers)

#paste layers
for i in range(1, num_layers + 1):
    img = layers[f'lay{i}']
    bg.paste(img, ((i - 1) * w, 0))

# Show or save the base image
bg.show()
        
        
        
        
        
        
        