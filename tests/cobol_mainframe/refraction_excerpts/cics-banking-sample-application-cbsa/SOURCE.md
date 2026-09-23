# cics-banking-sample-application-cbsa (excerpt)

13 files from <https://github.com/cicsdev/cics-banking-sample-application-cbsa> at `417334533178ab6e753cc64b0e0e5cf0b4952704`, unmodified, under that project's license (EPL-2.0; LICENSE, NOTICES copied alongside).

BANKDATA (batch, dead CALC-DAY-OF-WEEK, OPEN OUTPUT behind A010), BNK1CAC (CICS SECTIONs, dead POPULATE-TIME-DATE) and ABNDPROC, with their copybooks -- including BANKDATA's EXEC SQL INCLUDEd DB2 DECLARE TABLE members ACCDB2/CONTDB2 (#3344). Plus three BMS maps (#3347): BNK1CAM (the map BNK1CAC COPYs; an INITIAL literal continued mid-word), BNK1ACC (OCCURS=10) and BNK1UAM (PICOUT).

Regenerate with `python tests/tools/mainframe_corpus.py excerpt cics-banking-sample-application-cbsa` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
