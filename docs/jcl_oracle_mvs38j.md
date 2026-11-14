# JCL oracle tier 2: the MVS 3.8J box (#8414)

**Internal use only until counsel answers Q16.** No MVS 3.8J result is published. Never z/OS on Hercules (#6492); never
TK4- / TK5 (they bundle third-party CBT add-ons under mixed terms). The system is built from IBM's own distribution
tapes, using IBM base components only (JES2, IEFBR14, IEBGENER, IEBCOPY, IEHPROGM, IDCAMS of that era).

## What is built

| Piece | Source | Pin |
|---|---|---|
| SDL Hyperion 4.x (Q Public License 1.0) | `github.com/SDL-Hercules-390/hyperion`, built by `tests/tools/box/mvs38j/Dockerfile` | `ARG HYPERION_TAG` (Release_4.9.1; 4.9.1.1-SDL ran `hercules --version` 2026-11-13) |
| IBM starter system tapes | `jaymoseley.com/hercules/downloads/archives/vs2StarterTapes.tar.gz` | md5 `7c12c99c387193c8650f8ef78b4771c3` |
| IBM MVS 3.8J distribution tapes | `.../vs2DistributionTapes.tar.gz` | md5 `ec9f1c8672bd406a4ff7bc00f139f5bc` |
| Jay Moseley's sysgen scripts, jobstreams, configs | `.../mvsInstallationResources.tar.gz` | md5 `129898e0f0881078448358553bc6b4c1` |

The md5s are the ones Jay Moseley publishes in "Installing MVS 3.8j - Gathering Prerequisite Materials" (V8, May 2024).
`mvs38j.sh tapes` refuses and deletes an archive whose md5 differs.

## Commands (on nyx; never CI)

```bash
tests/tools/box/heavy-run.sh tests/tools/box/mvs38j/mvs38j.sh image   # build the Hyperion image (~25 s warm)
tests/tools/box/mvs38j/mvs38j.sh tapes     # fetch + verify + unpack the three archives into $MVS38J_WORK/dl/
tests/tools/box/mvs38j/mvs38j.sh stage     # lay conf/ jcl/ tape/ sajobs/ and the helper scripts out under $MVS38J_WORK
tests/tools/box/mvs38j/mvs38j.sh dasd starter   # empty DASD volumes of one stage (starter | dlibs | sysgen | user), via dasdinit in the image
tests/tools/box/mvs38j/mvs38j.sh sysgen smp1 [--tape VOLSER=FILE ...]   # starter-system IPL, SMP jobs over the 3215 console (smp2 likewise)
tests/tools/box/mvs38j/mvs38j.sh sysgen starter   # START1 + SPOOL0: DASDI then DUMP/RESTORE per volume, driven over the console (~11 s)
tests/tools/box/mvs38j/mvs38j.sh status    # container and tape state
tests/tools/box/mvs38j/mvs38j.sh start     # needs $MVS38J_WORK/conf/mvs.conf (the generated system)
tests/tools/box/mvs38j/mvs38j.sh run DECK  # submit a deck, wait for the job, print the parsed JES2 log as JSON
tests/tools/box/mvs38j/mvs38j.sh stop
```

`MVS38J_WORK` defaults to `/srv/storage_16tb/projects/gitgalaxy/mvs38j`, outside the repo; the system image is never
committed. `start` binds the card-reader socket (3505) and the console (3270) to 127.0.0.1 only. Scratch containers are
named `churn-<issue>-<n>` (`MVS38J_NAME`).

## System generation (staging and the starter stage automated; the rest not yet)

`stage` and `dasd` are verified (2026-11-13): all four stages' volumes create in about 4 GB of sparse files, answering "n" to
`create.dasd.sh`'s compression prompt. Moseley's configs use paths relative to `$MVS38J_WORK`, which `stage` reproduces.

Jay Moseley's sysgen is staged: starter system (stand-alone programs), then IPL of the starter system for the SMP4 builds
(`smp1.cnf`, `smp2.cnf`), stage 1 (`jcl/sysgen01.jcl`), stage 2 (`stage2.rexx`, `stage2.awk`), then user mods.

`tests/tools/box/mvs38j/sysgen.py` (stdlib, host side) drives it: it starts Hercules in the image with `docker run -i`, writes console commands to
its stdin and reads its log, which carries the integrated 1052-C console (input prefixed `/`). `mvs38j.sh sysgen starter`
is verified (2026-11-14): for each volume it IPLs the stand-alone DASDI from the starter tape (tape 280 for START1, 281 for
SPOOL0), waits for PSW `...FFFF`, sends `/`, answers the `IBC105A DEFINE INPUT DEVICE` prompt with `/input=1442,00c`, waits for
PSW `...1111`, then does the same with DUMP/RESTORE (`/input=1442,00d`, done at PSW `...EEEE`). Both volumes then carry their
labels. A stand-alone error message (`IBC...E`, `CONTROL STATEMENT ERROR`) or a timeout stops the stage.

`tests/tools/box/mvs38j/sysgen.py condcode FILE JOB|ALL [--expect STEP=CC ...]` is the `condcode.rexx` check in Python: it reads `IEF142I` (step
executed, completion code) and `IEF272I` (step not executed) from a Hercules printer file and exits 1 on an unexpected code.

`tests/tools/box/mvs38j/console.py` is the telnet client for the 3215 console at 001F (stdlib; port 3270, published on
127.0.0.1 only). It refuses every telnet option but binary, echo and suppress-go-ahead, strips IAC sequences, and collects lines
on a thread; a prompt with no trailing newline (`IEA101A`) matches too. It identifies itself as `ANSI` when Hercules asks for the
TERMINAL-TYPE (`IAC WILL 24`, then `SB 24 0 ANSI`): without that Hercules never attaches the 3215 and the IPL stops at wait
state 21 (`IEA304W`). `sysgen.py smp1|smp2` starts Hercules with `conf/smpN.cnf`, waits for `HHC01024I` (Docker's port proxy
accepts a connection before Hercules listens, then drops it), `ipl 150`, answers `r 0,clpa` and `r 0,format,noreq` (a fresh
spool also asks `$HASP436`, answered `r NN,y`; a warm one does not), then feeds each deck with `devinit 12`, waits for
`$HASP395 <job> ENDED`, and stops on `IEF452I` (JCL error), `IEA...E` / `IEC...E` / ABEND. Verified live (2026-11-14): the
job's tape DD gets `*nn IEF238D <job> - REPLY DEVICE NAME`, answered `r nn,170` (the config's first 3420); each volume then asks
`*IEC501A M 170,<volser>,...` with no reply id, satisfied by `devinit 170 <file>` (`--tape VOLSER=FILE`; smp4p44 mounts
`MVS38J` = `tape/zdlib1.het`, then `T74172` = `tape/smp4b.het`). Jobs: smp1 runs `jcl/smp4p44.jcl` only and needs an IPL
after it (`$HASP104`); smp2 runs the reader-preloaded `smpmount.jcl` confirm (`IEF166D REPLY Y/N`, answered `r nn,y`), then
`smpjob00..07`. smp1's IEHDASDR step needs `v 148,offline` (149, 14A) first, else `IEH824I ... DEVICE NOT OFF-LINE`; the console
echoes nothing for VARY, so the driver sleeps. Its `IEH841D CONFIRM REQUEST TO INITIALIZE` is answered `r nn,u`. smp2's volumes
are built in (`DEFAULT_TAPES`: `MVS38J` `tape/zdlib1.het`, `T74172` `tape/smp4b.het`, `PTFS20` `tape/ptfs.het`, `J90012`
`tape/j90012.het`; `--tape` overrides) and smpjob01 asks for its mount as `IEF233A M 170,<volser>`. `MVS38J_CONSOLE_LOG=file`
writes the console transcript, the way to see why a stage stalls. Finally the condcode check runs over the printer bytes
written during the stage (the file is `noclear`, so it accumulates across runs; the stage reads only the new part) and refuses
any `IEHnnnI ... TERMINATED`. Traps: repeated smp1 runs fill `START1` (`E37` on `SYS1.LINKLIB`): recreate the starter DASD
and rerun `sysgen starter` first. smp2 ran live through `$HASP395 ENDED` for every job (2026-11-14); `SMPJOB00` `DLBUCL`
ended CC 8 on every run: its `UCLIN PTS` / `DEL SYS .` deletes a system entry that a just-scratched PTS never has (`HMA2532`,
`HMASMP` RC 08), by design of the deck. `sysgen.SMP2_EXPECTED` lists the four steps allowed above CC 0 with a reason each
(`SMPJOB00` `DLBUCL` 8; `SMPJOB03` `DLBUCL4`, `SMPJOB05`, `SMPJOB06` 4: link-edit warnings and a REJECT of sysmods never
applied); every other smp2 step must end CC 4 or less, and a listed step must match exactly.

