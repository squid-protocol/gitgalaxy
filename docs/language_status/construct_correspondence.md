# Construct correspondence: what each COBOL construct becomes in Java

Generated with `tests/tools/construct_map.py` (scan, then analyze) on 2026-10-02. It covers 49 converted programs
across CardDemo, CBSA and GenApp, in three forms:

- **COBOL**: the original program.
- **det**: the deterministic port, as `det_port.py run` emits it.
- **model**: the model-written port, where one exists (26 programs): 23 CardDemo ports, plus CBSA UPDACC
  and GenApp LGICDB01 / LGAPVS01 from #4168. Those three are proven but await review.

The aim is to see, construct by construct, where Java grows and where the model's Java is smaller. Model idioms that
are much smaller than the det port's code for the same paragraph are candidate rewrite rules for the det readability
layers.

**Read the candidates as hypotheses.** A model port is proven only on its case's scenarios. Each rule built from a
candidate needs its own proof on every case that contains the construct before the det port adopts it. Each candidate
below therefore lists those cases.

## Method

1. **Scan.** Each form goes into its own git repo per estate, scanned by `galaxyscope`. Every measurement is the
   scanner's own per-function data (`function_data`: lines, branches, complexity, tokens).
   - Plain `galaxyscope` scans the det ports. Each one declares itself with a `// gitgalaxy-det-port:` header, which
     the aperture admits past the generated-noise gates (#4164).
2. **Paragraphs.** The COBOL comes from the det translator's own parse of the PROCEDURE DIVISION (`det/stmt.py`). It
   resolves copybooks the way `det_port.py` does: case copy dirs, DCLGEN include dirs, then the estate's BMS
   symbolic maps.
3. **Constructs.** Each paragraph's statements are tagged, and the paragraph takes its dominant construct.
   - A paragraph is `record-move` when MOVE / INITIALIZE / SET TO are at least 60% of it (and 5 or more statements).
   - Otherwise it takes its heaviest other construct. An I/O statement (file, CICS file / screen / queue, SQL) counts
     3, because it is what the paragraph is for. An OPEN with its two file-status IFs is a `file-io` paragraph.
   - `88-level` is SET ... TO TRUE, or an IF / EVALUATE on a condition name.
   - `cics-control` is every other EXEC CICS: RETURN, XCTL, LINK, HANDLE, ASSIGN, and so on.
   - `trivial` is a paragraph of EXIT / CONTINUE only.
4. **Alignment.**
   - **det: exact.** The emitter writes each paragraph as one method under a `/** NAME. */` javadoc.
   - **model: by evidence.** The method's name is the paragraph's without its number (high); a comment before the
     method names it (medium); a comment inside it names it (low). A model method that merges several paragraphs is
     compared with their sum (a group). The tables use high and medium evidence only.

Cells are the median (interquartile range) of per-paragraph values; `x` columns are Java / COBOL, per paragraph or
group.

## Where the det port's size comes from

| det port part | lines | share |
|---|---:|---:|
| paragraph methods | 29,304 | 47% |
| storage field declarations | 17,290 | 28% |
| entry points (task, batch, link) | 6,606 | 11% |
| PERFORM / GO TO dispatch | 3,545 | 6% |
| DTO bridges (COMMAREA / record objects to storage) | 2,354 | 4% |
| other helpers | 2,005 | 3% |
| CICS plumbing | 463 | 1% |
| entity keys | 212 | 0% |

**Paragraph code is not where the det port grows.** Its paragraph methods are only 1.33x the COBOL
paragraphs' lines: 29,308 against 21,994. The 5x whole-file growth the [COBOL vs Java scan
comparison](../wiki/05-18-cobol-java-scan-parity.md) measured has three main sources:

- the storage layer: every WORKING-STORAGE field declared and initialised as bytes;
- the entry points;
- the dispatch.

That is the target for the typed and structured layers, not the translation of statements.

**One construct stands out: CICS screen I/O.** 42 `cics-screen` paragraphs (5% of all
paragraphs) account for 2,463 (34%) of the 7,314 lines the det paragraph methods add over COBOL. A SEND MAP
is one statement in COBOL. The det port inlines it as a field-by-field build of the map's values and subfields at
every SEND site, as the excerpt below shows.

## Per construct

### COBOL against the det port (exact)

