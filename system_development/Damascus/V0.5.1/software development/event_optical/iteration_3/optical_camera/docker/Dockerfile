# syntax=docker/dockerfile:1
FROM ubuntu:24.04
ARG ACCEPT_SPINNAKER_EULA=false
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ca-certificates libgomp1 \
    libswscale7 libavcodec60 libavutil58 libavformat60 \
    && rm -rf /var/lib/apt/lists/*
# Vendor installers stay in a temporary build mount, outside the image layers.
RUN --mount=type=bind,source=vendor,target=/vendor,readonly \
    mkdir -p /tmp/spinnaker /tmp/pyspin \
    && tar -xzf /vendor/spinnaker-4.4.0.246-noble-amd64-pkg.tar.gz -C /tmp/spinnaker \
    && tar -xzf /vendor/spinnaker_python-4.4.0.246-cp312-cp312-linux_x86_64.tar.gz -C /tmp/pyspin \
    && apt-get update \
    && test "$ACCEPT_SPINNAKER_EULA" = true \
    && printf '%s\n' \
       'libgentl libspinnaker/accepted-flir-eula boolean true' \
       'libgentl libspinnaker/analytics-consent boolean false' \
       | debconf-set-selections \
    && apt-get install -y --no-install-recommends \
       /tmp/spinnaker/spinnaker-4.4.0.246-noble-amd64/libgentl_4.4.0.246_amd64.deb \
       /tmp/spinnaker/spinnaker-4.4.0.246-noble-amd64/libspinnaker_4.4.0.246_amd64.deb \
       /tmp/spinnaker/spinnaker-4.4.0.246-noble-amd64/spinupdate_4.4.0.246_amd64.deb \
       /tmp/spinnaker/spinnaker-4.4.0.246-noble-amd64/libspinvideo_4.4.0.246_amd64.deb \
    && ldconfig \
    && mkdir -p /tmp/.config/spinnaker \
    && printf '%s\n' '<?xml version="1.0" encoding="utf-8"?>' \
       '<PrivacyConfig><Disabled>true</Disabled></PrivacyConfig>' \
       > /tmp/.config/spinnaker/privacy.xml \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir \
       /tmp/pyspin/spinnaker_python-4.4.0.246-cp312-cp312-linux_x86_64.whl numpy pillow \
    && find /opt/venv -name '_PySpin*.so' -exec ldd {} \; \
    && /opt/venv/bin/python -c 'import PySpin, numpy; print("PySpin import OK; NumPy", numpy.__version__)' \
    && mkdir -p /opt/build-info \
    && /opt/venv/bin/python -m pip freeze > /opt/build-info/python-packages.txt \
    && dpkg-query -W > /opt/build-info/debian-packages.txt \
    && sha256sum /vendor/*.tar.gz > /opt/build-info/vendor-sha256.txt \
    && rm -rf /tmp/spinnaker /tmp/pyspin /var/lib/apt/lists/*
ENV PATH="/opt/venv/bin:${PATH}" HOME=/tmp PYTHONUNBUFFERED=1
# SDK creates XML/cache subdirectories during Init(). Runtime UID varies by host.
# Sticky bit protects existing entries, matching /tmp semantics; container-local only.
RUN chmod 1777 /tmp/.config/spinnaker
COPY discover.py /app/discover.py
COPY capture.py /app/capture.py
COPY tests /app/tests
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN python3 -m compileall -q /app && /opt/venv/bin/python -m unittest discover -s /app/tests -v
WORKDIR /tmp
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
CMD ["--list"]
