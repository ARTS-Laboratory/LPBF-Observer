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

## Image Placeholder 1

> Insert a screenshot showing the **Jumbo Packet** setting here.

![Jumbo Packet Screenshot](Media\JumboPacket.png)

------------------------------------------------------------------------

## Image Placeholder 2

> Insert a screenshot showing the **Receive Buffer** setting here.

![Receive Buffer Screenshot](Media\ReceiveBuffers.png)

------------------------------------------------------------------------

## Notes

-   The maximum available values may differ depending on the network
    adapter manufacturer and model.
-   After changing these settings, restart the network connection or
    reboot the computer if required.
-   These settings are commonly used to improve the reliability of
    high-bandwidth GigE Vision camera streaming.