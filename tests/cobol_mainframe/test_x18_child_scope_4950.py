"""#4950 (register X18): no burned-estate RUN TRANSID child holds a region resource, and the runner's child schedule has no
burned consumer.

The harness refuses a dispatched child's ENQ / DEQ / counter / SQL (R1: `equivalence_cics.child_region_resource`), and the
cics-crucible runner refuses a waiting parent with a RUN child by name (`cics_crucible.async_refusals`). Both stay open
only until a burned program needs them. This pins that none does today: if a burned child gains one, this fails and R1
becomes real work."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import equivalence_cics as ec  # noqa: E402

CASES = sorted((ROOT / "tests" / "equivalence").glob("*/case.json"))
# a RUN TRANSID parent in the burned corpora (the programs that may name a child): comment lines are skipped
_RUN = re.compile(r"(?i)^.{6}[^*/].*\bEXEC\s+CICS\s+RUN\s+TRANSID\b")


def _corpora() -> Path | None:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    for c in (Path(env) if env else None, ROOT / ".mainframe_corpora"):
        if c and c.is_dir():
            return c
    return None


def _cases_with_children():
    out = []
    for path in CASES:
        case = json.loads(path.read_text(encoding="utf-8"))
        if case.get("child_programs"):
            out.append((path.parent.name, case))
    return out


def test_the_cases_with_children_are_the_five_known_ones():
    """A new case with `child_programs` must be checked below by being listed here (and its children read)."""
    assert [n for n, _ in _cases_with_children()] == [
        "asynccc-asyncpnt",
        "cbsa-bnk1ccs",
        "cbsa-bnk1ccs-generated",
        "cbsa-crecust",
        "cbsa-crecust-generated",
    ]


def test_every_burned_child_program_holds_no_region_resource():
    root = _corpora()
    if root is None:
        pytest.skip("no mainframe corpora")
    checked = 0
    for name, case in _cases_with_children():
        corpus = root / case["corpus"]
        if not corpus.is_dir():
            pytest.skip(f"corpus {case['corpus']} not available")
        sources = {p["program"].upper(): p["program_source"] for p in case["programs"]}
        for program in sorted({p.upper() for p in case["child_programs"].values()}):
            text = (corpus / sources[program]).read_text(encoding="latin-1")
            assert ec.child_region_resource(text) is None, f"{name}: child {program} holds a region resource (R1)"
            checked += 1
    assert (
        checked >= 12
    )  # asyncpnt's seven, CRDTAGY1-5 (the bnk1ccs and crecust cases, generated ones included, share them)


def test_only_asyncpnt_csstats2_and_crecust_run_children_in_the_burned_corpora():
    root = _corpora()
    if root is None:
        pytest.skip("no mainframe corpora")
    hits = set()
    for case_corpus in ("cics-async-api-credit-card-application-example", "cics-banking-sample-application-cbsa",
                        "cics-genapp", "aws-mainframe-modernization-carddemo", "zecs",
                        "dbb-mortgage-application"):  # fmt: skip
        base = root / case_corpus
        if not base.is_dir():
            pytest.skip(f"corpus {case_corpus} not available")
        for f in base.rglob("*"):
            if f.suffix.lower() in (".cbl", ".cob") and f.is_file():
                if any(_RUN.search(ln) for ln in f.read_text(encoding="latin-1").splitlines()):
                    hits.add(f.stem.upper())
    assert hits == {"ASYNCPNT", "CSSTATS2", "CRECUST"}, hits
