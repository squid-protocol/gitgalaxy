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
tests/tools/box/mvs38j/mvs38j.sh sysgen custom   # PUB000/PUB001 init, user catalogs, TSO ids, TSO apps (MVS00..MVS03); needs `dasd user` first (run live 2026-11-20: 76 steps, all 0000)
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

### custom (read from Moseley's iCUSTv8 page 2026-11-20; run live the same day: 4 decks, 76 steps, every one 0000)

`mvs38j.sh dasd user` first creates `pub000.3380` and `pub001.3390`. `mvs38j.sh sysgen custom` then IPLs the generated system
(first or warm), sends the `attach` lines of `conf/mvs.script` (the two volumes are not initialized, so `mvs.cnf` has them
commented out), and submits Moseley's MVS00 (ICKDSF init, then a CLASS S continuation that varies both online and imports the
SYSCPK catalog), MVS01 (user catalogs and aliases; sets the master catalog update password SYSPROG), MVS02 (HMVS01 and
HMVS02, 15 steps each) and MVS03 (RPF, QUEUE, REVIEW, DATE from `tape/tsoaps.het`, mounted at the unit the `IEC501A` names, plus
the GREGQ job it submits). MVS00 and MVS03 end twice (`$HASP395` count 2). Every step must complete 0000, the code the page lists
for MVS00 (4 steps), MVS01 (1) and MVS02 (30); this is stricter than the SMP stages (CC 4 allowed). On success `custom.done`
makes `ipl_conf` uncomment the two `0180` / `0190` lines in `conf/mvs.conf` for every later IPL, as the page's "remove the hash".

* **Message ids (confirmed live).** The master-catalog ask is `*nn IEC301A S JOB MVS02 DSNAME SYS1.VSAM.MASTER.CATALOG`
  (no word PASSWORD in it; the first live pass hung on it until the pattern named `IEC301A`); the ICKDSF confirmation is
  `*nn ICK003D REPLY U TO ALTER VOLUME 0180 CONTENTS, ELSE T`, answered `u` for 0180 and 0190.
* **Not re-runnable on used volumes.** MVS00's `INIT ... VERIFY(111111)` / `VERIFY(222222)` fail (`ICK31300I VERIFICATION
  FAILED: VOLUME-SERIAL WRONG`, CC 12, the IEBGENER continuation not executed) once PUB000 / PUB001 carry their labels. After a
  partial run, restore `mvsres` / `mvs000` / `page00` / `spool1` from `dasd.stage3.bak`, copy the SYSCPK image back, remove
  `ipl.done` and `custom.done`, delete the two `pub*` volumes and run `mvs38j.sh dasd user` again.
* **Ranged tape line.** `mvs.conf` declares its drives as `0100.4  3420  *`; `tape_unit` reads that form.
* **Out of reach here (page text read, not driven):** starting VTAM and TSO needs a tn3270 client on 3270 (`VTAM`, then
  `HMVS01` logon); the box has only the 009 console, and batch jobs through the card reader are all tier 2 needs. TSO-only
  features are not part of the JCL oracle.

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
now known informational lines (`unparsed_ief` is 0 on all four decks). PROC steps: a step line of a procedure call carries two names, the procedure step FIRST and the calling job step second (`IEF142I NPJOB A1 O2 - STEP WAS EXECUTED ...` is step `A1` of `//O2 EXEC BASE`; seen live 2026-11-20). The runner keeps both (`step` = the calling step, `procstep` = the procedure step, null for a plain step); it had them the other way round until #8414 slice 2 (pinned on fixture text, `test_proc_steps_keep_the_step_and_procstep_names_apart`). An `IEF450I` abend line is assumed to follow the same order: not seen live. `IEF202I` (`STEP WAS NOT RUN BECAUSE OF CONDITION CODES`) is verified live too: every COND-bypassed step prints it followed by `IEF272I` (probe run below). Trap: wrapping `stop` in `heavy-run.sh` queued it behind
another worker's slot and the box ran on.

