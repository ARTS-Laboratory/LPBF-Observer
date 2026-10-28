
from pathlib import Path
import numpy as np
import cv2
import os
import re
import struct
import zlib
import matplotlib.pyplot as plt

# ==========================================
# USER SETTINGS
# ==========================================

# Folder containing binary images
INPUT_FOLDER = Path(r"C:\OpticalTestFolder\BIN")
folder_path = INPUT_FOLDER

# PNG files will be saved inside this folder
OUTPUT_FOLDER = INPUT_FOLDER / "Converted_PNG"

# Optical camera image dimensions
WIDTH = 5472
HEIGHT = 3648

# For grayscale images: 1
# For RGB images: 3
CHANNELS = 1

# For 8-bit images: np.uint8
# For 16-bit images: np.uint16
DATA_TYPE = np.uint8

# PNG compression: 0 (fastest) to 9 (smallest)
PNG_COMPRESSION = 1

# DPI metadata written to converted PNG files
PNG_DPI = 300

# Binary file extensions
EXTENSIONS = {".bin", ".raw", ".dat"}

# ==========================================
# INITIAL CHECKS
# ==========================================

def add_png_dpi_metadata(png_data, dpi):
    if dpi <= 0:
        raise ValueError("PNG_DPI must be greater than zero.")

    if not png_data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Encoded image is not a PNG file.")

    ihdr_length = struct.unpack(">I", png_data[8:12])[0]
    if png_data[12:16] != b"IHDR" or ihdr_length != 13:
        raise ValueError("PNG file has an invalid IHDR chunk.")

    pixels_per_meter = round(dpi / 0.0254)
    chunk_type = b"pHYs"
    chunk_data = struct.pack(
        ">IIB", pixels_per_meter, pixels_per_meter, 1
    )
    chunk = (
        struct.pack(">I", len(chunk_data))
        + chunk_type
        + chunk_data
        + struct.pack(
            ">I", zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        )
    )
    ihdr_end = 8 + 4 + 4 + ihdr_length + 4
    return png_data[:ihdr_end] + chunk + png_data[ihdr_end:]


print("Input folder:", INPUT_FOLDER.resolve())

if not INPUT_FOLDER.is_dir():
    raise FileNotFoundError(
        f"Input folder does not exist: {INPUT_FOLDER}"
    )

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

files = sorted(
    p for p in INPUT_FOLDER.rglob("*")
    if p.is_file()
    and p.suffix.lower() in EXTENSIONS
    and OUTPUT_FOLDER not in p.parents
)

print("\nBinary files found:", len(files))

if not files:
    print("\nNo binary files found!")
    print("Files in input folder:")
    for p in list(INPUT_FOLDER.iterdir())[:20]:
        print("  ", p.name)
    raise RuntimeError(
        "Check the folder and binary file extensions."
    )

# ==========================================
# CONVERSION FUNCTION
# ==========================================

