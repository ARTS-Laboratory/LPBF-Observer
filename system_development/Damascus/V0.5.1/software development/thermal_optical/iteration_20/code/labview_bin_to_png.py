
import numpy as np
from PIL import Image
from pathlib import Path

# ============================================================
# INPUT AND OUTPUT FOLDER (SAME FOLDER)
# ============================================================

FOLDER = Path(
    r"C:\Users\killedar\OneDrive - University of South Carolina"
    r"\GitHub\LPBF-Observer\system_development\Damascus"
    r"\V0.5.1\software development\thermal_optical"
    r"\iteration_20\data\raw\test_1"
)

# ============================================================
# CONVERT LABVIEW RGB U32 BINARY TO PNG
# ============================================================

def convert_bin_to_png(bin_path):

    # Read binary file as little-endian unsigned 32-bit values
    data = np.fromfile(bin_path, dtype="<u4")

    if data.size < 3:
        raise ValueError("File is empty or too small.")

    # First two values contain image dimensions
    height = int(data[0])
    width = int(data[1])

    if height <= 0 or width <= 0:
        raise ValueError("Invalid image dimensions.")

    print(f"Processing: {bin_path.name}")
    print(f"Image dimensions: {width} x {height}")

    # Extract image pixels
    pixels = data[2:]

    expected_pixels = height * width

    if pixels.size != expected_pixels:
        raise ValueError(
            f"Expected {expected_pixels} pixels, "
            f"but found {pixels.size}."
        )

    pixels = pixels.reshape((height, width))

    # Convert LabVIEW RGB U32 to RGB channels
    red = ((pixels >> 16) & 0xFF).astype(np.uint8)
    green = ((pixels >> 8) & 0xFF).astype(np.uint8)
    blue = (pixels & 0xFF).astype(np.uint8)

    # Combine RGB channels
    rgb_image = np.stack(
        (red, green, blue),
        axis=-1
    )

    # Save PNG in SAME folder
    png_path = bin_path.with_suffix(".png")

    Image.fromarray(rgb_image, mode="RGB").save(png_path)

    print(f"Saved: {png_path.name}")
    print("--------------------------------")


# ============================================================
# PROCESS ALL BINARY FILES
# ============================================================

def main():

    if not FOLDER.exists():
        print(f"Folder not found: {FOLDER}")
        return

    bin_files = sorted(FOLDER.glob("*.bin"))

    if not bin_files:
        print("No binary files found.")
        return

    print(f"Found {len(bin_files)} binary files.\n")

    converted = 0
    failed = 0

    for bin_file in bin_files:

        try:
            convert_bin_to_png(bin_file)
            converted += 1

        except Exception as e:
            failed += 1
            print(f"ERROR: {bin_file.name}: {e}")

    print("\nConversion complete!")
    print(f"Successfully converted: {converted}")
    print(f"Failed: {failed}")
    print(f"Output folder: {FOLDER}")


if __name__ == "__main__":
    main()
