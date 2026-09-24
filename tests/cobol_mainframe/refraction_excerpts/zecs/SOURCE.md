# zecs (excerpt)

5 files from <https://github.com/walmartlabs/zECS> at `6d6bcbbc89c9be086a58cb7ad2ff4d702e873d02`, unmodified, under that project's license (Apache-2.0; LICENSE copied alongside).

The HLASM CICS slice: ZECSNC (DFHEIENT entry; ASSIGN, ABEND, RECEIVE, DEFINE DCOUNTER checked by `OC EIBRESP,EIBRESP`, START TRANSID from a DS field, WRITEQ TD) and ZECS002 (ABEND through a DC constant, VERIFY), the CSDZECS.rdo member that defines them, and the CSDZECS.jcl job that feeds it to DFHCSDUP. ECS001.cbl is the COBOL side: a CICS web client (WEB OPEN / CONVERSE / CLOSE) whose `MOVE DFHVALUE(DELETE) TO METHOD-CDVA` moves a CICS translator constant, not a data item (the zECS census finding).

Regenerate with `python tests/tools/mainframe_corpus.py excerpt zecs` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
