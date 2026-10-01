# Benchmark: COACTUPC ported by the agent porter (held, not adopted)

CardDemo's account update (COACTUPC, 4,236 COBOL lines), ported by the agent porter
(`gitgalaxy/tools/cobol_to_java/agent_porter.py`) and **proven on attempt 1** against the 54 scenarios of
`tests/equivalence/carddemo-acctupdate`: 70 turns, 5 proofs run by the agent itself, $6.13; then proven again,
independently, by the porting loop (`loop.md`). The single-shot porter could not port it: a 155k-token prompt, and
an answer longer than one message, of which only the tail was captured.

Held as a benchmark for the generator-first pipeline (deterministic frame and statements, the model filling what is
left), not adopted as the case's port: the agent direction is paused in favour of bring-your-own-model.

Caveat on this run: it used the agent porter's first sandbox, in which Claude Code still had a shell (read-only
commands approved by itself). The transcript was audited: the agent read only its workspace and the proof reports,
never this repository or any committed port (none existed for COACTUPC); it used the shell for scratch scripts in
/tmp (generating Java lookup tables from CSLKPCDY). The sandbox now has no shell (the `prove` MCP tool).

- `CoactupcService.java` -- the port, as the agent left it
- `NOTES.md` -- its notes: defects of the original kept, facts contradicted
- `transcript.jsonl.gz` -- the whole session (Claude Code stream-json)
- `loop.md` -- the porting loop's record
