from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

inputPath = BASE_DIR / "Recordings"
outputPath = BASE_DIR / "Videos"
outputPathCSV = BASE_DIR / "CSV"


print(BASE_DIR.parent / "Record" / "Recordings")