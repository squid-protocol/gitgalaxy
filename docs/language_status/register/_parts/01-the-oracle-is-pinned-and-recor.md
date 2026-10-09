## The oracle is pinned and recorded (#4309)

`tests/equivalence/gnucobol.Dockerfile` pins the oracle, so every proof names the same GnuCOBOL:

| pinned | value |
|---|---|
| base image | `debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251` |
| `gnucobol3` / `libcob4` (Debian package) | `3.1.2-5+b1` |
| `cobc --version` | `cobc (GnuCOBOL) 3.1.2.0` (the build fails if the installed compiler prints anything else) |

The image carries the three values as labels (`org.gitgalaxy.oracle.*`). `tests/tools/equivalence_oracle.py` reads
the image a run uses -- its id, labels, `cobc --version` and the installed package -- and compares it with the pin.
Every proof report (`equivalence.py run`, the CALL and CICS harnesses, `cics_crucible.py` results and
`--report-dir` proofs) records that fingerprint under `oracle`, with `matches_pin` and any `mismatches`. A
mismatch (an image built before the pin, a `--build-arg` override) is a warning locally and stops the run under
`GITGALAXY_ORACLE_STRICT=1`, which the CICS crucible workflow sets. `gnucobol-db2.Dockerfile` builds `FROM` the
oracle image, so a Db2 case's image inherits the pin and its labels; it is built once and kept, so after the oracle
moves, `docker rmi gitgalaxy-gnucobol-db2:3` before the next Db2 run.

Moving the oracle is a deliberate change: bump the three `ARG`s together, rebuild, and re-prove (a changed oracle
makes every proof's evidence stale). If Debian drops the pinned package from `deb.debian.org` at a point release,
the pinned build fails (the weekly CICS crucible run notices); restore it from `snapshot.debian.org` rather than
taking whatever version is current.
