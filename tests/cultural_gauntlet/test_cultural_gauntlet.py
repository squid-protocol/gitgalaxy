"""#3834: the Cultural Gauntlet (part 1: source dialect x data code page, checked statically;
part 2: the India slice -- cp1140, the rupee dialects, Asia/Kolkata, the runtime-static group and the
opt-in executed JVM layer).

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
    assert {d for d, _ in ran} == set(cg.DIALECTS) and all((d, cg.CONTROL) in ran for d in cg.DIALECTS)
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
    cells = {f"{d}|{c}|{g}" for d, c in cg.plan(full=True) for g in [*cg.GROUPS, cg.RUN_GROUP]}
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
_CLOCK = """@Value("${gitgalaxy.zone:Asia/Kolkata}") String zoneId) {
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
        ZonedDateTime.now(zone); LocalDate.now(clock); value.getBytes(text); /* Locale.getDefault() */"""
    assert cg.runtime_static_diffs({**_ROOTED, "x/Ok.java": ok}, "Asia/Kolkata") == []
    # #3824 / #3823: the declared zone and Locale.ROOT must be there -- a clock in UTC is an India finding
    assert cg.runtime_static_diffs(_ROOTED, "UTC")[0] == \
        'batch/MainframeClock.java: missing `@Value("${gitgalaxy.zone:UTC}")`'  # fmt: skip
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
