import frame_generator as generator

FILE = 0
file_name, file_path = generator.file_path(FILE)

print(f"Generating frames for: {file_name.name}\n")
print(f"File path: {file_path}\n")

generator.save_metadata_md(file_name, file_path)

#generator.data_viewer(file_name)
generator.generate_frames(file_name, file_path)