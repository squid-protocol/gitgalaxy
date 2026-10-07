# cics-async-api-credit-card-application-example (excerpt)

10 files from <https://github.com/cicsdev/cics-async-api-credit-card-application-example> at `c32c52fcfd8d587b352f67959a5dfb0d11dbd8bb`, unmodified, under that project's license (Apache-2.0; LICENSE copied alongside).

IBM's CICS asynchronous API credit-card application: two front-end programs that fan out to the same eight CICS services, ASYNCPNT in parallel (EXEC CICS RUN TRANSID / FETCH CHILD / FETCH ANY, channels and containers) and SEQPNT in sequence (LINK), plus the services GETNAME, GETADDR, GETPOL, GETSPND, CRDTCHK, CSSTATUS, CSSTATS2 and UPDCSDB. The repository ships no copybooks, BMS maps or CSD deck; the CICS resources are bundle definitions.

Regenerate with `python tests/tools/mainframe_corpus.py excerpt cics-async-api-credit-card-application-example` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.
