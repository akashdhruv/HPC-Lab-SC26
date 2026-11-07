# Toolchain for mxp-optimization when RAPTOR is not installed natively: Ubuntu 24.04, OpenMPI,
# LLVM/clang 20, MPFR, RAPTOR and OpenEvolve built from the dev/tools submodules.
# Build from mxp-optimization/; the repository is mounted at run time by dev/bin/box.

FROM ubuntu:24.04 AS toolchain

ARG LLVM_VER=20
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates wget gnupg lsb-release software-properties-common \
        build-essential make cmake ninja-build git binutils \
        openmpi-bin libopenmpi-dev libmpfr-dev python3 python3-venv \
    && wget -qO /tmp/llvm.sh https://apt.llvm.org/llvm.sh \
    && bash /tmp/llvm.sh ${LLVM_VER} \
    && apt-get install -y --no-install-recommends llvm-${LLVM_VER}-dev libclang-${LLVM_VER}-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/llvm.sh

FROM toolchain AS raptor

ARG LLVM_VER=20
COPY dev/tools/RAPTOR /opt/src/RAPTOR

RUN cmake -S /opt/src/RAPTOR -B /tmp/build -G Ninja \
        -DLLVM_DIR=/usr/lib/llvm-${LLVM_VER}/lib/cmake/llvm \
        -DCMAKE_INSTALL_PREFIX=/opt/raptor-install \
        -DCMAKE_BUILD_TYPE=Release -DRAPTOR_MLIR=OFF \
    && ninja -C /tmp/build install \
    && rm -rf /tmp/build

FROM toolchain

COPY --from=raptor /opt/raptor-install /opt/raptor-install
COPY dev/tools/OpenEvolve /opt/src/OpenEvolve
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir /opt/src/OpenEvolve pyyaml

ENV RAPTOR_INSTALL_DIR=/opt/raptor-install \
    PY=/opt/venv/bin/python \
    PATH=/opt/venv/bin:$PATH \
    OMPI_ALLOW_RUN_AS_ROOT=1 \
    OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
    HOME=/tmp

WORKDIR /work/mxp-optimization