### Remaining slices (#8414)

1. Hercules restart between smp1 and smp2 (each stage is its own Hercules run today; verified live on fresh volumes).
2. Moseley's "Customizing MVS" page (not read beyond the IPL replies).
3. Probe run, remaining classes (the COND / EVEN / ONLY, PROC, data-flow, GDG, step-restart and IEBGENER / IEBCOPY / IEFBR14 slices are done, below): SYSOUT class (`SYSJOB`), the checkpoint restarts (`RSTJOB4` / `11` / `12`, SYSCHK) and `carddemo` where 3.8J has the construct. IF / THEN / ELSE (`ifelse`, `ifflow_scenarios.json`) cannot run here.

## Probe run (#8414): COND / EVEN / ONLY

`tests/tools/box/mvs38j/probe.py cond --printer FILE` (a started box) builds one deck per scenario of `tests/equivalence/jcl/fixture/`
(`CONDJOB`, `EVNJOB`; 8 scenarios) from the fixture's own EXEC cards, COND kept as written. `{rc: n}` runs IDCAMS with `SET MAXCC=n`;
`{abend: ...}` runs a program that is in no library (S806: COND, EVEN and ONLY read that a step abended, not its code); a step with no
`given` runs IDCAMS with MAXCC 0, so a step the manual answer bypasses but the box starts is a disagreement. Each job log goes through
`runner.parse_log` (step started = `IEF142I` or an `IEF450I` abend). `tests/equivalence/jcl/fixture/mvs38j_probe.json` holds, per scenario,
three answers side by side: `expect` (IBM text, written before any evaluator), `engine` (`jcl_flow`) and `box` (MVS 3.8J), plus the
box's step records. Run 2026-11-20: **8 of 8 agree on all three columns**, `unparsed_ief` 0. Any scenario where the columns differ is a
register finding with its three answers and a cited rule, never an edit of `expect` or of the evaluator. Internal only (Q16): the file
is not linked from any published page.

Not covered by this deck shape (and so not claimed): a COND on a step that follows a step bypassed by an EVEN / ONLY chain deeper than
the fixture's; an abend code other than S806 (a user abend would need a program 3.8J ships that issues one).

## Probe run (#8414): PROC symbolics and overrides

