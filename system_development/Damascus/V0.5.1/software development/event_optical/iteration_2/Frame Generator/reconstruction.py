import frame_generator as generator
from telemetry import plot_telemetry

FILE = 2

file_name, file_path, folders = generator.file_path(FILE)

print(f"Generating frames for: {file_name.name}\n")
print(f"Output path: {file_path}\n")

generator.save_metadata_md(file_name, file_path)

plot_telemetry(
    file_name,
    file_path,
)

generator.generate_frames(
    file_name,
    file_path,
    folders,
)