---
description: "Apollo 11's guidance computer source, read by the current GitGalaxy engine: 171 AGC assembly files, two spacecraft, 4,786 labelled routines. A dated, reproducible teardown by Joe Esquibel."
---
# The Architecture of Apollo: The Guidance Computer, Read Again

*By Joe Esquibel · rescanned 8 November 2026 · made with the [GitGalaxy](https://github.com/squid-protocol/gitgalaxy) code-scanning engine*

> ### === EXHIBIT: APOLLO ===
> 
> **WHY IT MATTERS:**
> The code that defined software engineering.
> 
> **THE ARCHITECTS:**
> Margaret Hamilton & The MIT Instrumentation Lab.
> 
> **HISTORICAL SIGNIFICANCE:**
> Written for the Apollo Guidance Computer (AGC), this code operated on only 4KB of RAM and 72KB of ROM. Margaret Hamilton’s leadership and vision propelled her team to create a system so thorough and robust, that it permanently altered humanity’s view on the role of software in projects. The literal birth place of software engineering, as Margaret coined that term during this project to describe the seriousness and scale of the endeavor that she was leading. When 72KB of code is the only thing standing between three humans and the void, does programming become an act of engineering, or an act of faith? Would you go to space armed with less than one emoji’s worth of data? The digital preservation of this artifact is made possible by the meticulous efforts from the Virtual AGC Project. By manually transcribing the original scanned printouts from the MIT Instrumentation Laboratory, they ensured this code survived into the modern era. The complete assembly source code for the Command and Lunar Modules is now preserved and publicly accessible.
> 
> **--- AUDIO & ARTIFACTS ---**
> ▶ **13 Minutes to the Moon: The fourth astronaut**
> The definitive audio history of the Apollo Guidance Computer, the fourth astronaut. It features direct interviews with Margaret Hamilton and Jack Garman. BBC World Service.
> [Listen Here](https://www.bbc.com/audio/play/w3csz4dn)
> 
> ▶ **Science Friday: The Women Who Brought Us Apollo 11**
> This interview with Margaret Hamilton explores how she coined the term "Software Engineering." It highlights the human touch: she brought her daughter to the lab, and her daughter playing with the simulator actually revealed a bug that could have wiped the memory.
> [Listen Here](https://www.sciencefriday.com/segments/the-women-who-brought-us-apollo-11/)
> 
> ▶ **Radiolab: Mixtapes to the Moon**
> While less about the code, this provides the "human texture" of the mission—specifically the audio tapes and the feeling of the 400,000 people working in sync. Highlights how humans can work together as a collective to achieve the impossible.
> [Listen Here](https://radiolab.org/podcast/mixtapes-to-the-moon)

---

## What we measured

One scan of [chrislgarry/Apollo-11](https://github.com/chrislgarry/Apollo-11) at commit `247dd7d` (2026-01-22). The
engine was GitGalaxy at commit `3bb225071` (2026-11-08), with git history off. Every number below comes from that one
scan; [Check my work](#check-my-work) has the command.

| | |
|---|---:|
| files tracked by git | 262 |
| files read | 254 |
| AGC assembly files read | 171 (74,054 lines of code) |
| labelled routines found | 4,786 |
| routine-to-routine links resolved | 4,270 |
| engine time | 1.28 s |

The 8 files left out are each listed with a reason in the audit report:
- three hidden config files;
- a binary lockfile (`bun.lockb`);
- three AGC files set aside for "lexical monotony", their lines too alike to carry structure: both
  `ERASABLE_ASSIGNMENTS.agc` memory maps and Luminary's copy of `PINBALL_GAME_BUTTONS_AND_LIGHTS.agc`;
- Luminary's `MAIN.agc`, which is only a list of the files to assemble, with no structural signal.

Losing a Pinball is a real limit of the scan, and it is stated here rather than hidden.

## 1. A language without functions

AGC assembly has no functions, so the engine has to find structure by position:
- **Routines:** a routine starts where a label sits at the very start of a line, followed by an instruction (`TC`,
  `CA`, `CAF`, `TS` and so on). The rule is in
  [`agc_assembly.py`](../../../gitgalaxy/standards/language_standards/languages/agc_assembly.py).
- **Data:** a label followed by data (`2DEC`, `ADRES`, `EQUALS`) is not a routine.
- **Comments:** a `#` starts a comment.
- **Calls:** a `TC Q` hands control back through the Q register. It is a return, not a call.

By that rule the two programs hold 4,786 routines.

## 2. The Twin Hubs: Comanche and Luminary

The repository holds two programs, compiled for two computers in two spacecraft:
- **`Comanche055`** flew the Command Module: deep-space navigation, lunar orbit, and re-entry.
- **`Luminary099`** flew the Lunar Module: descent to the surface, and the climb back to rendezvous.

| | files read | lines of code | routines |
|---|---:|---:|---:|
| Comanche055 (Command Module) | 84 | 37,970 | 2,492 |
| Luminary099 (Lunar Module) | 87 | 36,084 | 2,294 |

The two programs are close to the same size, and 51 file names appear in both. Each spacecraft carries its own
scheduler (`EXECUTIVE.agc`, `WAITLIST.agc`), its own interrupt handler (`T4RUPT_PROGRAM.agc`) and its own DSKY display
code. What differs is the physics:
- **Luminary** has the descent: `LUNAR_LANDING_GUIDANCE_EQUATIONS.agc` (1,028 lines, 75 routines) and
  `BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc` (734 lines, 66 routines).
- **Comanche** has the way home instead: `CM_ENTRY_DIGITAL_AUTOPILOT.agc` (842 lines, 57 routines).

## 3. The "Pinball" Interface

`Comanche055/PINBALL_GAME_BUTTONS_AND_LIGHTS.agc` drove the DSKY, the Display and Keyboard. The engineers named it
"Pinball" for its flashing lights. Astronauts in bulky gloves keyed in a "Verb" (action) and a "Noun" (data).

In the scan, Pinball is one of the largest files (2,461 lines of code, 286 routines). It is also the most connected:
16 other files link to it in the engine's file graph, more than any other file. Two of its small routines are among the
most-called in the whole program:
- `FALTON` has 20 callers;
- `GOPIN`, in `EXTENDED_VERBS.agc`, also has 20.

Luminary's copy of Pinball is the file the engine set aside (see above), so this section describes the Command
Module's.

## 4. Priority Scheduling & Cycle Syncing

`EXECUTIVE.agc` and `WAITLIST.agc` made one of the first priority-based operating systems:
- **Comanche's copies:** 345 and 266 lines;
- **Luminary's copies:** 353 and 279 lines.

During the descent, a radar setting flooded the computer with extra work. The Executive dropped low-priority jobs,
which raised the famous 1201 and 1202 alarms, and the landing guidance kept running. `EJSCAN`, the routine that scans
for the next job to run, is 48 lines in Comanche and 54 in Luminary.

## 5. Orbital Mechanics & The Heavy Lifters

The largest files are the navigation programs:
- `P20-P25.agc`, rendezvous navigation and tracking: 3,377 lines in Luminary and 2,788 in Comanche. Comanche's copy
  holds `R60CALL` (212 lines).
- `INTERPRETER.agc`: about 2,085 lines and 241-243 routines in each spacecraft.

The engineers built a virtual machine inside the computer: the interpreter ran vector and matrix arithmetic that the
bare processor could not. Its dispatch step, `OPJUMP3`, is 13 lines.

The longest "routines" the engine finds are tables, not logic: `GTSFIN` in `PINBALL_NOUN_TABLES.agc` runs 707 lines in
Luminary and 683 in Comanche. It is a label followed by hundreds of lines of noun definitions, and the routine rule
reads it as one block. That is a limit of reading structure by position.

## What it can't tell you

- **The routine rule is a heuristic.** A label followed by an instruction is treated as a routine. Tables that start
  with an instruction are counted too, and an entry point reached only by jumping into the middle of code is not.
- **Links are resolved by label name.** A label reused in both programs resolves within its own program, but indirect
  jumps through tables are not followed.
- **One scan, one engine version.** The numbers are from the scan above. An earlier version of this page quoted
  per-file risk scores and an architectural "drift" score. Neither is used any more: the per-file surface readings
  describe where a pattern concentrates and do not predict defects
  ([what the Structural Surface Profile claims](../../vectors.md)).
- **This is the code as transcribed.** The Virtual AGC project transcribed the original scanned printouts by hand.
  The engine reads that transcription, not the core rope memory that flew.

## Check my work

```bash
git clone https://github.com/chrislgarry/Apollo-11 && git -C Apollo-11 checkout 247dd7d
GITGALAXY_DISABLE_GIT_HISTORY=1 galaxyscope Apollo-11 --output apollo-scan/   # GitGalaxy at 3bb225071
sqlite3 -readonly apollo-scan/Apollo-11_galaxy_master.db \
  "SELECT file_path, coding_loc, function_count, popularity FROM file_data ORDER BY coding_loc DESC LIMIT 10"
```

The audit report (`*_galaxy_audit.json`) lists every left-out file with its reason. The master database's
`function_data` table holds every routine, with its length and callers.

---

**[⬅️ Back to the Museum of Code](index.md)**
