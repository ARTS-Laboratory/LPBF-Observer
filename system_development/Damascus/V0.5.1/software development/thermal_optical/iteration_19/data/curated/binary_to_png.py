# -*- coding: utf-8 -*-
"""
Created on Fri Oct 23 11:55:38 2026

@author: MADHAMI
"""

import numpy as np
from PIL import Image
import os
import glob

# ============================================================
# USER INPUTS
# ============================================================

# Folder containing binary files
input_folder = r"C:\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_19\data\raw\test_5"

# Folder where PNG images will be saved
output_folder = r"C:\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_19\data\raw\curated\test_5"

# Image resolution (CHANGE TO MATCH YOUR CAMERA)
width = 5472
height = 3648

# Pixel format
# np.uint8  = 8-bit grayscale
# np.uint16 = 16-bit grayscale
dtype = np.uint8

# ============================================================
# CREATE OUTPUT FOLDER
# ============================================================

os.makedirs(output_folder, exist_ok=True)

# ============================================================
# FIND BINARY FILES
# ============================================================

bin_files = sorted(glob.glob(os.path.join(input_folder, "optical_*.bin")))

print(f"Found {len(bin_files)} binary files.")

# ============================================================
# CONVERT BIN TO PNG
# ============================================================

for file_path in bin_files:

    # Get filename without extension
    filename = os.path.splitext(os.path.basename(file_path))[0]

    # Read binary pixel data
    image_data = np.fromfile(file_path, dtype=dtype)

    # Verify image dimensions
    expected_pixels = width * height

    if image_data.size != expected_pixels:
        print(f"Skipping {filename}: "
              f"Expected {expected_pixels} pixels, "
              f"found {image_data.size}")
        continue

    # Reconstruct image
    image_array = image_data.reshape((height, width))

    # Convert array to image
    image = Image.fromarray(image_array)

    # Define output path
    output_path = os.path.join(output_folder, filename + ".png")

    # Save PNG
    image.save(output_path)

    print(f"Saved: {output_path}")

print("Conversion complete.")