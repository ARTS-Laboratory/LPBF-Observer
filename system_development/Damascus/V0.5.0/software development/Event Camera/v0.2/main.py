import functions as fun

devices = fun.initializeDevice()

device = fun.selectDevice(devices)

fun.configureDevice(device)

fun.recordXYTPEvents(device)

fun.destroyDevice(devices)