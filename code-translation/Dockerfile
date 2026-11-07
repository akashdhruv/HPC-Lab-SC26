# Image of code-translation: the compilers and tools the oracle needs. The repository is
# mounted at run time by dev/bin/container; the image holds no copy of it.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends gfortran g++ make python3 \
    && rm -rf /var/lib/apt/lists/*

ENV HOME=/tmp
