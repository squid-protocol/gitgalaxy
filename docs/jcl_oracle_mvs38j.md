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
tests/tools/box/mvs38j/mvs38j.sh sysgen stage1    # sysgen00 (ICKDSF init of the target volumes) + sysgen01 (stage 1 assembly), then hetget of stage1.output
tests/tools/box/mvs38j/mvs38j.sh sysgen stage2    # stage1.output -> jcl/stage2.jcl (Moseley's awk, ported), SYSGEN1..6 released one by one (verified live 2026-11-19)
tests/tools/box/mvs38j/mvs38j.sh sysgen stage3    # sysgen02..06, USERMODS, FDZ1D02 on the starter, condcode check, starter shutdown (verified live 2026-11-19)
tests/tools/box/mvs38j/mvs38j.sh sysgen starter   # START1 + SPOOL0: DASDI then DUMP/RESTORE per volume, driven over the console (~11 s)
tests/tools/box/mvs38j/mvs38j.sh sysgen ipl [--probe DECK]   # first IPL of the generated system, optional probe job + live-log check (verified live 2026-11-19)
tests/tools/box/mvs38j/mvs38j.sh status    # container and tape state
tests/tools/box/mvs38j/mvs38j.sh start     # resident driver (sysgen.py serve): IPL (warm after the first), returns once JES2 is ready; needs the generated system
tests/tools/box/mvs38j/mvs38j.sh run DECK  # submit a deck, wait for the job, print the parsed JES2 log as JSON
tests/tools/box/mvs38j/mvs38j.sh stop      # SIGTERM to the driver: $P JES2, Z EOD, quiesce, quit (not a heavy step: do not wrap it in heavy-run.sh)
```

`MVS38J_WORK` defaults to `/srv/storage_16tb/projects/gitgalaxy/mvs38j`, outside the repo; the system image is never
committed. `start` binds the card-reader socket (3505) and the console (3270) to 127.0.0.1 only. Scratch containers are
named `churn-<issue>-<n>` (`MVS38J_NAME`).

## System generation (staging through the first IPL automated and verified live)

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
`HMASMP` RC 08), by design of the deck. `sysgen.SMP2_EXPECTED` lists the five steps allowed above CC 0 with a reason each
(`SMPJOB00` `IEHPROGM` 8, found on the 2026-11-14 fresh-volume run: `SCRATCH` of 53 `SYS1.A*` names a fresh SMP000 never held,
`IEH207I` DATA SET OR MEMBER NOT FOUND; `SMPJOB00` `DLBUCL` 8; `SMPJOB03` `DLBUCL4`, `SMPJOB05`, `SMPJOB06` 4: link-edit warnings and a REJECT of sysmods never
applied); every other smp2 step must end CC 4 or less, and a listed step must match exactly.

`sysgen.py smp2` runs `smpjob07` for two `$HASP395 ENDED` lines (`SMP_ENDED`): it submits a second job of the same name through the
internal reader (`LINK UTILITIES`) that relinks ICKDSF into the starter's `SYS1.LINKLIB`. Quitting Hercules after the first
`ENDED` left the starter with no ICKDSF, and the next stage's ICKDSF step abended `S806` (`IEA703I 806-4 ... MODULE ACCESSED ICKDSF`).

`sysgen.py stage1` (verified live 2026-11-14, from fresh volumes through `starter`, `smp1`, `smp2`) starts Hercules with
`conf/sysgen.cnf` (tape 170 = `tape/stage1.het`), IPLs the starter (`clpa`, `noreq`), sends the `attach` lines of `conf/sysgen.script`
(149 MVSRES, 14A MVS000, 14B SPOOL1, 14C PAGE00), runs `jcl/sysgen00.jcl` (3 jobs: it submits two continuation jobs through the internal
reader; each ICKDSF `INIT` asks `ICK003D REPLY U TO ALTER VOLUME`, answered `r nn,u`) and `jcl/sysgen01.jcl` (2 jobs: the stage 1
assembly, then a continuation job that copies the result to tape 170), checks the step codes (`STAGE1_EXPECTED`: `SYSGEN00 IEHPROGM`
and `SYSGEN01 CLEANUP` end CC 8 on a fresh build, as in Moseley's page) and extracts `stage1.output` from `tape/stage1.het`
with the image's `hetget -a` (`hetget`). `FDZ1D02` (ICKDSF R13) is not part of it: its `IEWL` step names the target master
catalog as `JOBCAT` (`IEF212I ... DATA SET NOT FOUND`, step not executed) until sysgen00 has defined it, so it belongs after the
target system exists (Moseley runs it last). Re-running a stage needs fresh volumes: `mvs38j.sh dasd starter|dlibs|sysgen` first.

`sysgen.py stage2` (verified live 2026-11-19, from fresh volumes through `starter`, `smp1`, `smp2`, `stage1`; 130 steps, SYSGEN1..6 each
ended) ports `stage2.awk` as `convert_stage1` (SYSGEN1..6 held with `TYPRUN=HOLD,TIME=1439` and the target master catalog as `JOBCAT`,
`EXPDT=99350` -> `00000`, SYSGEN6's `STEPY` -> `IEFBR14`, separator cards dropped), writes `jcl/stage2.jcl`, IPLs the starter again,
attaches the targets, feeds the deck and releases each job with `$A'SYSGENn'`, waiting for its `$HASP395 ENDED`. Traps found live:
(1) `$A` sent before `$HASP101 <job> HELD` answers `$HASP000 NOT HELD` and the job waits forever, so the driver waits for HELD, looking
from the deck's start (the reader queues the next job while the last one runs); (2) an `attach`ed volume is offline, and SYSGEN1's `LPA1`
step stops at `IEF238D REPLY DEVICE NAME` (`IEF247I ... 149 OFFLINE`), so the driver sends `v 149|14A|14B|14C,online`; (3) back-to-back
console lines overrun the 3215 input buffer (`HHC02913E COMM: Buffer overrun` closes the console), so they are paced 3 s apart.
`stage1.output` must come from a good `stage1` run on fresh volumes (1058265 bytes, 17 steps; a 199017-byte one was truncated after
SYSGEN1). `STAGE2_EXPECTED`: only `SYSGEN6 STEPZ1` (IEHPROGM SCRATCH of `SYS1.NUCLEUS(SYSCATLG)`, `IEH207I` not found) ends CC 8; nine
`LK` link-edit steps in SYSGEN1/2 end CC 4, within the bound; every other step ends CC 0. Re-running needs fresh volumes (SYSGEN1 creates the target datasets).

`sysgen.py stage3` (verified live 2026-11-19 on the stage 2 volumes: 7 decks, 209 steps, none not executed, none over CC 4) is
Moseley's "after stage 2" part (iSYSGENv8.htm, fetched 2026-11-19). It runs on the **starter** system, not on an IPL of the generated
one: it IPLs the starter with `conf/sysgen.cnf`, attaches and varies the target volumes online (as stage 2), and feeds `sysgen02`,
`sysgen03`, `sysgen04`, `sysgen05`, `sysgen06`, `usermods` and `fdz1d02` through the reader at 00C in that order, then shuts down
(`$p jes2`, `z eod`, `quiesce`, Hercules `quit`). Each deck is done when its `$HASP395 ENDED` lines have appeared: 1, 1, **2**
(sysgen04 submits a continuation job of the same name), 1, 1, **7** (USERMODS is seven jobs in one file), **2** (FDZ1D02 builds and
submits its second job). Tapes are answered by the volser the deck names (`DD ... VOL=SER=`): `PVTMAC` -> `tape/apvtmacs.het`,
`SMPPTF` -> `tape/usermods.het`, `MVS38J` -> `tape/dz1d02.het` (it overrides `DEFAULT_TAPES`' `zdlib1`); sysgen04's `IEC507D REPLY 'U'`
is answered by the existing `USE_ASK_RE`. `STAGE3_EXPECTED` is empty: no step is allowed above CC 4 (Moseley lists CC 4 for sysgen06's
HMASMP and four USERMODS link-edit steps). It takes about 25 min (`usermods` alone ~7 min); it changes the volumes, so keep a copy of
`$MVS38J_WORK/dasd` before running (there is no re-run without fresh volumes). Trap found live: the shutdown wait patterns were first
guessed (`$HASP085`) and timed out after every deck had passed; the real lines (`IEF142I JES2 JES2 - STEP WAS EXECUTED` after
`$p jes2`, `IEE334I HALT EOD SUCCESSFUL` after `z eod`) were read from a second starter IPL over the finished volumes and pinned in
`JES2_STOPPED_RE` / `EOD_DONE_RE`. **Not verified in one continuous run:** the decks ran in one run, the corrected shutdown in the
second IPL; `quiesce` prints nothing. The first IPL of the generated system is `sysgen ipl`, below.

### ipl (verified live 2026-11-19)

`mvs38j.sh sysgen ipl [--probe DECK]` writes `conf/mvs.conf` from Moseley's `conf/mvs.cnf` (the 3270 master console at 010 is
commented out and the 1052-C at 009 enabled, so `/` lines on Hercules stdin are console input; the 3505 reader binds every
interface so docker's loopback publish reaches it), IPLs unit 150 and answers by message: `IEA101A` `r 0,clpa`, `IFB010D`
`r N,u`, `$HASP426` `r N,format,noreq`, `$HASP479` `r N,y`, `$HASP436` `r N,y`; ready is `$HASP099 ALL AVAILABLE FUNCTIONS
COMPLETE` (~105 log lines). A first IPL formats the spool; once it has finished, `ipl.done` in `$MVS38J_WORK` makes every later
IPL warm: `$HASP426` is answered `r N,noreq` (Moseley's normal-start-up page; answering `format,noreq` on a formatted spool
hung with no further prompt, 600 s). Then it shuts down (`$p jes2`, `z eod`, `quiesce`).

* **SYSCPK is needed.** SYSC.LINKLIB and SYSC.PROCLIB are on the SYSCPK 3350 (unit 253). Without it the IPL stops at
  `IEA317A`; a blank 3350 is refused with `IEA318I ... UNACCEPTABLE`. `mvs38j.sh tapes` downloads `SYSCPK.tar.gz` (md5 pinned) and
  `ipl` copies `syscpk.3350` into `dasd/`.
* `IEA357I INVALID - MODULE IGNORED` lines during CLPA are benign (Moseley).
* **Probe (`--probe DECK`)**: the deck goes to the 3505 reader through `runner.submit`; `ipl` waits for `$HASP395 JOB ENDED`,
  reads the printer file (`runner.parse_log`) and compares its (step, condition code) pairs with the `IEFACTRT` lines the console
  printed live (`sysgen.live_steps`). The live console carries `IEFACTRT` step accounting, not the `IEF142I` of the printer
  listing, and the two agree. Run: two-step `IEFBR14` job, both CC 0, 115 log lines, exit 0. This is the one deck run so far: the
  runner's other patterns (`IEF272I`, `IEF450I`, `IEF285I`, the JCL error) are still fixture-tested only.

## Job runner

`tests/tools/box/mvs38j/runner.py` (stdlib, host side; **checked against a live 3.8J log (2026-11-19, `start` + `run`): `IEF142I` step lines with a zero and a non-zero (4) code, `IEF272I`, `IEF450I` abend (S806, an unknown program), `IEF452I` JCL error; `IEF285I` dispositions CATALOGED / UNCATALOGED / PASSED / DELETED / KEPT too**) is
reached through `mvs38j.sh run DECK [--timeout S] [--host H] [--port P] [--printer FILE]`. It needs a started box
(`mvs38j.sh start`, which runs `sysgen.py serve`: a resident host process that owns Hercules' console pipe, IPLs, writes `box.ready` and `box.pid` in the work dir and, on SIGTERM, stops JES2 cleanly so the next start is a warm IPL; its log is `box.log`). The deck's first card must be `//NAME JOB ...`; each line is padded to an 80-column card image and sent
to the socket reader on 127.0.0.1:3505, and the connection closing ends the deck. `--printer` defaults to the first 1403
printer of `$MVS38J_WORK/conf/mvs.conf`. The runner waits for `$HASP395 NAME ENDED` (a JCL-error job ends with `$HASP396 NAME TERMINATED` instead; both count), then prints JSON
with provenance `mvs38j-run`, per job: steps (`IEF142I` executed with its completion code; `IEF272I` / `IEF202I` not
executed), dataset dispositions (`IEF285I`), abends (`IEF450I`), the JCL-error flag and the SYSOUT line count. A message
it does not know is counted in `unparsed_ief`, never guessed. `runner.py parse PRINTER_FILE [JOB]` parses a captured
printer file without a box. Exit 1 on a timeout or a deck without a JOB card; 2 on a missing deck or usage error.
Results are internal only (Q16).

