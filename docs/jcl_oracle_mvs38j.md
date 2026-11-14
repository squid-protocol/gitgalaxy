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
tests/tools/box/mvs38j/mvs38j.sh sysgen starter   # START1 + SPOOL0: DASDI then DUMP/RESTORE per volume, driven over the console (~11 s)
tests/tools/box/mvs38j/mvs38j.sh status    # container and tape state
tests/tools/box/mvs38j/mvs38j.sh start     # needs $MVS38J_WORK/conf/mvs.conf (the generated system)
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

### Remaining slices (#8414)

1. Starter-system IPL stages: `smp1.cnf` / `smp2.cnf` with `ipl 150`, `r 0,clpa`, `r 0,format,noreq`, then jobs through
   `devinit 12 jcl/smpjobNN.jcl` with tape mounts (`devinit 170 tape/...`, `r N,170`), and a `condcode` check per job. The
   console there is the telnet 3215 at 001F (port 3270): the driver needs a small telnet client for it, not the 1052-C `/` path.
2. Stage 1 and stage 2 (`sysgen01` output to `stage1.output`, `stage2.rexx`/`awk` port or call, the socket reader on 3505),
   then the user mods and `mvs.cnf` first IPL of the generated system.
3. Job runner: submit a deck to `localhost:3505`, capture the printer file, parse to JSON with provenance `mvs38j-run`.

## What this tier cannot test

IF / THEN / ELSE, JCLLIB, INCLUDE, SET, modern DFSORT / ICETOOL, Enterprise COBOL and CICS do not exist in MVS 3.8J.
They stay tier 1 (manual answers) until z/OS access (#6492).
