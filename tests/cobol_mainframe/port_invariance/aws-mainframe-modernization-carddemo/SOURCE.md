# aws-mainframe-modernization-carddemo (port-invariance pairs)

cobol/: CBACT03C, CBCUS01C, CBTRN01C, COBTUPDT, COUSR01C, COUSR03C, CSUTLDTC from <https://github.com/aws-samples/aws-mainframe-modernization-carddemo> at `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e`, unmodified, under that project's license (Apache-2.0; licence files copied alongside).

java/: each program's deterministic Java port (service class), emitted by GitGalaxy's det-port translator (`tests/tools/det_port.py run`) from that source and proven equivalent to it.

Regenerate with `python tests/tools/port_invariance.py fixture --work <det sweep work dir>`.