def convert_binary_to_png(binary_path):

    print(f"\nProcessing: {binary_path.name}")

    # Read binary file
    raw_bytes = binary_path.read_bytes()

    file_size = len(raw_bytes)

    expected_size = (
        WIDTH * HEIGHT * CHANNELS
        * np.dtype(DATA_TYPE).itemsize
    )

    print("File size:", file_size, "bytes")
    print("Expected size:", expected_size, "bytes")

    # Detect raw data or common LabVIEW headers
    header_size = file_size - expected_size

    if header_size not in (0, 4, 8):
        print("ERROR: Binary file size mismatch.")
        print("Possible causes:")
        print(" - Incorrect image dimensions")
        print(" - Incorrect channel count")
        print(" - Incorrect pixel data type")
        print(" - Additional file header or padding")
        return False

    print("Detected header bytes:", header_size)

    # Convert binary data into numpy array
    image_array = np.frombuffer(
        raw_bytes,
        dtype=DATA_TYPE,
        count=WIDTH * HEIGHT * CHANNELS,
        offset=header_size
    )

    # Reshape image
    if CHANNELS == 1:
        image = image_array.reshape(
            HEIGHT, WIDTH
        )

    elif CHANNELS == 3:
        image = image_array.reshape(
            HEIGHT, WIDTH, 3
        )

        # RGB to BGR for OpenCV
        image = cv2.cvtColor(
            image, cv2.COLOR_RGB2BGR
        )

    else:
        raise ValueError(
            "CHANNELS must be 1 or 3."
        )

    # Create PNG output filename
    output_path = (
        OUTPUT_FOLDER / (binary_path.stem + ".png")
    )

    # Encode image as PNG
    success, encoded = cv2.imencode(
        ".png",
        image,
        [cv2.IMWRITE_PNG_COMPRESSION,
         PNG_COMPRESSION]
    )

    if not success:
        print("ERROR: PNG encoding failed!")
        return False

    png_data = add_png_dpi_metadata(encoded.tobytes(), PNG_DPI)

    # Write image
    output_path.write_bytes(png_data)

    # Verify output
    if output_path.exists() and output_path.stat().st_size > 0:
        print("SUCCESS: Saved PNG")
        print("Location:", output_path.resolve())
        return True

    print("ERROR: PNG was not saved.")
    return False


# ==========================================
# PROCESS ALL FILES
# ==========================================

successful = 0
failed = 0

for binary_file in files:

    try:
        result = convert_binary_to_png(binary_file)

        if result:
            successful += 1
        else:
            failed += 1

    except Exception as e:
        failed += 1
        print("ERROR:", repr(e))


# ==========================================
# FINAL REPORT
# ==========================================

print("\n====================================")
print("CONVERSION SUMMARY")
print("====================================")

print("Total files:", len(files))
print("Successfully converted:", successful)
print("Failed:", failed)

print("\nPNG output folder:")
print(OUTPUT_FOLDER.resolve())

print("====================================")

# ==========================================        
## Plotting the FPS and output timestamp
# ========================================= 
# Number of files to analyze (None = all files)
num_files = None

# -----------------------------------
# READ FILE NAMES
# -----------------------------------

timestamps = []

for filename in os.listdir(folder_path):

    # Match filenames like optical_0000.bin
    match = re.match(r"^optical_(\d+)\.bin$", filename, re.IGNORECASE)

    if match:
        timestamp = int(match.group(1))
        timestamps.append(timestamp)

# Sort timestamps chronologically
timestamps = np.sort(timestamps)

# Limit number of files
if num_files is not None:
    timestamps = timestamps[:num_files]

# -----------------------------------
# CALCULATE TIME STEPS
# -----------------------------------

# Difference between consecutive timestamps (ms)
dt = np.diff(timestamps)

# Image number (starting at image 2)
image_number = np.arange(2, len(timestamps) + 1)

# -----------------------------------
# STATISTICS
# -----------------------------------

if len(dt) == 0:
    raise ValueError("At least two matching image files are required.")

print(f"Number of images analyzed: {len(timestamps)}")
print(f"Average time step: {np.mean(dt):.3f} ms")
print(f"Minimum time step: {np.min(dt):.3f} ms")
print(f"Maximum time step: {np.max(dt):.3f} ms")
print(f"Standard deviation: {np.std(dt):.3f} ms")

# -----------------------------------
# PLOT TIME STEP FLUCTUATIONS
# -----------------------------------

plt.figure(figsize=(12, 5))

plt.plot(image_number, dt, '-o',
         markersize=3,
         linewidth=1,
         color='blue',
         label='Actual Time Step')

plt.axhline(np.mean(dt),
            color='red',
            linestyle='--',
            linewidth=1.5,
            label=f'Average = {np.mean(dt):.2f} ms')

plt.xlabel("Image Number")
plt.ylabel("Time Step (ms)")
plt.title("Optical Camera Acquisition Time Step Fluctuations")

plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()