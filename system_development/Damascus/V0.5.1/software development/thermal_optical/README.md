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
* new plan: use "Stream to Image Files-example" to write PNGs (instead of reconfig FLIR Camera.vi)


## Iteration 15
* optimized thermal_optical_capture.vi (not using FLIR Camera.vi structure)* 


## Iteration 16
* (v16.1) v14 + thermal acquisition loop
* NPZs & PNGs write to same file path, with file names from same clock
* includes optical only VI "ImageAcquisition_16"


## Iteration 17
* examples VI from LabView
* Final Image Aquisition Simplified VI for capturing optical images in .png


## Iteration 18
* combined Thermal & optical VI for capturing thermal and optical images.
* where optical uses Snap.vi (still slow frame rate)


## Iteration 19
* thermal + optical VI where optical uses GetImage2.vi (still ~2fps)
* Contains VI for different aquisition approaches using IMAQdx.
* optical_grab2 VI captures at 16.67 fps and writes binary files.
* Optical Camera Acquisition Benchmarks table found here.


## Iteration 20
* optical_grab2 -> binary files out.

* Experimental notes (VI params -> result)
- Pixel Format, Image Out Type (NI MAX)
______________________________________________________________

* U8 w/o Wait -> fluctuating (4-16) FPS, file size out: 19MB
- Mono 8, GreyscaleU8

* U8 w Wait -> fluctuating (0-10) FPS, file size out: 19MB
- Mono 8, GreyscaleU8

* U16 w/o Wait -> fluctuating (1-10) FPS, file size out: 38MB
- Mono__, GreyscaleU16

* U16 w Wait -> fluctuating (1-10) FPS, file size out: 38MB
- Mono__, GreyscaleU16

* Also data processing code is here (time_step plot generator and Binary->PNG python files)


## Iteration 21
* optical_grab2 using property nodes to set pixel format & image out type (Mono 8, GreyscaleU8)
* FLIR BFS-U3-200S6M-C has ADC 10 bit & 12 bit. ADC Bit Depth is kept at 12 Bit and Pixel format is mono12p as per the camera specifications. (Mono12p would require GreyscaleU16)
* Optical_grab2.vi saves the binary images in mono16 format.
* Optical_grab2 combined with thermal image capturing to create thermal_optical_capture_21.


## Iteration 22
* copy of 21 with objective to determine optimal bit depth & pixel/image format combinations
* doesn't have a significant effect because its the file writing that is the bottleneck


## Iteration 23
* loop for capture and loop for file saving with buffer to maintain capture FPS and allow slow writing speed.

## Iteration 24
* optical_grab2.vi is writing images in TDMS format.