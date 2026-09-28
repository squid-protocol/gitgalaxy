"""#3834: the Cultural Gauntlet (part 1: source dialect x data code page, checked statically;
part 2: the India slice -- cp1140, the rupee dialects, Asia/Kolkata, the runtime-static group and the
opt-in executed JVM layer; part 3: the target database's collation (D), the input data (E) and the
remaining runtime locales).

The gauntlet's sampled plan runs clean against its ratchet; a broken oracle is caught as a NEW failing
cell; the seed survives the trip through fixed-block EBCDIC in every page and every dialect; and the
zoned-sign oracle is independent of the converter -- IBM's overpunch bytes decoded by the page, and
the national zero signs pinned from IBM CDRA.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cultural_gauntlet as cg

from gitgalaxy.core.source_text import decode_source


@pytest.fixture(scope="module")
def sampled(tmp_path_factory):
    """The CI run: the default (sampled) plan, --ci against the committed baseline."""
    base = tmp_path_factory.mktemp("cultural_gauntlet")
    code = cg.main(["--ci", "--out", str(base / "out"), "--work", str(base / "work")])
    results = json.loads((base / "out" / "results.json").read_text(encoding="utf-8"))
    return code, results, (base / "out" / "report.md").read_text(encoding="utf-8")


def test_the_sampled_plan_passes_its_ratchet(sampled):
    code, results, report = sampled
    assert code == 0
    assert "| dialect | utf8 | cp037 |" in report and "skipped" in report
    # every page ran, and '£' met every page: the dialect that moves between pages
    ran = {(r["dialect"], r["page"]) for r in results.values() if "skipped" not in r}
    assert {("currency_pound", p) for p in cg.PAGES} <= ran
    assert {d for d, _ in ran} == {*cg.DIALECTS, *cg.COLLATION_TARGETS, *cg.INPUT_FORMATS}
    assert all((d, cg.CONTROL) in ran for d in cg.DIALECTS)
    # the euro sign is in none of the pre-euro pages: skipped and counted, never failed
    euro = [r for r in results.values() if r["dialect"] == "currency_euro" and r["page"] != cg.CONTROL]
    assert euro and all("skipped" in r and not r["diffs"] for r in euro)


def test_the_code_page_checks_pass_in_every_page(sampled):
    """The generated CobolRecords overpunches as each page does, and the scan reads each page's
    source to the declared facts: the oracle is sound where the converter is right."""
    _, results, _ = sampled
    for page in cg.PAGES:
        for group in ("records", "facts"):
            assert results[f"currency_pound|{page}|{group}"]["diffs"] == [], (page, group)


def test_a_broken_oracle_is_a_new_failing_cell(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(cg.DIALECTS["plain"]["expect"], "limit_literal", "12345.68")
    code = cg.main(["--ci", "--full", "--only", "plain", "--pages", "cp273", "--work", str(tmp_path)])
    assert code == 1
    assert (
        "NEW FAILING CELL plain|cp273|facts: WS-LIMIT VALUE: want '12345.68', got '12345.67'" in capsys.readouterr().out
    )


def _canned(monkeypatch, failing: dict, baseline: dict, tmp_path):
    monkeypatch.setattr(cg, "BASELINE", tmp_path / "baseline.txt")
    cg.write_baseline(baseline)
    results = {cid: {"dialect": "plain", "page": "cp037", "group": "facts", "diffs": [d] if d else []}
               for cid, d in failing.items()}  # fmt: skip
    monkeypatch.setattr(cg, "run", lambda *_, **__: results)


def test_the_ratchet_is_the_unicode_gauntlets(monkeypatch, tmp_path, capsys):
    """A listed failure passes CI, a new one fails it, a listed cell that now passes asks for the
    baseline to be lowered without failing, and a listed cell this run did not run is left alone."""
    _canned(monkeypatch, {"a|cp037|facts": "x", "b|cp037|facts": ""}, {"a|cp037|facts": "x", "b|cp037|facts": "y",
                                                                       "c|cp297|facts": "z"}, tmp_path)  # fmt: skip
    assert cg.main(["--ci", "--work", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "1 baseline cells now pass -- lower the baseline" in out and "b|cp037|facts" in out
    assert "c|cp297|facts" not in out
    _canned(monkeypatch, {"a|cp037|facts": "x", "d|cp037|facts": "new"}, {"a|cp037|facts": "x"}, tmp_path)
    assert cg.main(["--ci", "--work", str(tmp_path)]) == 1
    assert "NEW FAILING CELL d|cp037|facts: new" in capsys.readouterr().out


def test_the_baseline_is_one_mergeable_line_per_cell(monkeypatch, tmp_path):
    monkeypatch.setattr(cg, "BASELINE", tmp_path / "baseline.txt")
    cg.write_baseline({"b|cp037|ticket": "multi\nline", "a|cp273|facts": "one"})
    body = [x for x in (tmp_path / "baseline.txt").read_text(encoding="utf-8").splitlines() if not x.startswith("#")]
    assert body == ["a|cp273|facts\tone", "b|cp037|ticket\tmulti line"]
    attrs = (Path(__file__).resolve().parents[2] / ".gitattributes").read_text(encoding="utf-8")
    assert "tests/cultural_gauntlet/baseline.txt merge=union" in attrs


def test_every_committed_baseline_cell_is_a_cell_of_the_full_plan():
    cells = {f"{d}|{c}|{g}" for d, c in cg.plan(full=True) for g in cg.groups(d, execute=True, db=True)}
    assert set(cg.read_baseline()) <= cells


# ---- the seed as raw EBCDIC ---------------------------------------------------------------------
@pytest.mark.parametrize("page", cg.PAGES)
@pytest.mark.parametrize("dialect", sorted(cg.DIALECTS))
def test_the_seed_reads_back_from_fixed_block_ebcdic(dialect, page):
    """80-byte card images, no line ends, read back through the engine's declared decode; a dialect
    character the page lacks (the euro sign) refuses the cell rather than mangling it."""
    text = cg.seed_text(dialect)
    data = cg.encode(text, page)
    if any(sign in text and not _page_holds(page, sign) for sign in "€₹"):
        assert data is None
        return
    assert data is not None and len(data) == 80 * len(text.splitlines()) and b"\n" not in data
    got = decode_source(data, declared=page)
    assert got.how == "declared"
    assert [line.rstrip() for line in got.text.splitlines()] == text.splitlines()


def test_the_dialect_meets_the_page():
    """'£' is a different byte in each page (0xB1 US, 0x5B UK, where the US page keeps `$`)."""
    line = "           CURRENCY SIGN IS '£'."
    assert cg.encode(line, "cp037")[29] == 0xB1 and cg.encode(line, "cp285")[29] == 0x5B
    assert cg.encode("$", "cp285")[0] == 0x4A and cg.encode("$", "cp037")[0] == 0x5B  # padded to a card


def _page_holds(page: str, char: str) -> bool:
    try:
        char.encode(page)
    except UnicodeEncodeError:
        return False
    return True


# ---- the zoned-sign oracle ----------------------------------------------------------------------
@pytest.mark.parametrize("page", cg.PAGES)
def test_the_overpunch_characters_are_the_pages_own(page):
    """The page's codec shows IBM's sign bytes as CDRA says: the zero signs move, A-I / J-R do not."""
    plus, minus = cg.CDRA_ZERO_SIGNS[page]
    assert cg.POSITIVE_BYTES.decode(page) == plus + "ABCDEFGHI"
    assert cg.NEGATIVE_BYTES.decode(page) == minus + "JKLMNOPQR"


def test_the_sign_check_names_each_value_a_codec_gets_wrong():
    us = (
        'private static final String POSITIVE = "{ABCDEFGHI";\n    private static final String NEGATIVE = "}JKLMNOPQR";'
    )
    assert cg._sign_diffs(us, "cp037") == []
    diffs = cg._sign_diffs(us, "cp277")  # the US table on a Danish page: only +0 and -0 differ
    assert diffs == ["CobolRecords +0: cp277 byte 0xC0 is 'æ', the codec overpunches '{'",
                     "CobolRecords -0: cp277 byte 0xD0 is 'å', the codec overpunches '}'"]  # fmt: skip
    escaped = us.replace('"{', '"\\u00e4').replace('"}', '"\\u00fc')  # the forge escapes non-ASCII
    assert cg._sign_diffs(escaped, "cp273") == []


# ---- part 2: the India slice ----------------------------------------------------------------------
def test_the_india_cells_run_in_the_sampled_plan(sampled):
    """INR in the control and cp1140, plain in cp1140, '₹' in the control; the report names the India row."""
    _, results, report = sampled
    ran = {(r["dialect"], r["page"]) for r in results.values() if "skipped" not in r}
    assert {("currency_inr", "utf8"), ("currency_inr", "cp1140"), ("plain", "cp1140"),
            ("currency_rs_lakh", "utf8"), ("currency_rupee", "utf8")} <= ran  # fmt: skip
    assert all("skipped" in r for r in results.values() if r["dialect"] == "currency_rupee" and r["page"] != "utf8")
    assert "| dialect | utf8 | cp037 | cp273 | cp277 | cp278 | cp285 | cp297 | cp1140 |" in report
    assert "## India" in report and "India: " in report and "(zone Asia/Kolkata" in report
    # the India page reads, decodes its signs, and never reaches for the JVM's defaults
    for group in ("facts", "records", "runtime-static"):
        assert results[f"plain|cp1140|{group}"]["diffs"] == [], group
        assert results[f"currency_inr|cp1140|{group}"]["diffs"] == [], group


def test_the_rupee_dialects_declare_their_sizes():
    """Literals, as part 1's EUR / U: 'INR ' takes 4 bytes for its first position, 'Rs' 2; the lakh
    grouping `KK,KK,KK9.99` has 6 integer digits; no symbol is R (reserved: `CR`)."""
    inr, rs, rupee = (cg.DIALECTS[d] for d in cg.INDIA_DIALECTS)
    assert "CURRENCY SIGN IS 'INR ' WITH PICTURE SYMBOL 'I'" in inr["special"] and inr["edited"] == "III,II9.99"
    assert inr["expect"]["record_bytes"] == 43 and inr["expect"]["due_sql"] == "DECIMAL(7, 2)"
    assert "CURRENCY SIGN IS 'Rs' WITH PICTURE SYMBOL 'K'" in rs["special"] and rs["edited"] == "KK,KK,KK9.99"
    assert rs["expect"]["layout"][-1] == ("ACCT-DUE-ED", 30, 13) and rs["expect"]["due_sql"] == "DECIMAL(8, 2)"
    assert rupee["expect"]["special_names"] == [("CURRENCY", "₹", "₹")]
    assert rupee["expect"]["edited"] == " ₹1,234.50"
    assert all(sym != "R" for d in cg.INDIA_DIALECTS for _, _, sym in cg.DIALECTS[d]["expect"]["special_names"])
    # an India cell's mainframe runs in IST; a Western cell's in UTC
    assert cg.cell_zone("currency_inr", "utf8") == cg.cell_zone("plain", "cp1140") == "Asia/Kolkata"
    assert cg.cell_zone("plain", "cp037") == "UTC"


def test_cp1140_is_cp037_with_the_euro_sign():
    """Independently of the converter: cp1140's overpunch bytes 0xC0-0xC9 / 0xD0-0xD9 decode as cp037's,
    and the two pages differ at 0x9F alone (the euro sign where cp037 has the currency sign ¤)."""
    assert cg.POSITIVE_BYTES.decode("cp1140") == "{ABCDEFGHI"
    assert cg.NEGATIVE_BYTES.decode("cp1140") == "}JKLMNOPQR"
    every = bytes(range(256))
    assert [b for b in every if every[b : b + 1].decode("cp1140") != every[b : b + 1].decode("cp037")] == [0x9F]
    assert "€".encode("cp1140") == b"\x9f" and not _page_holds("cp1140", "₹")


# ---- the runtime-static group ---------------------------------------------------------------------
_CLOCK = """@Value("${gitgalaxy.zone:${gitgalaxy.culture.zone:Asia/Kolkata}}") String zoneId) {
        this.zone = ZoneId.of(zoneId == null || zoneId.trim().isEmpty() ? "Asia/Kolkata" : zoneId.trim());
        return pinned.isEmpty() ? ZonedDateTime.now(zone) : ZonedDateTime.of(LocalDateTime.parse(pinned), zone);"""
_ROOTED = {"batch/MainframeClock.java": _CLOCK,
           "entity/vsam/CobolRecords.java": "String upper = s.toUpperCase(Locale.ROOT);",
           "batch/DatasetResolver.java": 'return base.resolve(String.format(Locale.ROOT, "G%04dV00", g));',
           "batch/JclConditions.java": "Matcher m = TEST.matcher(cond.toUpperCase(Locale.ROOT));"}  # fmt: skip


@pytest.mark.parametrize(
    "line, what",
    [
        ("Locale here = Locale.getDefault();", "Locale.getDefault()"),
        ('String s = String.format("%,.2f", amount);', "String.format without a Locale"),
        ("return key.trim().toUpperCase();", "toUpperCase() / toLowerCase() without a Locale"),
        ("NumberFormat f = NumberFormat.getInstance();", "NumberFormat without a Locale"),
        ('DecimalFormat f = new DecimalFormat("#,##0.00");', "DecimalFormat without its symbols"),
        ("ZoneId z = ZoneId.systemDefault();", "ZoneId.systemDefault()"),
        ("TimeZone z = TimeZone.getDefault();", "TimeZone.getDefault()"),
        ("LocalDate today = LocalDate.now();", "now() without a zone"),
        ("Calendar c = Calendar.getInstance();", "a calendar without a zone"),
        ("byte[] b = value.getBytes();", "the default charset"),
        # part 3: the tr-TR / ar-EG / th-TH-u-nu-thai / de-DE traps
        (
            'DateTimeFormatter f = DateTimeFormatter.ofPattern("dd MMM uuuu");',
            "DateTimeFormatter.ofPattern without a Locale (month, day and AM/PM names, week fields)",
        ),
        (
            "DateTimeFormatter f = DateTimeFormatter.ofLocalizedDate(FormatStyle.SHORT);",
            "a localized DateTimeFormatter (the default locale's pattern)",
        ),
        (
            'DateFormat f = new SimpleDateFormat("yyyyMMdd");',
            "SimpleDateFormat without a Locale (Thai digits, the Buddhist calendar)",
        ),
        ("Collator c = Collator.getInstance();", "Collator without a Locale"),
        (
            "boolean d = Character.isDigit(c);",
            "Character.isDigit / digit / getNumericValue (any script's digits, #3831)",
        ),
    ],
)
def test_the_runtime_static_group_names_each_jvm_default(line, what):
    src = {
        **_ROOTED,
        "entity/vsam/CobolEdit.java": f"class CobolEdit {{\n    // ZoneId.systemDefault() in a comment\n    {line}\n}}",
    }
    assert cg.runtime_static_diffs(src, "Asia/Kolkata") == [f"entity/vsam/CobolEdit.java:3: {what}: `{line}`"]


def test_the_runtime_static_group_passes_the_explicit_forms():
    ok = """String.format(Locale.ROOT, "%02X", b); s.toUpperCase(Locale.ROOT); Character.toUpperCase(c);
        NumberFormat.getInstance(Locale.ROOT); new DecimalFormat("0.00", DecimalFormatSymbols.getInstance(Locale.ROOT));
        ZonedDateTime.now(zone); LocalDate.now(clock); value.getBytes(text); /* Locale.getDefault() */
        DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSZ"); DateTimeFormatter.ofPattern("hh:mm a", Locale.US);
        new SimpleDateFormat("yyyyMMdd", Locale.ROOT); Collator.getInstance(Locale.ROOT);"""
    assert cg.runtime_static_diffs({**_ROOTED, "x/Ok.java": ok}, "Asia/Kolkata") == []
    # #3824 / #3823: the declared zone and Locale.ROOT must be there -- a clock in UTC is an India finding
    assert cg.runtime_static_diffs(_ROOTED, "UTC")[0] == \
        'batch/MainframeClock.java: missing `@Value("${gitgalaxy.zone:${gitgalaxy.culture.zone:UTC}}")`'  # fmt: skip
    assert "batch/JclConditions.java: not generated" in cg.runtime_static_diffs({}, "UTC")[-1]


def test_a_planted_locale_default_in_the_generated_java_is_caught(tmp_path):
    """The real pipeline's Java for plain x cp1140 passes; the same Java with one Locale.getDefault()
    planted into its CobolEdit fails the cell's runtime-static group, naming file and line."""
    obs = cg._observe(tmp_path / "plain__cp1140", "plain", "cp1140")
    assert cg.check("plain", "cp1140", obs)["runtime-static"] == []
    edit = obs["java_sources"]["entity/vsam/CobolEdit.java"]
    planted = edit.replace(
        "        pic = expand(pic);", "        pic = expand(pic).toUpperCase(Locale.getDefault());", 1
    )
    assert planted != edit
    diffs = cg.check("plain", "cp1140", {**obs, "java_sources": {**obs["java_sources"],
                                                                  "entity/vsam/CobolEdit.java": planted}})  # fmt: skip
    line = planted.splitlines().index("        pic = expand(pic).toUpperCase(Locale.getDefault());") + 1
    assert diffs["runtime-static"] == [f"entity/vsam/CobolEdit.java:{line}: Locale.getDefault(): "
                                       "`pic = expand(pic).toUpperCase(Locale.getDefault());`"]  # fmt: skip


# ---- the executed layer (--run) -------------------------------------------------------------------
def _envs(**changes):
    ref = {**cg.RUN_EXPECT, "date": cg.RUN_DATE["Asia/Kolkata"], "edited": "x", "canary": "en-US UTC $1.00"}
    hindi = {**ref, "canary": "hi-IN Asia/Kolkata ₹1.00", **changes}
    return {"envs": {"default": ref, "hindi": hindi}}


def test_the_executed_layer_wants_identity_across_environments_and_the_declared_values():
    assert cg.runtime_run_diffs(_envs(), "Asia/Kolkata") == []
    assert cg.runtime_run_diffs(_envs(lakh="1,234,567.89"), "Asia/Kolkata") == [
        "lakh differs in hindi: '12,34,567.89' (default) vs '1,234,567.89'"]  # fmt: skip
    assert cg.runtime_run_diffs(_envs(canary="en-US UTC $1.00"), "Asia/Kolkata") == [
        "hindi: the JVM environment did not apply (canary 'en-US UTC $1.00')"]  # fmt: skip
    assert cg.runtime_run_diffs(_envs(), "UTC", edited=" $1,234.50") == [
        "date (default): want '2026032902300000+0000', got '2026032902300000+0530'",
        "edited (default): want ' $1,234.50', got 'x'"]  # fmt: skip


def test_the_executed_layer_skips_cleanly_without_a_jdk(monkeypatch, tmp_path):
    monkeypatch.setattr(cg, "jdk", lambda: None)
    assert "no JDK" in cg.execute_cell(tmp_path, "plain", "cp1140", {})["skipped"]


def test_the_executed_layer_runs_the_india_cell(tmp_path, capsys):
    """--run on INR x cp1140: the generated CobolRecords / CobolEdit / MainframeClock under hi-IN and en-IN
    in Asia/Kolkata print what the en-US / UTC reference prints -- the declared values."""
    if cg.jdk() is None:
        pytest.skip("no JDK (javac + java) on this machine")
    code = cg.main(["--ci", "--run", "--full", "--only", "currency_inr", "--pages", "cp1140",
                    "--work", str(tmp_path / "work"), "--out", str(tmp_path / "out")])  # fmt: skip
    results = json.loads((tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    assert code == 0, capsys.readouterr().out
    assert results["currency_inr|cp1140|runtime-run"]["diffs"] == []
    run = tmp_path / "work" / "currency_inr__cp1140" / "jvm"
    assert (run / "classes" / "CulturalGauntletDriver.class").is_file()


# ---- part 3, C: the remaining runtime locales ---------------------------------------------------------------
def test_the_run_layer_covers_every_locale_in_every_zone():
    """tr-TR, ar-EG, th-TH-u-nu-thai and de-DE each as the JVM's zone UTC, Asia/Kolkata and Europe/Berlin."""
    for locale in ("tr-TR", "ar-EG", "th-TH-u-nu-thai", "de-DE"):
        for zone in ("UTC", "Asia/Kolkata", "Europe/Berlin"):
            assert f"{locale}/{zone}" in cg.JVM_ENVIRONMENTS
    assert cg.JVM_ENVIRONMENTS[-1] == cg.REFERENCE_ENVIRONMENT and len(cg.JVM_ENVIRONMENTS) == 15
    # PINNED_CLOCK is Europe/Berlin's spring-forward day: 02:30 does not exist there
    assert cg.PINNED_CLOCK.startswith("2026-03-29T02:30")


def test_the_thai_environment_keeps_its_unicode_extension():
    """-Duser.extensions carries `-u-nu-thai`: without it the JVM is plain th-TH and prints ASCII digits."""
    assert cg.jvm_flags("th-TH-u-nu-thai/Europe/Berlin") == [
        "-Duser.language=th", "-Duser.timezone=Europe/Berlin", "-Duser.country=TH", "-Duser.extensions=u-nu-thai"]  # fmt: skip
    assert cg.jvm_flags("tr-TR/Asia/Kolkata") == ["-Duser.language=tr", "-Duser.timezone=Asia/Kolkata",
                                                 "-Duser.country=TR"]  # fmt: skip
    ref = {"canary": "en-US UTC $1.00", "x": "1"}
    lost = {"envs": {"default": ref, "th-TH-u-nu-thai/UTC": {**ref, "canary": "th-TH UTC ฿1.00"}}}
    assert cg._across_environments(lost["envs"]) == [
        "th-TH-u-nu-thai/UTC: the JVM prints no Thai digits (canary 'th-TH UTC ฿1.00')"]  # fmt: skip
    kept = {"default": ref, "th-TH-u-nu-thai/UTC": {**ref, "canary": "th-TH-u-nu-thai UTC ฿ \u0e51.\u0e50\u0e50"}}
    assert cg._across_environments(kept) == []


# ---- part 3, D: the target database's collation ---------------------------------------------------------
def test_the_collation_oracle_is_the_pages_byte_order():
    """Independent of the converter: each key space-padded to PIC X(8) in the page's bytes. EBCDIC puts
    lower case before upper and letters before digits; `ABC ` is `ABC`'s 8 bytes, a duplicate WRITE; the
    national letters sit where the page puts them (Å is 0x67 in cp037, 0x5B in cp277)."""
    us = cg.collation_oracle(cg.COLLATION_KEYS, "cp037", "A1")
    assert us["browse"] == "é1|ÄRGER|ÅS|ÑANDU|#1|@1|ØRE|abc|aBC|ÆBLE|A 1|A.1|A-1|Abc|ABC|A1|E1|NANDU|ZZ|1A|123"
    assert us["rejected"] == "ABC" and us["read-all"] == us["browse"]
    assert us["browse-from"] == "A1|E1|NANDU|ZZ|1A|123"
    assert us["browse-back"].startswith("A1|ABC|Abc|A-1|A.1|A 1|")
    dk = cg.collation_oracle(cg.COLLATION_KEYS, "cp277", "A1")
    assert dk["browse"].startswith("#1|é1|ÅS|ÄRGER|ÑANDU|ÆBLE|ØRE|@1|abc") and dk["browse"] != us["browse"]
    ascii_order = "|".join(sorted({k.rstrip() for k in cg.COLLATION_KEYS}))
    assert us["browse"] != ascii_order  # the keys tell EBCDIC from ASCII / code points


def _collation_sources(engine: str, page: str) -> dict:
    sources: dict = {}
    for rel, text in cg.collation_static_want(engine, page):
        sources[rel] = sources.get(rel, "") + text + "\n"
    sources["service/CustbatService.java"] = (
        '    public List<CustRec> readAllCustFile() {\n        return repo.findAll(Sort.by("custKeySort"));\n'
    )
    return sources


_KEY_RULE = ["Order and compare VSAM / DB2 keys by the source code page's bytes, as the mainframe does"]


@pytest.mark.parametrize("engine", ["h2", "postgresql", "mysql"])
def test_the_collation_static_group_holds_3822s_contract(engine):
    sources = _collation_sources(engine, "cp277")
    assert cg.collation_static_diffs(sources, _KEY_RULE, engine, "cp277") == []
    assert ("utf8mb4_bin" in sources["entity/vsam/CustRec.java"]) == (engine == "mysql")
    # the database's default collation on the key, a sort key in the wrong page, a readAll with no ORDER BY
    bare = {**sources, "entity/vsam/CustRec.java": sources["entity/vsam/CustRec.java"].replace("cp277", "cp037")}
    assert cg.collation_static_diffs(bare, _KEY_RULE, engine, "cp277") == [
        'entity/vsam/CustRec.java: missing `this.custKeySort = CobolRecords.sortKey(custKey, "cp277");`'
    ]
    heap = {**sources, "service/CustbatService.java": "public List<CustRec> readAllCustFile() {\n"
                                                        "        return custRecRepository.findAll();"}  # fmt: skip
    assert cg.collation_static_diffs(heap, [], engine, "cp277") == [
        "CustbatService.readAllCustFile: `return custRecRepository.findAll();` has no ORDER BY -- a sequential READ "
        "of the KSDS returns its records in key order (cp277 bytes, CUST_KEY_SORT)",
        "CUSTCICS port ticket: no key-order rule (#3822)"]  # fmt: skip


def test_the_generated_table_is_rendered_as_hibernate_creates_it():
    entity = """@Table(name = "vsam_cust")
    @Id
    @Column(name = "CUST_KEY", columnDefinition = "varchar(8) COLLATE \\"C\\"")
    private String custKey;

    @Column(name = "CUST_NAME", length = 20)
    private String custName;
    @Column(name = "CUST_BAL", precision = 9, scale = 2)
    private BigDecimal custBal;
"""
    assert cg.entity_ddl(entity) == ("vsam_cust", 'CREATE TABLE vsam_cust (CUST_KEY varchar(8) COLLATE "C" not null, '
                                     "CUST_NAME varchar(20), CUST_BAL numeric(9, 2), PRIMARY KEY (CUST_KEY))")  # fmt: skip
    with pytest.raises(ValueError, match="no @Id"):
        cg.entity_ddl(entity.replace("@Id", ""))


def test_the_db_layer_reads_all_as_the_generated_readall_orders():
    """#3945: the executed read-all runs the generated readAll's Sort.by, as the entity's columns; a bare
    findAll() sends no ORDER BY (the database's own order)."""
    entity = """    @Id
    @Column(name = "CUST_KEY", length = 8)
    private String custKey;

    @Column(name = "CUST_KEY_SORT", length = 16)
    private String custKeySort;
"""
    svc = "    public List<CustRec> readAllCustFile() {{\n        return repo.findAll({});\n"
    sources = {"entity/vsam/CustRec.java": entity,
               "service/CustbatService.java": svc.format('org.springframework.data.domain.Sort.by("custKeySort")')}
    assert cg.read_all_sql(sources, "vsam_t", "CUST_KEY") == "SELECT CUST_KEY FROM vsam_t ORDER BY CUST_KEY_SORT"
    both = {**sources, "service/CustbatService.java": svc.format('Sort.by("custKey", "custKeySort")')}
    assert cg.read_all_sql(both, "vsam_t", "CUST_KEY").endswith("ORDER BY CUST_KEY, CUST_KEY_SORT")
    bare = {**sources, "service/CustbatService.java": svc.format("")}
    assert cg.read_all_sql(bare, "vsam_t", "CUST_KEY") == "SELECT CUST_KEY FROM vsam_t"
    with pytest.raises(ValueError, match="no column"):
        cg.read_all_sql({**sources, "service/CustbatService.java": svc.format('Sort.by("nope")')}, "t", "K")


def test_the_database_answers_are_checked_against_the_mainframes():
    want = cg.collation_oracle(cg.COLLATION_KEYS, "cp037", cg.FROM_KEY)
    ok = {**want, "db-order": "#1|123|1A|A1"}
    assert cg.collation_db_diffs({"db": ok}, "cp037") == []
    heap = {**ok, "read-all": "ZZ|abc"}
    assert cg.collation_db_diffs({"db": heap}, "cp037") == [
        f"read-all [the batch step's sequential READ (the generated readAll's ORDER BY)]: want {want['read-all']!r}, "
        "got 'ZZ|abc'"]  # fmt: skip
    # the canary: keys whose database order IS the mainframe's could not have caught a wrong collation
    assert cg.collation_db_diffs({"db": {**want, "db-order": want["browse"]}}, "cp037")[0].startswith("canary: ")
    assert cg.collation_db_diffs({"error": "javac: x"}, "cp037") == ["executed layer failed: javac: x"]


def test_the_sampled_plan_runs_part_3(sampled):
    """Each database target and each DB2 format runs in the sampled plan (static layers), and passes: #3945's
    sequential READ orders by the sort column."""
    _, results, report = sampled
    ran = {(r["dialect"], r["page"]) for r in results.values() if "skipped" not in r}
    assert set(cg.SAMPLED_COLLATION.items()) | set(cg.SAMPLED_INPUT.items()) <= ran
    for target, page in cg.SAMPLED_COLLATION.items():
        assert results[f"{target}|{page}|collation-static"]["diffs"] == [], target
        assert results[f"{target}|{page}|runtime-static"]["diffs"] == []
    for name, page in cg.SAMPLED_INPUT.items():
        for group in cg.INPUT_GROUPS:
            assert results[f"{name}|{page}|{group}"]["diffs"] == [], (name, group)
    assert "## Part 3: target database collation (D) and input data (E)" in report
    assert "| collation_postgresql_en_us |" in report and "| input_eur |" in report


def test_the_db_layer_skips_what_this_machine_does_not_have(monkeypatch, tmp_path):
    """MySQL is never faked; without the H2 jar or the PostgreSQL binaries those targets are skipped, and say why."""
    monkeypatch.setattr(cg, "_maven_jar", lambda *_: None)
    with cg.databases(tmp_path) as specs:
        assert "no MySQL server" in specs["collation_mysql_ai_ci"]["skipped"]
        assert specs["collation_h2"] == {"skipped": "no H2 jar in ~/.m2"} or cg.jdk() is None
        assert "skipped" in specs["collation_postgresql_c"] and "skipped" in specs["collation_postgresql_en_us"]
    assert cg.execute_db(tmp_path, "collation_h2", "cp037", {}, {"skipped": "why"}) == {"skipped": "why"}


def _db_available(target: str) -> bool:
    if cg.jdk() is None:
        return False
    if target == "collation_h2":
        return cg._maven_jar("com.h2database", "h2") is not None
    return cg._maven_jar("org.postgresql", "postgresql") is not None and cg._pg_bin() is not None


@pytest.mark.parametrize("target, page", [("collation_h2", "cp273"), ("collation_postgresql_en_us", "cp277")])
def test_the_db_layer_runs_the_generated_table(target, page, tmp_path, capsys):
    """--db for real: the generated DDL, the keys through the generated CobolRecords, the generated finders'
    SQL. Every browse matches the mainframe, and so does the sequential READ (#3945: the generated readAll's
    ORDER BY)."""
    if not _db_available(target):
        pytest.skip(f"{target}: its database is not on this machine")
    code = cg.main(["--ci", "--db", "--full", "--only", target, "--pages", page,
                    "--work", str(tmp_path / "work"), "--out", str(tmp_path / "out")])  # fmt: skip
    assert code == 0, capsys.readouterr().out
    results = json.loads((tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    cell = results[f"{target}|{page}|collation-db"]
    assert cell["diffs"] == []
    assert cell["database"] == ("en_US.UTF-8" if "en_us" in target else cell["database"])
    assert cell["database"].startswith(("H2 ", "en_US"))


# ---- part 3, E: the input data ------------------------------------------------------------------------------
def test_the_input_answers_are_literals():
    """DB2's character forms (SQL Reference, "Datetime values"), GnuCOBOL's ROUNDED ties and NUMVAL verdicts."""
    assert cg.DB2_CHARACTER_FORMS == {"eur": ("26.09.2026", "14.30.05"), "usa": ("09/26/2026", "02:30 PM"),
                                      "iso": ("2026-09-26", "14.30.05")}  # fmt: skip
    assert cg.TIES_WANT == {"WS-UP": "0.03 -0.03 0.04 3 -3 4", "WS-EVEN": "0.02 -0.02 0.04 2 -2 4"}
    assert len(cg.NUMVAL_WANT.split("|")) == len(cg.NUMVAL_INPUTS)
    assert all(not ch.isascii() for text in cg.NUMVAL_INPUTS[1:5] for ch in text)
    assert cg.input_run_want("usa")["date"] == "09/26/2026 02:30 PM"


def test_the_input_static_group_types_by_picture_and_sql_type_not_by_name():
    obs = {"java_sources": {}, "schema_sql": "", "ticket_rounding": [], "ticket_rules": []}
    diffs = cg.input_static_diffs(obs, "eur")
    assert "entity/vsam/KundRec.java: not generated (want `r.datum = CobolRecords.toInteger(CobolRecords." \
           "zoned(rec, 8, 8, 0, text));`)" in diffs  # fmt: skip
    assert "clean-room schema DATUM: want 'INTEGER', got None" in diffs
    assert "ticket rules: no NUMVAL rule (#3831)" in diffs


def test_the_input_layer_runs_under_every_environment(tmp_path, capsys):
    """--run on EUR x cp273: Db2Dates and CobolRecords in 15 JVM environments print the declared answers;
    #3946: parseTimestamp rejects Arabic-Indic digits, as DB2 does."""
    if cg.jdk() is None:
        pytest.skip("no JDK (javac + java) on this machine")
    code = cg.main(["--ci", "--run", "--full", "--only", "input_eur", "--pages", "cp273",
                    "--work", str(tmp_path / "work"), "--out", str(tmp_path / "out")])  # fmt: skip
    assert code == 0, capsys.readouterr().out
    results = json.loads((tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    assert results["input_eur|cp273|input-static"]["diffs"] == []
    assert results["input_eur|cp273|runtime-run"]["diffs"] == []