| construct | paragraphs | cases | COBOL lines | det lines | det x lines | det x branches | det x complexity |
|---|---:|---:|---:|---:|---:|---:|---:|
| trivial | 228 | 25 | 2 (2–3) | 4 (4–4) | 2.0 (1.5–2.0) | - | - |
| record-move | 94 | 41 | 26 (18–60) | 38 (28–89) | 1.4 (1.1–1.5) | 1.8 (1.2–2.5) | 1.8 (1.2–2.5) |
| 88-level | 91 | 9 | 41 (30–55) | 41 (27–55) | 1.1 (0.9–1.2) | 1.4 (1.0–1.5) | 1.4 (1.0–1.5) |
| file-io | 71 | 8 | 17 (17–17) | 30 (30–31) | 1.8 (1.8–1.8) | 1.0 (1.0–1.0) | 1.0 (1.0–1.0) |
| cics-control | 62 | 37 | 14 (4–34) | 23 (9–65) | 1.8 (0.9–2.1) | 5.2 (3.0–6.0) | 5.2 (3.0–6.0) |
| evaluate | 59 | 26 | 30 (28–42) | 38 (33–53) | 1.2 (1.1–1.3) | 1.8 (1.4–2.0) | 1.8 (1.4–2.0) |
| perform | 59 | 29 | 16 (7–44) | 15 (9–61) | 1.4 (1.1–1.5) | 1.2 (1.0–1.4) | 1.2 (1.0–1.4) |
| cics-screen | 42 | 19 | 11 (9–13) | 55 (40–80) | 4.6 (3.0–8.3) | 3.0 (3.0–3.5) | 3.0 (3.0–3.5) |
| db2-singleton | 16 | 12 | 33 (26–69) | 34 (22–59) | 1.0 (0.8–1.1) | 1.8 (1.1–2.2) | 1.8 (1.1–2.2) |
| cics-file | 11 | 10 | 19 (5–74) | 27 (11–71) | 1.6 (1.0–2.2) | 1.9 (1.6–4.1) | 1.9 (1.6–4.1) |
| arithmetic | 10 | 6 | 17 (12–17) | 32 (24–33) | 1.9 (1.8–2.0) | 1.0 (1.0–1.0) | 1.0 (1.0–1.0) |
| call | 7 | 7 | 5 (5–5) | 11 (11–11) | 2.2 (2.2–2.2) | - | - |
| db2-cursor | 7 | 3 | 23 (23–26) | 27 (21–34) | 1.1 (0.9–1.3) | 1.0 (1.0–1.3) | 1.0 (1.0–1.3) |
| goback | 6 | 6 | 3 (3–3) | 6 (6–6) | 2.0 (1.9–2.0) | - | - |
| display | 4 | 4 | 20 (6–30) | 28 (13–40) | 1.8 (1.1–2.1) | 2.0 (1.2–3.0) | 2.0 (1.2–3.0) |
| if | 4 | 4 | 48 (36–128) | 60 (35–136) | 1.1 (0.9–1.3) | 1.1 (0.9–1.3) | 1.1 (0.9–1.3) |
| nested-if | 3 | 2 | 85 (83–106) | 78 (64–112) | 0.8 (0.7–1.3) | 1.2 (1.0–1.2) | 1.2 (1.0–1.2) |
| cics-queue | 1 | 1 | 21 (21–21) | 24 (24–24) | 1.1 (1.1–1.1) | 1.7 (1.7–1.7) | 1.7 (1.7–1.7) |

### The model port, where one exists

| construct | model groups | model x lines | model / det lines |
|---|---:|---:|---:|
| record-move | 42 | 0.6 (0.4–1.0) | 0.40 (0.18–0.70) |
| 88-level | 18 | 0.7 (0.5–0.8) | 0.56 (0.41–0.62) |
| file-io | 26 | 0.6 (0.2–1.0) | 0.35 (0.10–0.53) |
| cics-control | 18 | 9.0 (0.6–14.0) | 0.58 (0.41–0.63) |
| evaluate | 36 | 0.6 (0.4–0.9) | 0.48 (0.36–0.62) |
| perform | 32 | 1.0 (0.7–1.1) | 0.61 (0.57–0.75) |
| cics-screen | 24 | 0.8 (0.5–1.6) | 0.13 (0.09–0.29) |
| cics-file | 5 | 1.2 (0.5–1.5) | 0.55 (0.32–0.68) |
| arithmetic | 9 | 0.8 (0.3–0.8) | 0.40 (0.17–0.45) |
| call | 4 | 0.8 (0.8–0.9) | 0.36 (0.36–0.43) |
| display | 2 | 1.0 (0.6–1.5) | 0.52 (0.34–0.70) |
| if | 2 | 1.0 (0.8–1.2) | 0.81 (0.71–0.91) |
| cics-queue | 1 | 0.6 (0.6–0.6) | 0.50 (0.50–0.50) |

