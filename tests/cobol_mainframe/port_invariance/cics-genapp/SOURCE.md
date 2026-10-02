# cics-genapp (port-invariance pairs)

cobol/: LGAPVS01 from <https://github.com/cicsdev/cics-genapp> at `f6f3f4b2580d31b7d8dcc31ce3e3676f4cceaaaa`, unmodified, under that project's license (EPL-2.0; licence files copied alongside).

java/: each program's deterministic Java port (service class), emitted by GitGalaxy's det-port translator (`tests/tools/det_port.py run`) from that source and proven equivalent to it.

Regenerate with `python tests/tools/port_invariance.py fixture --work <det sweep work dir>`.
