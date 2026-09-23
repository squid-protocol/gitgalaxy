# aws-mainframe-modernization-carddemo (excerpt)

20 files from <https://github.com/aws-samples/aws-mainframe-modernization-carddemo> at `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e`, unmodified, under that project's license (Apache-2.0; LICENSE, NOTICE copied alongside).

CBACT01C (batch SELECT/OPEN lineage, with READACCT.jcl) and COCRDLIC (CICS, two dynamic CALLs, a BMS symbolic-map copybook), with their copybooks. Plus COCRDLI.bms (#3347), the map that symbolic-map copybook is generated from, so the differential checks one against the other. Plus two CSD decks (#3356): CARDDEMO.CSD (the FILE -> DSNAME definitions READACCT.jcl's dataset joins to, an extrapartition TDQUEUE, LIBRARY) and CRDDEMOD.csd (DB2TRAN -> DB2ENTRY -> PLAN). Plus CORPT00C (#3352/#3353): SEND/RECEIVE MAP bound to CORPT00.bms, and an EXEC CICS WRITEQ TD QUEUE('JOBS') (the internal-reader queue), with its map and copybooks.

Regenerate with `python tests/tools/mainframe_corpus.py excerpt aws-mainframe-modernization-carddemo` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