**What the structured and typed layers change.** The same analysis was run on the det ports emitted with
`--style structured --typed` (B1 + B3). The per-construct ratios move by under 5%, and paragraph methods total
29,071 lines against 29,308. B1 names the methods. B3 types the standalone items, but most paragraph code
moves group fields, so their use stays byte-level. Neither shrinks a paragraph.

## Candidate rewrite rules for the det readability layers

**How the candidates were found.** The analysis took the model methods (high or medium evidence) that are at most half
the det lines for the same paragraphs, with the det side at least 20 lines. Each was searched for the idioms below. A
group can show several idioms, so the savings overlap and do not add up.

| idiom | groups | cases | det lines | model lines | saved | constructs |
|---|---:|---:|---:|---:|---:|---|
| string-helpers | 49 | 16 | 3,488 | 1,019 | 2,469 | record-move 18, cics-screen 9, evaluate 8, 88-level 3, cics-control 3, arithmetic 3, file-io 2, cics-file 1, perform 1, cics-queue 1 |
| typed-accessors | 35 | 15 | 3,221 | 921 | 2,300 | record-move 16, cics-screen 7, 88-level 3, evaluate 3, cics-control 3, file-io 2, perform 1 |
| task-api | 26 | 11 | 1,926 | 410 | 1,516 | evaluate 12, cics-screen 9, cics-control 2, record-move 1, 88-level 1, cics-queue 1 |
| optional-stream | 16 | 13 | 1,551 | 248 | 1,303 | cics-screen 11, 88-level 2, evaluate 2, record-move 1 |
| string-concat | 17 | 10 | 1,404 | 384 | 1,020 | record-move 6, evaluate 5, arithmetic 3, 88-level 1, cics-control 1, file-io 1 |
| early-return | 7 | 5 | 1,392 | 518 | 874 | record-move 3, 88-level 1, cics-file 1, perform 1, evaluate 1 |
| boolean-flags | 4 | 4 | 564 | 226 | 338 | record-move 3, 88-level 1 |
| bigdecimal | 10 | 4 | 344 | 122 | 222 | file-io 3, record-move 3, arithmetic 2, display 1, cics-queue 1 |
| repository | 6 | 4 | 233 | 93 | 140 | evaluate 3, file-io 1, display 1, record-move 1 |
| switch | 2 | 2 | 86 | 37 | 49 | evaluate 2 |

Read with the excerpts, the idioms suggest these rules, in order of payoff: the det lines the model's code saves
in the groups the rule's construct appears in. A paragraph can hold several constructs, so the rules' savings
overlap. Each rule is deterministic: the det port's generator could emit it, and the proof decides.

1. **EVALUATE TRUE / WHEN chains on 88-levels as named boolean methods.** The model names each condition (`isErrFlgOn()`, boolean locals) where the det port compares the field to the 88's values inline. One method per 88 name, generated from the layout, makes each test one call and puts the values in one place.
   - Evidence: 244 paragraphs in 28 cases; where a model port exists, the model's code is 0.41x the det port's (91 groups, 3,797 lines fewer).
   - Prove on: carddemo-acctupdate, carddemo-acctview, carddemo-adminmenu, carddemo-billpay, carddemo-cardlist, carddemo-cardupdate, carddemo-cardview, carddemo-cotrtlic, carddemo-cotrtupc, carddemo-dailyval, carddemo-intcalc, carddemo-menu, carddemo-posttran, carddemo-readcard, carddemo-readcust, carddemo-readxref, carddemo-report, carddemo-signon, carddemo-tranadd, carddemo-tranlist, carddemo-tranview, carddemo-trnrpt, carddemo-useradd, carddemo-userdel, carddemo-userlist, carddemo-userupd, cbsa-delacc, cbsa-xfrfun.
