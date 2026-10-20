
from pathlib import Path
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

# -------- USER SETTINGS --------
FOLDER = Path(r"C:\Users\killedar\OneDrive - University of South Carolina\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_12\data\raw\test_1_optical_thermal")

OPTICAL_FILE = FOLDER / "optical_21005.png"
THERMAL_FILE = FOLDER / "Thermal_21005.npz"

# -------- THERMAL NPZ FILE --------
print("\n========== THERMAL CAMERA ==========")

with np.load(THERMAL_FILE, allow_pickle=False) as data:
    print("Available NPZ keys:", data.files)

    for key in data.files:
        value = data[key]
        print(f"\nKey: {key}")
        print("Shape:", value.shape)
        print("Data type:", value.dtype)

        if value.size <= 20:
            print("Value:", value)
        elif any(word in key.lower() for word in
                 ["time", "stamp", "frame", "meta"]):
            print("First values:", value.flat[:10])

# -------- OPTICAL PNG FILE --------
print("\n========== OPTICAL CAMERA ==========")

with Image.open(OPTICAL_FILE) as img:
    print("Image size:", img.size)
    print("Image format:", img.format)

    print("\nPNG metadata:")
    if img.info:
        for key, value in img.info.items():
            print(f"{key}: {value}")
    else:
        print("No PNG metadata found.")

    print("\nEXIF metadata:")
    exif = img.getexif()

    if exif:
        for key, value in exif.items():
            print(f"{key}: {value}")
    else:
        print("No EXIF metadata found.")
