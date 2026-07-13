import bomboclatFunctions as system

devices = system.initializeDevice()
device = system.selectDevice(devices)
deviceSettings = system.configureDevice(device)

width = deviceSettings["width"]
height = deviceSettings["height"]
acquisitionMode = deviceSettings["acquisitionMode"]

print(f"{width}, {type(width)}")
print(f"{height}, {type(height)}")
print(f"{acquisitionMode}, {type(acquisitionMode)}")

system.destroyDevice(devices)
