"""#3212: the generated clean room and Spring Boot tree match the committed snapshot.

A failure here means cobol-refractor or cobol-to-java output changed. If the
change is intended, read the diff, bless it with

    python tests/tools/refraction_snapshot.py update

and say in the PR description what moved and why.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mainframe_corpus as mc  # noqa: E402
import refraction_snapshot as rs  # noqa: E402

EXCERPTS = sorted(p for p in rs.EXCERPTS.iterdir() if p.is_dir())


def _assert_matches(source: Path, snap_dir: Path, bless: str) -> None:
    diffs = rs.diff(rs.read_snapshot(snap_dir), rs.generate(source))
    shown = "\n".join(diffs[:5])[:6000]
    assert not diffs, (
        f"{len(diffs)} generated file(s) differ from {snap_dir.name}'s snapshot; bless with `{bless}`\n{shown}"
    )


@pytest.mark.parametrize("source", EXCERPTS, ids=lambda p: p.name)
def test_excerpt_snapshot(source):
    _assert_matches(source, rs.SNAPSHOTS / "excerpts" / source.name, "refraction_snapshot.py update")


@pytest.mark.parametrize("corpus", mc.load_manifest(), ids=lambda c: c["name"])
def test_full_corpus_snapshot(corpus):
    """Local only: skipped unless the corpus is fetched at its pin."""
    clone = mc.clone_path(corpus)
    if not (clone / ".git").exists():
        pytest.skip(f"{corpus['name']} not fetched (mainframe_corpus.py fetch)")
    _assert_matches(
        mc.require_clone(corpus),
        rs.SNAPSHOTS / "full" / corpus["name"],
        f"refraction_snapshot.py update --corpus {corpus['name']}",
    )


def test_every_excerpt_has_a_snapshot():
    assert EXCERPTS
    for source in EXCERPTS:
        assert rs.read_snapshot(rs.SNAPSHOTS / "excerpts" / source.name), source.name


def test_same_name_programs_keep_separate_outputs():
    """#3218: COBOL/SAM2.cbl and multiroot/sam/SAM2.cbl each keep their own JCL,
    schema and IR in the clean room."""
    snap = rs.read_snapshot(rs.SNAPSHOTS / "excerpts" / "zopeneditor-sample")
    for key in ("COBOL__SAM2", "multiroot__sam__SAM2"):
        assert f"clean/01_zero_trust_jcls/{key}.jcl" in snap
        assert f"clean/04_ir_state_dumps/{key}_ir.json" in snap


def test_normalisation_hides_the_scratch_dir_and_timestamp(tmp_path):
    variants = rs._work_variants(tmp_path)
    windows = str(tmp_path).replace("/", "\\") + "\\repo\\COBOL\\A.cbl"
    text = f"at {tmp_path}/repo_gitgalaxy_clean_20260919_101112 and {windows} done"
    out = rs._normalise_str(text, variants + [str(tmp_path).replace("/", "\\")])
    assert out == "at <WORK>/repo_gitgalaxy_clean_<TS> and <WORK>/repo/COBOL/A.cbl done"


def test_diff_reports_missing_unexpected_and_changed():
    diffs = rs.diff({"a": "1\n", "b": "x\n"}, {"b": "y\n", "c": "z\n"})
    assert diffs[0] == "missing (in the snapshot, not generated): a"
    assert "-x" in diffs[1] and "+y" in diffs[1]
    assert diffs[2] == "unexpected (generated, not in the snapshot): c"
