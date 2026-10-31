"""cics_spec_status: the generated CICS spec status page renders, and its parts -- the translator's keying of a
command, census counts (counts only), the stub probe, the spec PR table -- do what the page says."""

import json
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det translator (OPTIONS, parse_exec) is read live

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_spec_status as st


def fixed(*code: str) -> str:
    return "\n".join(f"{i * 100:06d} {c}" for i, c in enumerate(code, 1)) + "\n"


def test_the_page_renders():
    """#4789 / #5057: the page is not committed; generated-docs.yml renders it from main and publishes it."""
    text = st.render()
    assert text.startswith("# CICS command spec: status\n") and "## Full and engine-only entries" in text
    assert st.render() == text  # deterministic: the published copy is a fresh render of main


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ("GET CONTAINER('A') INTO(X)", "GET CONTAINER"),
        ("SEND MAP('M') MAPSET('S') ERASE", "SEND MAP"),
        ("HANDLE CONDITION NOTFND(P-1)", "HANDLE CONDITION"),
        ("WEB OPEN HOST(H) SESSTOKEN(T)", "WEB OPEN"),  # a name-only entry
        ("GETMAIN SET(P) LENGTH(10)", "GETMAIN"),
        ("FOO BAR(1)", "(unlisted) FOO"),
    ],
)
def test_spec_key_is_the_translators(body, key):
    assert st.spec_key(body) == key


def test_census_use_counts_programs_split_burned(tmp_path):
    prog = fixed("PROCEDURE DIVISION.", "    EXEC CICS WEB OPEN HOST(H) END-EXEC.",
                 "    EXEC CICS WEB OPEN HOST(H) END-EXEC.", "    EXEC CICS RETURN END-EXEC.")  # fmt: skip
    for corpus in ("zecs", "some-census-repo"):
        d = tmp_path / corpus / "src"
        d.mkdir(parents=True)
        (d / "P1.cbl").write_text(prog)
    use = st.census_use([tmp_path])
    assert use["WEB OPEN"] == {"programs": 2, "burned": 1, "non_burned": 1}  # two commands in one program: one
    assert use["RETURN"]["programs"] == 2


def test_the_stub_probe_tells_taken_from_refused_whole():
    cmds = st.spec()
    assert st.stub_takes("READ", cmds["READ"])  # needs FILE: found by the per-option probe
    assert st.stub_takes("RETURN", cmds["RETURN"])
    assert not st.stub_takes("ACQUIRE", cmds["ACQUIRE"])  # engine-only


def test_spec_prs_reads_section_7():
    prs = st.spec_prs()
    assert [p["pr"] for p in prs][:3] == ["1", "2", "3"]
    assert {"4", "5", "6", "7", "8a", "8b"} <= {p["pr"] for p in prs}
    assert set(st.SPEC_PRS_DONE) <= {p["pr"] for p in prs}


def test_registers_have_rows_in_oracle_assumptions():
    known = st.register_rows()
    missing = {(k, r) for k, c in st.spec().items() for r in st.registers(c) if r not in known}
    assert not missing


def test_check_only_renders_and_writes_nothing(tmp_path, monkeypatch):
    """#5057: there is no committed page to be stale; `render --check` renders, `render` writes the git-ignored page."""
    page = tmp_path / "page.md"
    monkeypatch.setattr(st, "PAGE", page)
    monkeypatch.setattr(st, "REPO", tmp_path)
    assert st.main(["render", "--check"]) == 0
    assert not page.exists()
    assert st.main(["render"]) == 0
    assert page.read_text(encoding="utf-8") == st.render()


def test_check_fails_when_the_page_does_not_render(monkeypatch):
    def broken():
        raise ValueError("entries in a family _layout.json does not place: ['X999']")

    monkeypatch.setattr(st, "render", broken)
    with pytest.raises(ValueError):
        st.main(["render", "--check"])


def test_register_rows_are_the_summarised_x_entries():
    import register

    rows = st.register_rows()
    entries = {m["id"]: m for m, _ in register.load_entries()}
    assert rows and all(entries[r]["summary"] and r.startswith("X") for r in rows)
    table = set(re.findall(r"^\| (X\d+) \|", register.render(), re.M))
    assert rows == table


def test_the_data_file_holds_counts_and_case_ids_only():
    data = json.loads(st.DATA.read_text(encoding="utf-8"))
    for key, row in data["census"].items():
        assert set(row) == {"programs", "burned", "non_burned"}, key
        assert all(isinstance(v, int) for v in row.values())
    for key, cases in data["crucible"].items():
        assert all(isinstance(c, str) and "/" not in c for c in cases), key