2. **SEND MAP / RECEIVE MAP through one generated method per map.** The det port builds the map's values and subfields inline at every SEND, field by field. The model calls the generated screen class (`XxxScreen.fromValues`, `task.sendMap`) once. A per-map `send<Map>(erase, cursor)` / `receive<Map>()` pair, generated from the BMS map the det port already reads, would put that code in one place. Every SEND site would become one call.
   - Evidence: 42 paragraphs in 19 cases; where a model port exists, the model's code is 0.15x the det port's (24 groups, 1,749 lines fewer).
   - Prove on: carddemo-acctupdate, carddemo-acctview, carddemo-adminmenu, carddemo-billpay, carddemo-cardlist, carddemo-cardupdate, carddemo-cardview, carddemo-cotrtlic, carddemo-cotrtupc, carddemo-menu, carddemo-report, carddemo-signon, carddemo-tranadd, carddemo-tranlist, carddemo-tranview, carddemo-useradd, carddemo-userdel, carddemo-userlist, carddemo-userupd.
3. **Record fields through typed accessors.** Where a record has a generated DTO or entity, the model moves fields with `getX()` / `setX()` plus `fit` / pad helpers. The det port uses `Cobol.move(field, field, CS)` on storage. This extends B3 (typed state) from standalone items to fields of records that have a generated class. The record-move paragraphs carry most of the `string-helpers` and `typed-accessors` savings.
   - Evidence: 94 paragraphs in 41 cases; where a model port exists, the model's code is 0.36x the det port's (42 groups, 1,377 lines fewer).
   - Prove on: carddemo-acctupdate, carddemo-acctview, carddemo-adminmenu, carddemo-billpay, carddemo-cardlist, carddemo-cardupdate, carddemo-cardview, carddemo-cotrtlic, carddemo-cotrtupc, carddemo-dailyval, carddemo-dateutil, carddemo-intcalc, carddemo-menu, carddemo-posttran, carddemo-readcard, carddemo-readcust, carddemo-readxref, carddemo-report, carddemo-signon, carddemo-tranadd, carddemo-tranlist, carddemo-tranview, carddemo-trnrpt, carddemo-useradd, carddemo-userdel, carddemo-userlist, carddemo-userupd, cbsa-dbcrfun, cbsa-delacc, cbsa-inqacc, cbsa-updacc, cbsa-updcust, cbsa-xfrfun, genapp-lgapdb01, genapp-lgapvs01, genapp-lgdpvs01, genapp-lgicdb01, genapp-lgipdb01, genapp-lgucdb01, genapp-lgupdb01, genapp-lgupvs01.
4. **GO TO an exit paragraph as a return.** Programs with GO TO keep the dispatch style. The model returns early where the COBOL does GO TO <para>-EXIT inside a PERFORM range. Letting B1 (structured style) accept a GO TO whose only target is the end of the PERFORM range would bring those programs into the structured style.
   - Evidence: 75 paragraphs in 14 cases; where a model port exists, the model's code is 0.40x the det port's (12 groups, 801 lines fewer).
   - Prove on: carddemo-acctupdate, carddemo-acctview, carddemo-cardlist, carddemo-cardupdate, carddemo-cardview, carddemo-cotrtlic, carddemo-cotrtupc, carddemo-report, cbsa-dbcrfun, cbsa-delacc, cbsa-inqacc, cbsa-updacc, cbsa-updcust, cbsa-xfrfun.
5. **Repeated file-status paragraphs as one parameterised helper.** Batch programs repeat the same OPEN / CLOSE + status-check paragraph per file. The model folds them into one method taking the file. A det rule would fold paragraphs that are identical apart from the file and record names (clone detection on the parsed statements) into one method.
   - Evidence: 71 paragraphs in 8 cases; where a model port exists, the model's code is 0.33x the det port's (26 groups, 560 lines fewer).
   - Prove on: carddemo-cobtupdt, carddemo-dailyval, carddemo-intcalc, carddemo-posttran, carddemo-readcard, carddemo-readcust, carddemo-readxref, carddemo-trnrpt.
6. **INITIALIZE of a group as one generated initializer.** The det port expands INITIALIZE into one `moveFigurative` per elementary item, at every use. The model writes a `blankX()` / `resetX()` per record. A per-group `initialize<Group>()`, or a copy of the group's initial byte image (the port already embeds images), is one call per INITIALIZE.
   - Evidence: 53 paragraphs in 26 cases; where a model port exists, the model's code is 0.51x the det port's (7 groups, 385 lines fewer).
   - Prove on: carddemo-acctupdate, carddemo-acctview, carddemo-billpay, carddemo-cardlist, carddemo-cardupdate, carddemo-cardview, carddemo-cotrtlic, carddemo-cotrtupc, carddemo-posttran, carddemo-report, carddemo-tranadd, carddemo-trnrpt, cbsa-custctrl, cbsa-dbcrfun, cbsa-delacc, cbsa-inqacc, cbsa-updacc, cbsa-xfrfun, genapp-lgacdb01, genapp-lgacdb02, genapp-lgapdb01, genapp-lgdpdb01, genapp-lgicdb01, genapp-lgipdb01, genapp-lgucdb01, genapp-lgupdb01.
