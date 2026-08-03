import functions as fun

device = fun.initializeDevice()

fun.configureDevice(device)

#fun.printXYTPEvents(device)
fun.recordEventsXYTP(device)

fun.destroyDevice(device)