import functionFIles as bruh
from pytictoc import TicToc
from pathlib import Path

bruh.clear_terminal()

BASE_DIR = Path(__file__).resolve().parent

inputPath = BASE_DIR.parent / "Record" / "Recordings"
outputPath = BASE_DIR / "Videos"
outputPathCSV = BASE_DIR / "CSV"

fileNames = bruh.gimmeFileNames(inputPath)
filePaths = bruh.buildFilePaths(inputPath)
t = TicToc()

t.tic()

for i, path in enumerate(filePaths):
    print("" + "-"*50)
    frameIndex = bruh.saveVideo(filePaths[i], fileNames[i], outputPath)
    bruh.saveCSV(filePaths[i], fileNames[i], outputPathCSV, frameIndex)

t.toc()
print("All done!")