7. **CICS command outcomes as values.** The det port's `cics-control` paragraphs have 5x the COBOL branch points: each command's RESP and HANDLE CONDITION dispatch is spelled out. Where a program tests a command's RESP only for NORMAL / NOTFND (and so on), the model takes the `CicsTask` result (`Optional`, a result object) and branches once. The rule: a command whose RESP is only compared becomes a call returning that result.
   - Evidence: 62 paragraphs in 37 cases; where a model port exists, the model's code is 0.54x the det port's (18 groups, 217 lines fewer).
   - Prove on: carddemo-acctupdate, carddemo-acctview, carddemo-adminmenu, carddemo-billpay, carddemo-cardupdate, carddemo-cardview, carddemo-cotrtupc, carddemo-menu, carddemo-report, carddemo-tranadd, carddemo-tranlist, carddemo-tranview, carddemo-useradd, carddemo-userdel, carddemo-userlist, carddemo-userupd, cbsa-abndproc, cbsa-custctrl, cbsa-dbcrfun, cbsa-delacc, cbsa-inqacc, cbsa-updacc, cbsa-updcust, cbsa-xfrfun, genapp-lgacdb01, genapp-lgacdb02, genapp-lgacvs01, genapp-lgapdb01, genapp-lgapvs01, genapp-lgdpdb01, genapp-lgdpvs01, genapp-lgicdb01, genapp-lgipdb01, genapp-lgucdb01, genapp-lgucvs01, genapp-lgupdb01, genapp-lgupvs01.

**Not supported by this data.** Two idioms have too little evidence to rank.

- **EVALUATE as a Java `switch`** occurs in only 2 groups: the models mostly keep if / else chains.
- **Db2 through the generated repositories.** The three Db2 / VSAM model ports added in #4168 align well (UPDACC's UAD010 to `updateAccount`, LGICDB01's GET-CUSTOMER-INFO to `getCustomerInfo`). But their SQL sits in paragraphs dominated by MOVEs or an EVALUATE on SQLCODE, so those paragraphs count as record-move and evaluate. A Db2-level rule needs more Db2 model ports and a tag for the SQL inside a paragraph, not only its dominant construct.

## The TODO markers in model ports

The [COBOL vs Java scan comparison](../wiki/05-18-cobol-java-scan-parity.md) counted TODO / FIXME lines in the model ports as their debt. Of those
lines in the scanned model ports, 46 are the generator's own scaffold left in the file:

- the stub javadoc on `handleTransaction` / `handleLink` ("TODO: [AI AGENT] implement ...");
- "the RESP of ... is never tested" notes;
- "TODO: port the logic that fills ... before the SEND".

4 are the model's own, for example "CicsTask.rewrite does not expose RESP2; WS-REAS-CD is taken as 0".

So the model ports do not carry dozens of TODOs of their own. The generator should drop its scaffold comments once a
port fills the method. That is a follow-up for the service forge, not for the model.

## Excerpts

#### string-helpers: carddemo-tranlist SEND-TRNLST-SCREEN

model `sendTrnlstScreen` (14 lines) vs det (269 lines)

```java
void sendTrnlstScreen() {
    populateHeaderInfo();
    scr.put("ERRMSG", fit(message, 78));   // MOVE WS-MESSAGE TO ERRMSGO
    Cotrn0aScreen screen = Cotrn0aScreen.fromValues(scr);
    CicsTask.MapSubfields sub = new CicsTask.MapSubfields();
    if (cursorL) {
        sub.cursor("TRNIDIN");
    }
    if (eraseYes) {
        task.sendMap("COTRN0A", "COTRN00", screen, sub, "ERASE", "CURSOR");
    } else {
        task.sendMap("COTRN0A", "COTRN00", screen, sub, "CURSOR");
    }
}
```

