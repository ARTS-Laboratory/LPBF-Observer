import functions as fun

devices = fun.initializeDevice()

device = fun.selectDevice(devices)

fun.printXYTPEvents(device)

fun.destroyDevice(devices)