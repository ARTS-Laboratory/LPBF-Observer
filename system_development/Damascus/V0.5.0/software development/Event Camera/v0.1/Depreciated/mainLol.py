import bomboclatFunctions as fun

devices = fun.initializeDevice()
device = fun.selectDevice(devices)
settings = fun.configureDevice(device)

fun.recordVideo(device, seconds=20, out_file="run1.avi", fps=30)

fun.destroyDevice(devices)