```java
private int p9() {
    // PERFORM POPULATE-HEADER-INFO
    perform(11, 11);
    // MOVE WS-MESSAGE TO ERRMSGO OF COTRN0AO
    Cobol.move(f4_WS_MESSAGE, f756_ERRMSGO, CS);
    // IF SEND-ERASE-YES
    if (Cobol.compare(f8_WS_SEND_ERASE_FLG, "Y", CS) == 0) {
        // EXEC CICS SEND MAP('COTRN0A') MAPSET('COTRN00') FROM(COTRN0AO) ERASE CURSOR END-EXEC
        java.util.Map<String, String> values9 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub10 = new CicsTask.MapSubfields();
        values9.put("TRNNAME", Cobol.text(f408_TRNNAMEO, CS));
        DetCics.subfields(sub10, "TRNNAME", f47_TRNNAMEL, f50_TRNNAMEA, f404_TRNNAMEC, f406_TRNNAMEH, CS);
        values9.put("TITLE01", Cobol.text(f414_TITLE01O, CS));
        DetCics.subfields(sub10, "TITLE01", f53_TITLE01L, f56_TITLE01A, f410_TITLE01C, f412_TITLE01H, CS);
...
```

#### typed-accessors: carddemo-cardlist 0000-MAIN

model `runTask` (144 lines) vs det (383 lines)

```java
public void runTask(CicsTask task) {
    log.info("Cocrdlic: runTask");
    // 0000-MAIN: INITIALIZE CC-WORK-AREA WS-MISC-STORAGE WS-COMMAREA
    Ws w = new Ws();
    // MOVE LIT-THISTRANID TO WS-TRANID (never read again); SET WS-ERROR-MSG-OFF
    w.errorMsg = x("", 75);
    int calen = !task.hasCommarea() ? 0 : (task.eibcalen() == null ? 414 : task.eibcalen());
    if (calen == 0) {
        w.cc = blankCommarea();
        w.resetThis();
        w.cc.setCdemoFromTranid(x(TRAN, 4));
        w.cc.setCdemoFromProgram(x(PGM, 8));
        w.cc.setCdemoUserType("U");
        w.cc.setCdemoPgmContext(0);
...
```

```java
private int p0() {
    // INITIALIZE CC-WORK-AREA WS-MISC-STORAGE WS-COMMAREA
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f70_CC_WORK_AREA.storage(), f70_CC_WORK_AREA.offset() +
    Cobol.moveFigurative(Figurative.ZEROS, Field.binary(f1_WS_MISC_STORAGE.storage(), f1_WS_MISC_STORAGE.offset() + 0,
    Cobol.moveFigurative(Figurative.ZEROS, Field.binary(f1_WS_MISC_STORAGE.storage(), f1_WS_MISC_STORAGE.offset() + 4,
    Cobol.moveFigurative(Figurative.SPACES, Field.alphanumeric(f1_WS_MISC_STORAGE.storage(), f1_WS_MISC_STORAGE.offset
...
```

#### task-api: carddemo-userlist SEND-USRLST-SCREEN

model `sendUsrlstScreen` (12 lines) vs det (269 lines)

```java
void sendUsrlstScreen() {
    populateHeaderInfo();
    put("ERRMSG", message);
    // MOVE -1 TO USRIDINL holds at every SEND of this program: cursor on USRIDIN
    CicsTask.MapSubfields sub = new CicsTask.MapSubfields().cursor("USRIDIN");
    Cousr0aScreen screen = Cousr0aScreen.fromValues(new LinkedHashMap<>(scr));
    if (sendErase) {
        task.sendMap(Cousr0aScreen.MAP, Cousr0aScreen.MAPSET, screen, sub, "ERASE", "CURSOR");
    } else {
        task.sendMap(Cousr0aScreen.MAP, Cousr0aScreen.MAPSET, screen, sub, "CURSOR");
    }
}
```

