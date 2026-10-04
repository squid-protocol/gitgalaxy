# #3624: GnuCOBOL 3.1 with BDB indexed files -- the COBOL side of the equivalence harness: the ORACLE every proof
# compares the Java against. #4309: pinned, so every proof names the same oracle -- the base by digest, GnuCOBOL by
# its exact Debian package version. The harness (tests/tools/equivalence_oracle.py) reads these three values from this
# file, compares them with the image it runs (its labels, `cobc --version`, dpkg) and records the result with each
# proof. Changing any of them changes the oracle: bump them together, then re-prove (evidence records go stale).
ARG BASE=debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251
FROM ${BASE}
ARG BASE
ARG GNUCOBOL=3.1.2-5+b1
ARG COBC="cobc (GnuCOBOL) 3.1.2.0"
RUN apt-get update && apt-get install -y --no-install-recommends gnucobol3=${GNUCOBOL} libcob4=${GNUCOBOL} gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/* \
 && test "$(cobc --version | head -n 1)" = "${COBC}"
LABEL org.gitgalaxy.oracle.base="${BASE}" org.gitgalaxy.oracle.gnucobol3="${GNUCOBOL}" org.gitgalaxy.oracle.cobc="${COBC}"
WORKDIR /work
