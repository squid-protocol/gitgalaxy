# SDL Hyperion (Q Public License 1.0) built from the pinned release tag, for the MVS 3.8J JCL oracle (#8414).
# No MVS image is baked in: the system is generated into a host directory by mvs38j.sh and mounted at /mvs.
FROM debian:12-slim
ARG HYPERION_TAG=Release_4.9.1
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential autoconf automake libtool libltdl-dev m4 flex gawk git ca-certificates libbz2-dev zlib1g-dev netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${HYPERION_TAG}" https://github.com/SDL-Hercules-390/hyperion.git /src/hyperion \
    && cd /src/hyperion && ./configure --prefix=/opt/hercules --enable-optimization=yes \
    && make -j"$(nproc)" && make install \
    && rm -rf /src
ENV PATH=/opt/hercules/bin:$PATH LD_LIBRARY_PATH=/opt/hercules/lib
WORKDIR /mvs
CMD ["hercules", "-f", "/mvs/conf/mvs.conf", "--daemon"]
