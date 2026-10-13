import os 
from pathlib import Path
import cv2
import numpy as np
import time
from pytictoc import TicToc

#temp scale shit
low = 0
high = 250
t = TicToc()

def clear_terminal():
    # Check the operating system
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For macOS and Linux
        os.system('clear')

def gimmeFileNames(path, includeFolders=False):
    folder = Path(path)
    if includeFolders:
        names = [item.name for item in folder.iterdir()]
    else:
        names = [file.name for file in folder.iterdir() if file.is_file()]
    return names

def buildFilePaths(path):
    fileNames = gimmeFileNames(path)
    filePath = []
    
    for files in fileNames:
        filePath.append(os.path.join(path, files))
        
    return filePath

def loadData(path, name):
    print(f"Loading {name}.")

    data = np.load(path)
    frames = data['frames']
    timestamp = data['timestamp']
    frameTimestamps = data['frame_timestamps_ns']

    print(f"Loaded {frames.shape[0]} frames and {len(frameTimestamps)} timestamps in {name}.")

    return frames, timestamp, frameTimestamps


def saveVideo(path, name, output):
    print(f"Producing video for {name}")
    t.tic()

    folder = Path(output) / name
    folder.mkdir(parents = True, exist_ok = True)

    frames, timestamp, frameTimestamps = loadData(path, name)
    totalFrames, height, width, lo, hig, fps = getFramesInfo(frames)

    writer = cv2.VideoWriter(str(folder / f"{name}.mp4"), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height), isColor = True)
    
    finalMaxTemp = 0
    finalMaxIndex = 0

    for i, frame in enumerate(frames):

        normalized = ((frame - lo) / (hig - lo) * 255).astype(np.uint8)
        color = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)
        writer.write(color)

        maxTemp = frame.max()
        if maxTemp > finalMaxTemp:
            finalMaxTemp = maxTemp
            finalMaxIndex = i

    writer.release()

    t.toc()
    print(f"Final maximum temperature: {finalMaxTemp} °C at frame {finalMaxIndex}.\n")
    print(f"Saved → {folder}\n")

    return finalMaxIndex
    

def getFramesInfo(frames):
    totalFrames, height, width = frames.shape
    low = frames.min()
    high = frames.max()
    fps = 80

    return totalFrames, height, width, low, high, fps

def saveCSV(path, name, output, frameIndex):
    print(f"Producing CSV for {name}")
    t.tic()

    folder = Path(output) / name
    folder.mkdir(parents = True, exist_ok = True)

    frames, timestamp, frameTimestamps = loadData(path, name)
    totalFrames, height, width, low, high, fps = getFramesInfo(frames)

    frame = frames[frameIndex]
    np.savetxt(folder / f"{name}_frame{frameIndex}.csv", frame, delimiter=",", fmt="%.2f")

    t.toc()
    print(f"Saved CSV of frame {frameIndex} → {folder}\n")