## Job runner

`tests/tools/box/mvs38j/runner.py` (stdlib, host side; **fixture-tested only, not yet run against a live 3.8J log**) is
reached through `mvs38j.sh run DECK [--timeout S] [--host H] [--port P] [--printer FILE]`. It needs a started box
(`mvs38j.sh start`). The deck's first card must be `//NAME JOB ...`; each line is padded to an 80-column card image and sent
to the socket reader on 127.0.0.1:3505, and the connection closing ends the deck. `--printer` defaults to the first 1403
printer of `$MVS38J_WORK/conf/mvs.conf`. The runner waits for `$HASP395 NAME ENDED` (or `IEF452I` JCL error), then prints JSON
with provenance `mvs38j-run`, per job: steps (`IEF142I` executed with its completion code; `IEF272I` / `IEF202I` not
executed), dataset dispositions (`IEF285I`), abends (`IEF450I`), the JCL-error flag and the SYSOUT line count. A message
it does not know is counted in `unparsed_ief`, never guessed. `runner.py parse PRINTER_FILE [JOB]` parses a captured
printer file without a box. Exit 1 on a timeout or a deck without a JOB card; 2 on a missing deck or usage error.
Results are internal only (Q16).

### Remaining slices (#8414)

1. Run `sysgen smp2` end to end with the expected codes (not re-run live after this change; the 2026-11-14 printer file
   shows every step inside the bound); the Hercules restart between smp1 and smp2.
2. Stage 1 and stage 2 (`sysgen01` output to `stage1.output`, `stage2.rexx`/`awk` port or call, the socket reader on 3505),
   then the user mods and `mvs.cnf` first IPL of the generated system.
3. Probe run: the era-compatible IBM-written scenarios through `mvs38j.sh run`, once the generated system IPLs; confirm the
   runner's message patterns against a live log; merge `sysgen.step_results` onto `runner.parse_log`.

## What this tier cannot test

IF / THEN / ELSE, JCLLIB, INCLUDE, SET, modern DFSORT / ICETOOL, Enterprise COBOL and CICS do not exist in MVS 3.8J.
They stay tier 1 (manual answers) until z/OS access (#6492).