```java
private int p9() {
    // PERFORM POPULATE-HEADER-INFO
    perform(11, 11);
    // MOVE WS-MESSAGE TO ERRMSGO OF COUSR0AO
    Cobol.move(f4_WS_MESSAGE, f763_ERRMSGO, CS);
    // IF SEND-ERASE-YES
    if (Cobol.compare(f8_WS_SEND_ERASE_FLG, "Y", CS) == 0) {
        // EXEC CICS SEND MAP('COUSR0A') MAPSET('COUSR00') FROM(COUSR0AO) ERASE CURSOR END-EXEC
        java.util.Map<String, String> values10 = new java.util.LinkedHashMap<>();
        CicsTask.MapSubfields sub11 = new CicsTask.MapSubfields();
        values10.put("TRNNAME", Cobol.text(f415_TRNNAMEO, CS));
        DetCics.subfields(sub11, "TRNNAME", f54_TRNNAMEL, f57_TRNNAMEA, f411_TRNNAMEC, f413_TRNNAMEH, CS);
        values10.put("TITLE01", Cobol.text(f421_TITLE01O, CS));
        DetCics.subfields(sub11, "TITLE01", f60_TITLE01L, f63_TITLE01A, f417_TITLE01C, f419_TITLE01H, CS);
...
```

#### optional-stream: carddemo-userlist RECEIVE-USRLST-SCREEN

model `receiveUsrlstScreen` (11 lines) vs det (191 lines)

```java
void receiveUsrlstScreen() {
    // RESP is never tested by the program: MAPFAIL leaves the previous screen storage in place
    Optional<Cousr0aScreen> in = task.receive(Cousr0aScreen.MAP, Cousr0aScreen.MAPSET, Cousr0aScreen.class);
    if (in.isPresent()) {
        for (Map.Entry<String, String> e : in.get().screenValues().entrySet()) {
            put(e.getKey(), e.getValue() == null ? "" : e.getValue());
        }
    }
    respCd = in.isPresent() ? 0 : 36;
    reasCd = 0;
}
```

```java
private int p10() {
    // EXEC CICS RECEIVE MAP('COUSR0A') MAPSET('COUSR00') INTO(COUSR0AI) RESP(WS-RESP-CD) RESP2(WS-REAS-CD) END-EXEC
    java.util.Optional<Cousr0aScreen> received16 = task.receive("COUSR0A", "COUSR00", Cousr0aScreen.class);
    int resp18 = received16.isPresent() ? 0 : 36;
    if (received16.isPresent()) {
        java.util.Arrays.fill(f52_COUSR0AI.storage().bytes, f52_COUSR0AI.offset(), f52_COUSR0AI.offset() + f52_COUSR0A
        java.util.Map<String, String> typed17 = received16.get().screenValues();
        if (typed17.get("TRNNAME") != null) {
            DetCics.typed(f59_TRNNAMEI, f54_TRNNAMEL, typed17.get("TRNNAME"), CS);
        }
        if (typed17.get("TITLE01") != null) {
            DetCics.typed(f65_TITLE01I, f60_TITLE01L, typed17.get("TITLE01"), CS);
        }
        if (typed17.get("CURDATE") != null) {
...
```

#### string-concat: carddemo-tranadd VALIDATE-INPUT-DATA-FIELDS

model `validateInputDataFields` (68 lines) vs det (262 lines)

```java
private void validateInputDataFields() {
    if (errFlg) {
        // DEFECT (kept, unreachable): every error sends the screen and RETURNs, so ERR-FLG is
        // never on here. Fix: none needed; remove the dead block.
        scr.setTtypcd(sp(2));
        scr.setTcatcd(sp(4));
        scr.setTrnsrc(sp(10));
        scr.setTrnamt(sp(12));
        scr.setTdesc(sp(60));
        scr.setTorigdt(sp(10));
        scr.setTprocdt(sp(10));
        scr.setMid(sp(9));
        scr.setMname(sp(30));
        scr.setMcity(sp(25));
...
```

```java
private int p3() {
    // IF ERR-FLG-ON
    if (Cobol.compare(f9_WS_ERR_FLG, "Y", CS) == 0) {
        // MOVE SPACES TO TTYPCDI OF COTRN2AI TCATCDI OF COTRN2AI TRNSRCI OF COTRN2AI TRNAMTI OF COTRN2AI TDESCI OF CO
        Cobol.moveFigurative(Figurative.SPACES, f113_TTYPCDI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f119_TCATCDI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f125_TRNSRCI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f137_TRNAMTI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f131_TDESCI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f143_TORIGDTI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f149_TPROCDTI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f155_MIDI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f161_MNAMEI, CS);
        Cobol.moveFigurative(Figurative.SPACES, f167_MCITYI, CS);
...
```



## Reproduce

```sh
python tests/tools/det_port.py run --all-cases --translate-only --work DET
python tests/tools/construct_map.py scan --det-root DET [--model-root DIR] --work W
python tests/tools/construct_map.py analyze --work W        # W/correspondence.md, W/correspondence.json
```
