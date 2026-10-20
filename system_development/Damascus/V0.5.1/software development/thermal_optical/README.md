# Thermal + Optical
* these notes provide details re: functionality
* see README inside code folder for details

## Iteration 01
* intial integration, optical starts, optris calibrates, then thermal starts on record.
* "delay" problem fixed in iteration 3


## Iteration 02
* Run VI -> Optical starts after Optris calibration, Thermal starts on "Record"
* output:
	optical_000000000 (in milisec)
 
	thermal_000000001 (in n values)


## Iteration 03
* output:
	optical_0000 (indexes)
 
	thermal_0000 (indexes)
	
	
## Iteration 04
* (code based on new, simplfied server file (thermalServer.py). no preview. no backwards communication to labview. NPZ processor code gives PNGs & CSVs for each file name)
* labview --(file name)--> thermalServer --> npz output
* output:
	thermal_0000 (indexes)
	
	
## Iteration 05
* v4 functionality plus folder path and all camera functions (flag, focus, start, stop)
* output:
	Recordings/thermal_0000.npz
* npzProcessing.py gives:
	Images/thermal_0000/thermal_0000.png & .csv


## Iteration 06
* optical (ONLY) vi with input capture interval
* output:
	Data/optical_0000.png


## Iteration 07
* combined vi thermal and optical functionality (updated verion of iteration 3)


## Iteration 08
* thermal + optical capture in a loop together
* npzProcessor is now in the data folder


## Iteration 09
* thermal + optical capture in a loop together with file names based on timestamp
* dataset alignment possible with file names

* To Do Items at this stage:
* figure out whats setting the thermal fps
* set optical to 1000ms fps
* optimize IMAQ to be quicker (if we have to go higher FPS)
* Change to:
* output:
	Recordings/thermal_0000.npz
* npzProcessing.py gives: (so we arrow through the images)
	Images/thermal_0000.png
	CSV/   thermal_0000.csv


## Iteration 10
* thermal + optical capture in a loop together with file names based on timestamp and shared folder path
* npz shows thermal preview
* indicators: thermal frame out, optical frame out, time b/w frames


## Iteration 11
* additional functionality: writes a new folder in data path (instead of just writing files to specified path)


## Iteration 12
* thermal & optical separated (thermal_1 & optical_1) to test speeds of individual VIs
* results:
	thermal = ~50 ms			(consitent)
	optical = ~[875 - 1000] ms	(very laggy)


## Iteration 13
* using FLIR camera.vi to collect images faster (it currently outputs AVI files)
* Link to repo: https://github.com/ARTS-Laboratory/LabVIEW-code-for-Recording-FLIR-Blackfly-videos
* next iteration will be integrating v12 thermal loop into FLIR VI for faster acquisition


## Iteration 14
* reconfig "FLIR Camera.vi" to output PNGs only
* sub-iterations "14.n" are step wise attempts to write PNGs

## Iteration 15
* optimized thermal_optical_capture.vi (not using FLIR Camera.vi structure)
* 

## Iteration 16
* v14 + thermal acquisition loop
* NPZs & PNGs write to same file path, with file names from same clock