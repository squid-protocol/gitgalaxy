# cics-banking-sample-application-cbsa (port-invariance pairs)

cobol/: ABNDPROC, DBCRFUN, INQACC, UPDCUST from <https://github.com/cicsdev/cics-banking-sample-application-cbsa> at `417334533178ab6e753cc64b0e0e5cf0b4952704`, unmodified, under that project's license (EPL-2.0; licence files copied alongside).

java/: each program's deterministic Java port (service class), emitted by GitGalaxy's det-port translator (`tests/tools/det_port.py run`) from that source and proven equivalent to it.

Regenerate with `python tests/tools/port_invariance.py fixture --work <det sweep work dir>`.
