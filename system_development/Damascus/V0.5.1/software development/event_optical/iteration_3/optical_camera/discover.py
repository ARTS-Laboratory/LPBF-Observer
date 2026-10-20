"""Inspect Spinnaker discovery without initializing cameras or changing settings."""
import argparse
import json
import sys


def node_text(PySpin, nodemap, name):
    node = PySpin.CValuePtr(nodemap.GetNode(name))
    return node.ToString() if PySpin.IsReadable(node) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check imports without discovering cameras")
    args = parser.parse_args()
    import numpy
    import PySpin

    if args.check:
        print(json.dumps({"python": sys.version.split()[0], "numpy": numpy.__version__,
                          "PySpin": PySpin.__file__}, indent=2))
        return 0

    system = PySpin.System.GetInstance()
    cameras = None
    camera = None
    nodemap = None
    try:
        version = system.GetLibraryVersion()
        print("Spinnaker: " + ".".join(str(getattr(version, field)) for field in
                                       ("major", "minor", "type", "build")))
        cameras = system.GetCameras()
        count = cameras.GetSize()
        print(f"Discovered cameras: {count}")
        for index in range(count):
            camera = cameras.GetByIndex(index)
            try:
                nodemap = camera.GetTLDeviceNodeMap()
                row = {name: node_text(PySpin, nodemap, name) for name in
                       ("DeviceVendorName", "DeviceModelName", "DeviceSerialNumber",
                        "DeviceID", "GevDeviceIPAddress", "DeviceAccessStatus")}
                print(json.dumps(row, indent=2))
            finally:
                nodemap = None
                camera = None
        return 0 if count else 1
    finally:
        nodemap = None
        camera = None
        if cameras is not None:
            cameras.Clear()
            cameras = None
        system.ReleaseInstance()


if __name__ == "__main__":
    raise SystemExit(main())
