"""#3821: an equivalence claim names the environment it holds in.

Both harness sides used to run with the host's defaults (the JVM inherited its locale and time zone),
so a port that formats with the default locale passed on an en-US machine and was wrong in Bangkok. The
Java side now runs under pinned JVM environments -- each a default locale and time zone -- and every run
must equal the one COBOL run; the report says which environments and which key order a claim covers.
"""

import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_inputs as ei  # noqa: E402
import equivalence_java as ej  # noqa: E402

E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")


def test_named_and_written_environments():
    assert ej.environment("thai") == {"name": "thai", "locale": "th-TH-u-nu-thai", "tz": "Asia/Bangkok"}
    assert ej.environment("sv-SE/Europe/Stockholm") == {"name": "sv-SE/Europe/Stockholm", "locale": "sv-SE",
                                                        "tz": "Europe/Stockholm"}  # fmt: skip
    assert ej.environment("fr-FR")["tz"] == "UTC"
    assert ej.jvm_args(ej.environment("turkish")) == "-Dequivalence.locale=tr-TR -Dequivalence.tz=Europe/Istanbul"
    assert ej.jvm_args({**ej.environment("default"), "encoding": "Cp1252"}).endswith("-Dfile.encoding=Cp1252")


def test_the_cli_and_the_case_choose_the_environments():
    assert [e["name"] for e in eq._environments(None, {})] == ["default"]
    assert [e["name"] for e in eq._environments(None, {"environments": ["german"]})] == ["german"]
    assert [e["name"] for e in eq._environments("turkish, thai", {})] == ["turkish", "thai"]
    assert [e["name"] for e in eq._environments("all", {})] == list(ej.ENVIRONMENTS)


def test_the_generated_test_sets_the_environment_before_spring_starts():
    case = eq.load_case("carddemo-intcalc")
    src = ej.equivalence_test(case)
    block = src[src.index("static {") : src.index("static final Charset TEXT")]
    assert 'Locale.forLanguageTag(System.getProperty("equivalence.locale", "en-US"))' in block
    assert 'TimeZone.getTimeZone(System.getProperty("equivalence.tz", "UTC"))' in block
    assert src.index("static {") < src.index("@Test")


def test_the_report_states_environments_and_key_order():
    case = {"name": "c", "program": "P", "corpus": "x", "program_source": "p.cbl"}
    report = {"java": "ported", "outputs": {}, "return_code": {"cobol": "0", "java": "0"},
              "environments": [{"name": "thai", "locale": "th-TH-u-nu-thai", "tz": "Asia/Bangkok", "ok": False}]}  # fmt: skip
    md = eq.report_markdown(case, report)
    assert "Key order covered: ASCII / ISO-8859-1 byte order on both sides" in md
    assert "| thai | th-TH-u-nu-thai | Asia/Bangkok | **no** |" in md


ACCOUNT = [{"name": "ACCT-ID", "offset": 0, "bytes": 8, "pic": "X(08)", "usage": None},
           {"name": "ACCT-NAME", "offset": 8, "bytes": 12, "pic": "X(12)", "usage": None}]  # fmt: skip


def _gen(alphabet=None):
    gen = {"records": 30, "seed": 5, **({"alphabet": alphabet} if alphabet else {})}
    return ei.generate_dataset("ACCT", {"reclen": 20, "organization": "indexed", "keys": [{"offset": 0, "length": 8}],
                                        "generate": gen}, ACCOUNT, {})[0]  # fmt: skip


def test_a_mixed_alphabet_reaches_the_keys_and_the_default_is_unchanged():
    mixed = _gen("mixed").decode("latin-1")
    assert any(c.islower() for c in mixed) and any(c in "ÆØÅæøåÄÖÜäöüßÉéÑñÇç" for c in mixed)
    upper = _gen().decode("latin-1")
    assert set(upper) <= set(ei._TEXT + " ") and _gen() == _gen("upper")
    old = random.Random(1)  # the default draw is what #3804 drew
    assert ei._text_value(random.Random(1), "X", 6, 1) == "".join(old.choice(ei._TEXT) for _ in range(6))


@E2E
def test_intcalc_holds_in_every_environment(tmp_path):
    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-intcalc", "--environments", "all",  # noqa: S603
                           "--keep", str(tmp_path)], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((tmp_path / "report.json").read_text())
    assert [e["name"] for e in report["environments"]] == list(ej.ENVIRONMENTS)
    assert all(e["ok"] for e in report["environments"])


@E2E
def test_a_locale_naive_port_passes_in_en_us_and_fails_in_thai(tmp_path):
    """The false pass #3821 is about: without Locale.ROOT, String.format prints Thai digits under th-TH."""
    port = tmp_path / "port"
    shutil.copytree(eq.CASES / "carddemo-intcalc" / "port", port)
    svc = port / "service" / "Cbact04cService.java"
    svc.write_text(svc.read_text(encoding="utf-8").replace("String.format(Locale.ROOT, ", "String.format("),
                   encoding="utf-8")  # fmt: skip
    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-intcalc", "--environments",  # noqa: S603
                           "default,thai", "--port", str(port), "--keep", str(tmp_path / "w")],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 1, proc.stdout[-3000:]
    report = json.loads((tmp_path / "w" / "report.json").read_text())
    assert {e["name"]: e["ok"] for e in report["environments"]} == {"default": True, "thai": False}
