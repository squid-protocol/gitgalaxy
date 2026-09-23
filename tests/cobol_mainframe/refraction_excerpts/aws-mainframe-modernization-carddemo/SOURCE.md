# aws-mainframe-modernization-carddemo (excerpt)

14 files from <https://github.com/aws-samples/aws-mainframe-modernization-carddemo> at `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e`, unmodified, under that project's license (Apache-2.0; LICENSE, NOTICE copied alongside).

CBACT01C (batch SELECT/OPEN lineage, with READACCT.jcl) and COCRDLIC (CICS, two dynamic CALLs, a BMS symbolic-map copybook), with their copybooks. Plus COCRDLI.bms (#3347), the map that symbolic-map copybook is generated from, so the differential checks one against the other.

Regenerate with `python tests/tools/mainframe_corpus.py excerpt aws-mainframe-modernization-carddemo` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
