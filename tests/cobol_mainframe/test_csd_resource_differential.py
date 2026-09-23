"""
#3356: CSD resource definitions as a refraction-differential datum and a drafted
answer-key field.

No forge reads CSD resources, so -- as for the JCL DSN (#3345) -- the compared side
is the answer key's own CSD reader (`csd_resource_definitions`) over the raw deck,
against the engine's csd_resource_data. A delta is a real finding on one side,
never a stated absence, and it adjudicates only once a deck is signed off
`resources_validated`.
"""

import json
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402
import refraction_differential as rd  # noqa: E402

KEY_DIR = Path(__file__).resolve().parent / "answer_key"
EXCERPTS = Path(__file__).resolve().parent / "refraction_excerpts"
DECK = "etc/install/base/installjcl/BANK.csd"


@pytest.fixture(scope="module")
def mini_repo(tmp_path_factory):
    return tmp_path_factory.mktemp("csd_repo")


def _csd_row(old=(), db=()):
    return {"file": DECK, "language": "csd_deck", "csd": {"old": sorted(old), "db": sorted(db)}}


V_OK = "FILE(CUSTOMER)@10 group=BANK dsname=CBSA.CICSBSA.CUSTOMER record_format=V key_length=16 record_size=259"
V_DB = "FILE(CUSTOMER)@10 group=BANK dsname=CBSA.CICSBSA.CUSTOMER record_format=V"


def test_a_csd_resource_delta_is_a_real_finding_not_a_stated_absence(mini_repo):
    classified = rd.classify(mini_repo, [_csd_row(old=[V_OK], db=[V_DB])], None)
    assert {(d["field"], d["side"], d["value"], d["cause"]) for d in classified} == {
        ("csd_resource", "old", V_OK, rd.UNEXPLAINED),
        ("csd_resource", "db", V_DB, rd.UNEXPLAINED),
    }


def test_agreeing_decks_produce_no_delta(mini_repo):
    assert rd.classify(mini_repo, [_csd_row(old=[V_OK], db=[V_OK])], None) == []


def test_csd_rows_stay_out_of_the_cobol_summary(mini_repo):
    rows = [_csd_row(old=[V_OK], db=[V_OK])]
    assert rd.to_markdown({"repo": "r", "commit": "0" * 8}, rows).count(DECK) == 0


def test_csd_resource_verdict_needs_explicit_validation(mini_repo):
    resources = ak.csd_resource_definitions(
        "\n" * 9
        + " DEFINE FILE(CUSTOMER) GROUP(BANK)\n        DSNAME(CBSA.CICSBSA.CUSTOMER)\n"
        + "        RECORDSIZE(259) KEYLENGTH(16) RECORDFORMAT(V)\n"
    )
    assert ak.csd_resource_values(resources) == {V_OK}
    key = {"programs": {}, "csd_decks": {DECK: {"resources": resources, "resources_validated": False}}}
    rows = [_csd_row(old=[V_OK], db=[V_DB])]
    assert rd.summarize_causes(rd.classify(mini_repo, rows, key))["unexplained"] == 2

    key["csd_decks"][DECK]["resources_validated"] = True
    classified = rd.classify(mini_repo, rows, key)
    assert rd.summarize_causes(classified)["unexplained"] == 0
    assert {d["side"]: d["verdict"]["verdict"] for d in classified} == {"old": "engine defect", "db": "engine defect"}


def test_the_key_reader_applies_dfhcsdup_quoting():
    """A value is quoted only when it BEGINS with an apostrophe, `''` is an escaped
    apostrophe, and a `WORD(` inside a value is not an operand."""
    (row,) = ak.csd_resource_definitions(
        " DEFINE DB2ENTRY(HBANK) GROUP(BANK)\n"
        " DESCRIPTION('Bank''s entry (see PLAN(X))')\n"
        "        ACCOUNTREC(NONE) PLAN(CBSA)\n"
    )
    assert (row["resource_type"], row["name"], row["plan"]) == ("DB2ENTRY", "HBANK", "CBSA")


def test_a_template_placeholder_is_not_a_resource_on_either_side():
    """cics-genapp's shape: `DB2CONN(<DB2SSID>)` is a template, not a name."""
    deck = (
        "Define DB2Conn(<DB2SSID>) Group(GENA) DB2ID(<DB2SSID>)\nDefine DB2Entry(GENALU2) Group(GENA) Plan(GENAONE)\n"
    )
    key = ak.csd_resource_values(ak.csd_resource_definitions(deck))
    engine = ak.csd_resource_values(extract_boundary("csd", deck)["csd_resources"])
    assert key == engine == {"DB2ENTRY(GENALU2)@2 group=GENA plan=GENAONE"}


@pytest.mark.parametrize(
    "rel",
    [
        "cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd",
        "aws-mainframe-modernization-carddemo/app/csd/CARDDEMO.CSD",
        "aws-mainframe-modernization-carddemo/app/app-transaction-type-db2/csd/CRDDEMOD.csd",
    ],
)
def test_the_two_readers_agree_on_every_committed_deck(rel):
    """Two independent parses of the real decks land on the same definitions."""
    text = (EXCERPTS / rel).read_text(encoding="utf-8")
    key = ak.csd_resource_values(ak.csd_resource_definitions(text))
    engine = ak.csd_resource_values(extract_boundary("csd", text)["csd_resources"])
    assert key and key == engine


def test_draft_csd_reads_decks_and_dfhcsdup_jobs_only(tmp_path):
    (tmp_path / "csd").mkdir()
    (tmp_path / "jcl").mkdir()
    (tmp_path / "csd" / "APP.CSD").write_text(" DEFINE MAPSET(M1) GROUP(APP)\n")
    (tmp_path / "jcl" / "DEFS.jcl").write_text(
        "//J JOB\n//S EXEC PGM=DFHCSDUP\n//SYSIN DD *\n  DEFINE FILE(F1) GROUP(APP) DSNAME(A.B)\n/*\n"
    )
    (tmp_path / "jcl" / "RUN.jcl").write_text(
        "//J JOB\n//S EXEC PGM=X\n//SYSIN DD *\n  DEFINE FILE(F2) GROUP(APP)\n/*\n"
    )
    drafted = ak.draft_csd(tmp_path)
    assert sorted(drafted) == ["csd/APP.CSD", "jcl/DEFS.jcl"]  # RUN.jcl does not run DFHCSDUP
    (row,) = drafted["jcl/DEFS.jcl"]["resources"]
    assert (row["resource_type"], row["name"], row["dsname"]) == ("FILE", "F1", "A.B")
    assert drafted["csd/APP.CSD"]["resources_validated"] is False


@pytest.mark.parametrize("key_path", sorted(KEY_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_csd_key_entries_are_drafts_until_signed_off(key_path):
    """A drafted field never adjudicates, so a sign-off is an explicit, reviewed edit."""
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("csd_decks", {}).items():
        assert entry["resources"], rel
        if not entry.get("resources_validated"):
            assert entry["verification"]["status"] == "draft", rel
