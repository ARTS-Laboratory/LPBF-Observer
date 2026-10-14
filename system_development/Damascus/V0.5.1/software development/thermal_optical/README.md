# Thermal + Optical

## Iteration #1
* intial integration, optical starts, optris calibrates, then thermal starts on record.
* "delay" problem fixed in iteration 3

## Iteration #2
* Run VI -> Optical starts after Optris calibration, Thermal starts on "Record"
* output:
	optical_000000000 (in milisec)
 
	thermal_000000001 (in n values)

## Iteration #3
* output:
	optical_0000 (indexes)
 
	thermal_0000 (indexes)
	
## Iteration #4
* (code based on new, simplfied server file (thermalServer.py). no preview. no backwards communication to labview. NPZ processor code gives PNGs & CSVs for each file name)
* labview --(file name)--> thermalServer --> npz output
* output:
	thermal_0000 (indexes)
	
## Iteration #5
* v4 functionality plus folder path and all camera functions (flag, focus, start, stop)
* output:
	Recordings/thermal_0000.npz
* npzProcessing.py gives:
	Images/thermal_0000/thermal_0000.png & .csv

## Iteration #6
* optical (ONLY) vi with input capture interval
* output:
	Data/optical_0000.png

## Iteration #7
* combined vi thermal and optical functionality (updated verion of iteration 3)

## Iteration #8
* thermal + optical capture in a loop together
* npzProcessor is now in the data folder

## Iteration #9
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