`probe.py proc --printer FILE` runs the eight `tests/equivalence/jcl/proc` scenarios 3.8J can express: `SYMJOB` S1 to S3 (symbolics and
defaults), `OVRJOB` O1 to O3 (EXEC `PARM.` / `COND.` overrides, a DD override, an added DD), `PCJOB` C1 and C2 (PARM / COND on the call). The
SET, JCLLIB, INCLUDE and nested-procedure jobs have no 3.8J form. The deck keeps the job's procedure and that one call with its override
DDs; every `PGM=` becomes IEFBR14 and every DD keeps its DSN, allocated new on SYSDA (so the log names it). The observation channel is the
job log itself: `IEF236I` (the step, `procstep call`), `IEF237I` (each ddname), `IEF285I` (each DSN, in DD order) and `IEF653I`
(a symbol's substituted PARM). `tests/equivalence/jcl/proc/mvs38j_probe.json` holds `expect`, `engine` (`jcl_proc.resolve_job`) and `box`
per scenario. Run 2026-11-20: **8 of 8 agree**, and the first live `PROCSTEP` lines (`IEF142I OVRJOB A1 O3`, `A2 O3`) came from it.

What the box cannot show, so it is listed as `unobserved` in every result and not compared: the resolved `PGM` (replaced by IEFBR14), a
`PARM` that is not symbolic and every `COND` (IEFBR14 ends 0 and each COND here runs the step). The override rules for PARM / COND are
therefore tier 1 only. Box traps found: the listing's `++` echo shows the procedure's statements as written (an `EXEC PARM.A2=` override is
not echoed, an overridden DD shows as `+/`); a substituted statement past column 71 is a JCL error (`IEF621I`), so the probe leaves DISP to
default; a PROC statement parameter that no statement references gave `IEF657I SYMBOL NOT DEFINED IN PROCEDURE` in every trial (not
isolated further: the scenarios reference all of theirs).

## Probe run (#8414): data flow

`probe.py flow --printer FILE` runs the six `tests/equivalence/jcl/dataflow` scenarios (concatenation, `&&` temporaries with
`DISP=(,PASS)`, default dispositions, a bypassed creator, DUMMY) as IEFBR14 / IDCAMS decks and reads the allocation messages
(`IEF236I`, `IEF237I`, `IEF285I`) per step. `tests/equivalence/jcl/dataflow/mvs38j_probe.json` holds `expect`, `engine`
(`jcl_dataflow.resolve_dataflow`) and `box` side by side. Run 2026-11-20: **6 of 6 agree three ways**. Internal only (Q16): not linked
from a published page. `SYSJOB` is skipped (its `OUTPUT` statement is not in 3.8J).

Substituted, not claimed: the GDG `(0)` reference of the concatenation scenario ran against a plain dataset (`PAY.GDG.GSTAND`),
recorded as `substituted` in the results. A real generation (`(+1)` in a new GDG base) failed on the box with `IEF218I PATTERN DSCB
RECORD NOT FOUND IN VTOC` after four model-DSCB placements; the GDG probe below solved it (the model DSCB and every generation
must sit on the volume the group is pinned to).

Not observed (`FLOW_UNOBSERVED`): the read order of a concatenation (IEFBR14 reads nothing; the order is that of the allocation
messages), the SYSOUT class, the DISP of a permanent dataset (names only), real GDG generations.

Box traps found: a permanent dataset cataloged in the master catalog stops on `IEC301A` (SYSPROG password), so the deck re-roots it
under the `PUB001.` alias (user catalog `UCPUB001`); a DD operand past column 71 is `IEF618I`, so long cards continue; a `DISP=NEW`
without `UNIT` is `IEF210I` (the deck appends `UNIT=SYSDA,SPACE=(TRK,1)`); an `OLD` dataset that does not exist fails the whole job
(`IEF212I`), so datasets a scenario reads are created by a PREP deck and removed by an IDCAMS `DELETE` with `SET MAXCC=0`; the
`IEF285I` lines after the last step's `IEF374I` are job-end disposals, not the step's own, and `UCPUB001` is listed as a KEPT dataset
(filtered). A job hung on a prompt is purged with a `/*$CJnn,P` card through the card reader (the driver owns the console); a stale
`box.pid` blocks `start`.

## Probe run (#8414): GDG relative generations

`probe.py gdg --printer FILE` runs the `tests/equivalence/jcl/gdg` scenarios 3.8J can express: 20 of 31, each as its own job against
a base the probe defines first. 3.8J's GDG is a VSAM-catalog group: `IDCAMS DEFINE GDG (NAME(base) LIMIT(n) [EMPTY|NOEMPTY] SCRATCH)`
plus a model DSCB (a dataset named exactly the base, made by IEFBR14 `DISP=(,KEEP)`, `SPACE=(TRK,0)`, DCB FB / 80). Each scenario's
catalog is built by creating the absolute generations `base.GnnnnV00` (`DISP=(NEW,CATLG)`); a setup deck first deletes both bases and
IEHPROGM-scratches the VTOC (`IDCAMS DELETE ... GDG FORCE PURGE` leaves the generations' VTOC entries, so a re-create is `IEF253I`
otherwise). Then the job runs with its `(+n)` / `(0)` / `(-n)` DDs re-rooted under `PUB001.` (the master catalog stops on `IEC301A`),
the log is read (`IEF237I` ddname against `IEF285I` / `IEF287I` dataset, in order, the catalog entry and the `SYSnnnnn` DDs taken
out), and `LISTCAT ENTRIES(base) ALL` gives the catalog afterwards. `tests/equivalence/jcl/gdg/mvs38j_probe.json` holds `expect`
(IBM text), `engine` (`jcl_gdg.resolve_gdg`) and `box` per scenario, plus the box's dispositions, its catalog and the steps it did not
execute. Internal only (Q16).

Run 2026-11-20: **18 of 20 agree three ways, 2 differ on the box** (below). Skipped, with the reason in the file: the six
`step-bias-*` / `job-bias-*` / `proc-called-twice-under-step-bias` scenarios (GDGBIAS is a z/OS JOB keyword) and the five `restart-*`
scenarios (restart is a later slice). Both groups stay tier 1.

Box traps found: the model DSCB and every generation must be on one volume (`VOL=SER=PUB001`; a model elsewhere is `IEF218I`);
IEHPROGM / IEHLIST take `VOL=3390=PUB001`; a `DISP=(MOD,CATLG)` on a generation the catalog already holds prints `IEF287I ... NOT
RECTLGD` where a new one prints `IEF285I ... CATALOGED`; a DD naming the base prints one nameless `IEF237I` per generation and the
disposition lines come as `UNCATALOGED` then `DELETED` for each, so the parser merges those.

Findings (register entries, not edits of `expect` or the evaluator):

1. `empty-rolls-off-every-generation-at-limit`: the manual and the evaluator read `(0)` and `(-1)` in later steps as the pre-roll
   generations 7 and 6. On 3.8J, with EMPTY at the limit, the `(+1)` in step C1 uncatalogs all of them at that step, so step C2's
   `(0)` fails `IEF212I C2 CUR - DATA SET NOT FOUND` and the step does not run. The catalog afterwards ([8]) agrees.
2. `new-keep-is-a-deferred-roll-in`: a `(+1)` created `DISP=(NEW,KEEP)` is not cataloged, so a later step's `(+1) DISP=SHR` is a JCL
   error on 3.8J (`IEF286I K2 KIN - DISP FIELD INCOMPATIBLE WITH DSNAME`); the answer text and the evaluator resolve it to 8. The
   catalog afterwards ([5, 6, 7]) agrees.

Not observed (`GDG_UNOBSERVED`): what a program reads (every `PGM=` is IEFBR14), the fate of a generation rolled off at LIMIT
(SCRATCH / NOSCRATCH: only catalog membership is compared), the deferred roll-in state itself, a system-managed group (assumption
A5: 3.8J has the VSAM-catalog form), and the model DSCB after a base-name delete.

## Probe run (#8414): JOB RESTART= (deferred step restart)

`probe.py restart --printer FILE` runs the eleven `tests/equivalence/jcl/restart` scenarios of the jobs 3.8J can express: `RSTJOB1` (`RESTART=S3`),
`RSTJOB2` (`RESTART=*`), `RSTJOB3` (`RESTART=CALL1.P2`, a procedure step), `RSTJOB6` / `RSTJOB7` (COND naming a skipped step, a mixed COND) and
`RSTJOB8` (`COND=ONLY` on the restart step). Every `PGM=` becomes IDCAMS with `SET MAXCC=n` from `given`; a procedure's steps run `SYSIN DD DUMMY`
and the call overrides each `procstep.SYSIN`. The JOB card keeps `RESTART=` and every COND stays as written. The log gives each step one of
`skipped` (no step record: the box did not start it and did not bypass it), `run` (`IEF142I`) or `bypass` (`IEF202I`).
`tests/equivalence/jcl/restart/mvs38j_probe.json` holds `expect` (IBM text), `engine` (`jcl_restart.restart_flow`) and `box`.
Run 2026-11-21: **11 of 11 agree three ways**, `unparsed_ief` 0, no JCL error. Notably the box ignores a `COND` stepname that names a skipped
step (`RSTJOB6` Z3 runs) and a bare `COND=(0,NE)` reads only the steps that ran (assumption A1 on its outcome: S5 runs). Internal only (Q16).

Skipped, with the reason in the file: the checkpoint restarts (`RSTJOB4`, `11`, `12`: a SYSCHK dataset from a checkpointed run is needed) and the
IF / THEN / ELSE jobs (`RSTJOB5`, `9`, `10`). Both stay tier 1. `RSTJOB13` to `16` (the COND-override-on-a-procedure-call scenarios of #8835, added after this run) are skipped until the probe is rerun on the box. Not observed: what a program does (every step is IDCAMS).

## Probe run (#8414): IEBGENER / IEBCOPY / IEFBR14

`probe.py dsutil --printer FILE` runs the nine `cases` of `tests/equivalence/jcl/fixture/dsutil_scenarios.json` with the **real utilities**
(nothing is swapped for IDCAMS): IEFBR14 allocation and disposition (`NEW,CATLG` then `OLD,DELETE`; `NEW` with no disposition; `OLD` on an
uncataloged name), IEBGENER (instream to a new dataset, no `SYSUT1`, a `DUMMY` `SYSUT1`) and IEBCOPY (`SELECT`, `EXCLUDE`, no member statement)
on a two-member PDS read back member by member. The manual answers were committed before the run (dfd68b486). The fixture's `PRB.UTIL.*` names are
re-rooted to `PUB001.UTIL.*` at run time (see the trap below) and mapped back when the dispositions are read. A `PRBCLEAN` IEFBR14 job
(`MOD,DELETE`) runs before each scenario and at the end. `tests/equivalence/jcl/fixture/dsutil_mvs38j_probe.json` holds `expect` and `box`; `engine`
is null (no gitgalaxy evaluator models what a utility does to a dataset: two columns, not three).
(The list key is `cases`, not `scenarios`: the capability ledger reads every `scenarios` file in `tests/equivalence/jcl/*/` as an engine answer set and needs a `given` the utilities do not have.)
Run 2026-11-21: **8 of 9 agree manual / box**. `unparsed_ief` is 0 except A1's scenario (2: `IEF453I JOB FAILED - JCL ERROR` and `IEF212I DATA SET NOT FOUND`: the box calls a missing `OLD` dataset a JCL error, a message `runner.parse_log` does not read, so `jcl_error` stays false; the step is `IEF272I` not executed). The two assumptions agree: A1 (an `OLD` dataset that is not cataloged fails
allocation and flushes the later steps) and A2 (IEBGENER with no `SYSUT1` ends RC 12). Internal only (Q16).

* **Register finding (manual vs box, not resolved): `iebgener-dummy-input-empty-output`.** The fixture's answer is RC 0 (a `DUMMY` `SYSUT1` reads end
  of data, the usual way to allocate an empty dataset, `SYSUT2` carrying its own DCB). On 3.8J IEBGENER ends **RC 12** with `IEB317I JOB TERMINATED,NO
  INPUT BLKSIZE/LRECL`: a dummy input gives it no DCB to take, and the DCB coded on `SYSUT2` is not used instead. `SYSUT2` is still created and cataloged
  and the next step deletes it. `expect` is not changed: the manual text read for this fixture does not say, and a later IEBGENER level may differ.
  The engine has no answer to compare.
* **Trap: IEC301A.** A permanent dataset cataloged in the master catalog waits on `IEC301A ... SYS1.VSAM.MASTER.CATALOG` for the SYSPROG password and
  holds the initiator, so every later job queues behind it (the first run lost 10 minutes this way). Names go under `PUB001.` (a user-catalog alias).
  A warm IPL does not clear the held job: the spool keeps it and JES2 never reaches `$HASP099` (900 s); move `ipl.done` aside once so the IPL formats the spool, then put it back.

Not observed: the engine's answer, a dataset's record format / length / block size (no VTOC listing), which members a PDS holds beyond the one read
back per step. Not in the fixture (`refused`): IEBGENER `GENERATE`, IEBCOPY unload / reload, VTOC and DCB checks.

## What this tier cannot test

IF / THEN / ELSE, JCLLIB, INCLUDE, SET, modern DFSORT / ICETOOL, Enterprise COBOL and CICS do not exist in MVS 3.8J.
They stay tier 1 (manual answers) until z/OS access (#6492).
