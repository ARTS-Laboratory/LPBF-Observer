import functions as fun

device = fun.initializeDevice()

fun.configureDevice(device)

fun.setEventBiases(
    device,
    positive=25,
    negative=25,
    low_pass_cutoff=20,
    refractory_period=-20,
)

fun.verifyEventBiases(device)

fun.setErcSettings(device, enable=True, rate_limit=40.0)

#fun.printXYTPEvents(device)
fun.recordEventsXYTP(device)

fun.destroyDevice(device)