import functions as fun
from Recorder.recorder_config import (
    POSITIVE_EVENT_BIAS,
    NEGATIVE_EVENT_BIAS,
    LOW_PASS_CUTOFF,
    REFRACTORY_PERIOD,
    ERC_ENABLE,
    ERC_RATE_LIMIT,
)

device = fun.initializeDevice()

fun.configureDevice(device)

fun.setEventBiases(
    device,
    positive=POSITIVE_EVENT_BIAS,
    negative=NEGATIVE_EVENT_BIAS,
    low_pass_cutoff=LOW_PASS_CUTOFF,
    refractory_period=REFRACTORY_PERIOD,
)

fun.verifyEventBiases(device)

fun.setErcSettings(device, enable=ERC_ENABLE, rate_limit=ERC_RATE_LIMIT)

#fun.printXYTPEvents(device)
fun.recordEventsXYTP(device)

fun.destroyDevice(device)