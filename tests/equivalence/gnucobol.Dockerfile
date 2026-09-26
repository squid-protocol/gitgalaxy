FROM debian:bookworm-slim
# #3624: GnuCOBOL 3.1 with BDB indexed files -- the COBOL side of the equivalence harness
RUN apt-get update && apt-get install -y --no-install-recommends gnucobol3 gcc libc6-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /work
