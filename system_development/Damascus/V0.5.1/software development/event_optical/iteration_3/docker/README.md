# Container work to complete later

The recorder supports a command-line entry point, no display dependency,
configurable SDK paths/output directory, and SIGTERM handling. Project source
does not contain a host-specific absolute `/home/thienan` runtime path. Large
recordings, local dependencies and virtual environments are excluded from the
future Docker build context.

Before implementing an image:

1. Validate Python 3.12 HAL acquisition and resolve the vendor native shutdown
   abort. Record the exact compatible OpenEB/Arena versions and dependencies.
2. Build an Ubuntu-based Python 3.12 native runtime from sources; do not copy
   Arch-built `.so` files into an Ubuntu image.
3. Determine how users will supply the vendor SDK under its distribution terms.
4. Use the same `event-record` entry point with a writable mounted output
   directory, preserving output ownership for the host user.
5. Test native Linux GigE discovery and capture networking, with explicit host
   firewall configuration. The image must not disable the host firewall.
6. Test Windows/Docker Desktop/WSL2 access to the camera network separately.
   Successful offline processing on Windows does not establish live GigE access.

There is no Dockerfile yet, and no Windows/container capture support claim.
