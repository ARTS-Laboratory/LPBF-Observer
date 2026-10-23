
from pathlib import Path
import numpy as np
import cv2

# ==========================================
# USER SETTINGS
# ==========================================

# Folder containing binary images
INPUT_FOLDER = Path(r"C:\Users\killedar\OneDrive - University of South Carolina\GitHub\LPBF-Observer\system_development\Damascus\V0.5.1\software development\thermal_optical\iteration_19\data\raw\test_5")

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
DATA_TYPE = np.uint16

# PNG compression: 0 (fastest) to 9 (smallest)
PNG_COMPRESSION = 1

# Binary file extensions
EXTENSIONS = {".bin", ".raw", ".dat"}

# ==========================================
# INITIAL CHECKS
# ==========================================

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

    # Write image
    output_path.write_bytes(encoded.tobytes())

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
