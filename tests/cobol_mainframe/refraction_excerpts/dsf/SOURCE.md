# dsf (excerpt)

5 files from <https://github.com/navikt/DSF> at `faade4961e316c89e8c312456bae411c63f1c482`, unmodified, under that project's license (MIT; LICENSE.md copied alongside).

The DSF administration slice: control program R0010420 (XCTLs to R0010421-R0010427 and back to the menu R0010301, RETURN TRANSID through a DCL'd field), R0010423 (one of its table-maintenance transactions) and R001TK62 (XCTL PROGRAM(PROGRAM_ID), a program name held in a variable). GML/FRMERK.cobol is one of DSF's 7 COBOL batch programs (a 1985 report writer), so the forge has COBOL to refract.

Regenerate with `python tests/tools/mainframe_corpus.py excerpt dsf` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
