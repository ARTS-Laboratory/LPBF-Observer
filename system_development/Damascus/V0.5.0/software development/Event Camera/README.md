# Network Adapter Configuration

## Overview

To help improve camera streaming performance and reduce dropped packets
or acquisition interruptions, configure your network adapter with the
highest supported values for the settings below.

> **Note:** Do **not** manually enter the values shown in example
> screenshots. Instead, configure each setting to the **maximum value
> allowed by your network adapter**.

## Configuration Steps

1.  Open **Network Connections**.
2.  Right-click the Ethernet adapter connected to the camera and select
    **Properties**.
3.  Click **Configure**.
4.  Open the **Advanced** tab.
5.  Locate the following settings:
    -   **Jumbo Packet**
    -   **Receive Buffer**
6.  Set each option to the **maximum value available** in the adapter's
    configuration.
7.  Click **OK** to save the changes.

------------------------------------------------------------------------

## Jumbo Packet

<img src="Media\JumboPacket.png" alt="App Preview" width="500">

------------------------------------------------------------------------

## Receive Buffer

<img src="Media\ReceiveBuffers.png" alt="App Preview" width="500">

------------------------------------------------------------------------

## Notes

-   The maximum available values may differ depending on the network
    adapter manufacturer and model.
-   After changing these settings, restart the network connection or
    reboot the computer if required.
-   These settings are commonly used to improve the reliability of
    high-bandwidth GigE Vision camera streaming.



# Arena SDK Installation Guide

## Overview

The camera software requires the **LUCID Arena SDK** to be installed before the camera can be detected and used.

> **Important:** During installation, you **must** enable **Developer Mode**. Failing to do so will result in missing development components required by the application.

---

## Download the Arena SDK

Download the Arena SDK installer using the link below (You must make an account with Lucid):

**Arena SDK Installer:**

![Arena SDK Installer](https://thinklucid.com/downloads-hub/)


---

## Installation Instructions

1. Download the Arena SDK installer from the link above.
2. Run the installer with administrator privileges.
3. Follow the installation wizard.
4. When prompted to select installation options, **enable Developer Mode**.

---

## ⚠️ Critical Requirement: Enable Developer Mode

> **Developer Mode must be selected during installation.**

If Developer Mode is **not** selected:

- Required development libraries and headers will not be installed.
- The application may fail to detect or communicate with the camera.
- Camera SDK components required by the application will be missing.
- You may encounter runtime errors or application startup failures.
- The SDK may need to be completely reinstalled to add the missing components.

**Verify that the "Developer Mode" option is checked before proceeding with the installation.**

---

## Developer Mode Installation

<img src="Media\DeveloperModeInstaller.png" alt="App Preview" width="500">

---

## Verify the Installation

After installation:

- Launch **ArenaView**.
- Verify that your camera is detected.
- Confirm that you can start image acquisition successfully.
- If the camera is not detected, verify that Developer Mode was enabled during installation.

---

## Troubleshooting

If the application cannot communicate with the camera:

1. Confirm that the Arena SDK is installed.
2. Verify that **Developer Mode** was selected during installation.
3. Restart the computer if prompted by the installer.
4. If Developer Mode was not selected, rerun the installer and modify or reinstall the SDK with Developer Mode enabled.

---

## Additional Notes

Always install the version of the Arena SDK that matches the version required by this application. Using a different SDK version may result in compatibility issues.