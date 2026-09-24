# cics-genapp (excerpt)

7 files from <https://github.com/cicsdev/cics-genapp> at `f6f3f4b2580d31b7d8dcc31ce3e3676f4cceaaaa`, unmodified, under that project's license (EPL-2.0; LICENSE copied alongside).

A multi-region CICS slice: LGTESTP1 (the 3270 motor-policy menu on SSMAP, which LINKs the business program LGIPOL01), LGIPOL01 (LINKs the data program), LGIPDB01 (DB2 policy inquiry with EXEC SQL INCLUDEs), their COMMAREA / policy copybooks, SSMAP.bms (whose symbolic map is not shipped, #3490), and cdef122.jcl: the DFHCSDUP deck that makes LGIPOL01 remote on AOR1 and LGIPDB01 remote on DOR1 (#3494).

Regenerate with `python tests/tools/mainframe_corpus.py excerpt cics-genapp` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
