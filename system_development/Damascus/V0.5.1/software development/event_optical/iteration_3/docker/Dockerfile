# syntax=docker/dockerfile:1
ARG UBUNTU_IMAGE=ubuntu:24.04
FROM ${UBUNTU_IMAGE}
ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_JOBS=4
ARG OPENEB_COMMIT=9003b5416676e78ba994d912087486cfa94fae73

# Keep build tools in this first image for native SDK diagnostics/rebuilds.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git git-lfs build-essential cmake ninja-build pkg-config \
    python3 python3-dev python3-venv \
    libboost-all-dev libopencv-dev libusb-1.0-0-dev libeigen3-dev \
    libprotobuf-dev protobuf-compiler libhdf5-dev libglew-dev libglfw3-dev zlib1g-dev \
    libibverbs1 librdmacm1 iproute2 pciutils \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/event-optical-matplotlib \
    OPENEB_ROOT=/opt/openeb/build \
    ARENA_ROOT=/sdk/arena
WORKDIR /app
COPY pyproject.toml README.md requirements-build.txt requirements-reconstruction.txt requirements-analysis.txt /app/
RUN python -m pip install --no-cache-dir \
    -r requirements-build.txt -r requirements-reconstruction.txt -r requirements-analysis.txt
# Only the patch recipe is needed for the expensive SDK build layer.
COPY scripts/patch_openeb_evt3_boundary.py /opt/recipes/patch_openeb_evt3_boundary.py
RUN git clone --depth 1 --branch 5.2.0 --recurse-submodules \
    https://github.com/prophesee-ai/openeb.git /opt/openeb \
    && test "$(git -C /opt/openeb rev-parse HEAD)" = "$OPENEB_COMMIT" \
    && python /opt/recipes/patch_openeb_evt3_boundary.py /opt/openeb \
    && cmake -S /opt/openeb -B /opt/openeb/build -G Ninja \
       -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_INSTALL_PREFIX=/opt/openeb/install \
       -DPython3_EXECUTABLE=/opt/venv/bin/python \
       -Dpybind11_DIR="$(python -m pybind11 --cmakedir)" \
       -DCOMPILE_PYTHON3_BINDINGS=ON -DBUILD_TESTING=OFF -DBUILD_SAMPLES=OFF \
       -DLFS_DOWNLOAD_VALIDATION_RESOURCES=OFF \
       '-DCMAKE_CXX_FLAGS=-include cstdint -DH5Dread_chunk_vers=1' \
    && cmake --build /opt/openeb/build --parallel "$BUILD_JOBS" \
    && mkdir /opt/prophesee-plugin \
    && test -f /opt/openeb/build/lib/libhal_plugin_prophesee.so \
    && ln -s /opt/openeb/build/lib/libhal_plugin_prophesee.so /opt/prophesee-plugin/libhal_plugin_prophesee.so

COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/
COPY config/ /app/config/
COPY docs/ /app/docs/
COPY docker/ /app/docker/
RUN python -m pip install --no-cache-dir --no-deps . \
    && mkdir -p /opt/build-info \
    && python -m pip freeze > /opt/build-info/python-packages.txt \
    && dpkg-query -W > /opt/build-info/ubuntu-packages.txt \
    && git -C /opt/openeb rev-parse HEAD > /opt/build-info/openeb-commit.txt \
    && sed -i 's/\r$//' /app/docker/entrypoint.sh \
    && chmod +x /app/docker/entrypoint.sh
ENV PYTHONPATH=/app/src:/opt/openeb/build/py3 \
    LD_LIBRARY_PATH=/opt/openeb/build/lib:/opt/openeb/build/lib64 \
    MV_HAL_PLUGIN_PATH=/opt/prophesee-plugin \
    MV_HAL_PLUGIN_SEARCH_MODE=PLUGIN_PATH_ONLY \
    MV_FLAGS_EVT3_ROBUST_DECODER=1 \
    EVENT_OUTPUT_DIR=/data/recordings
# A build succeeds only after unit tests and actual native decoder regressions pass.
RUN python -m unittest discover -s /app/tests -p 'test_*.py' -v \
    && python /app/scripts/test_evt3_boundary.py
WORKDIR /data
ENTRYPOINT ["/bin/bash", "/app/docker/entrypoint.sh"]
CMD ["help"]