Live `IEF285I` (2026-11-19, a NEW,CATLG then OLD,DELETE deck): a disposition line may end in a `*--------0` marker, which the first
regex rejected (only the marker-less line parsed); `VOL SER NOS=` lines are not dispositions. Live findings (2026-11-19, four probe decks through `run`): the JCL-error line is `IEF452I NAME    JOB NOT RUN - JCL ERROR` with no
` - ` after the job name (the first regex needed it, so the job never read as ended); the abended step has an `IEF450I` and no
`IEF142I` (its record is the abend, not a step with a code); the printer file also carries `IEF236I/237I/373I/374I/375I/376I/472I/643I`,
now known informational lines (`unparsed_ief` is 0 on all four decks). Trap: wrapping `stop` in `heavy-run.sh` queued it behind
another worker's slot and the box ran on.

### Remaining slices (#8414)

1. Hercules restart between smp1 and smp2 (each stage is its own Hercules run today; verified live on fresh volumes).
2. Moseley's "Customizing MVS" page (not read beyond the IPL replies).
3. Probe run of the era-compatible IBM-written scenarios. (`sysgen.step_results` now reads through `runner.parse_log`'s `step_log`: one parser of the printer listing.)

## What this tier cannot test

IF / THEN / ELSE, JCLLIB, INCLUDE, SET, modern DFSORT / ICETOOL, Enterprise COBOL and CICS do not exist in MVS 3.8J.
They stay tier 1 (manual answers) until z/OS access (#6492).
