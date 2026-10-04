# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""SARIF / SBOM / graph sqlite / GPU / LLM-brief golden snapshots (#4109)."""

import copy
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden_diff  # noqa: E402
import golden_outputs_snapshot as gos  # noqa: E402

SARIF = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "GitGalaxy Scanner", "version": "v1"}},
            "invocations": [{"executionSuccessful": True}],
            "results": [
                {"ruleId": "R1", "level": "warning", "message": {"text": "a"}, "locations": [{"uri": "x.py"}]},
                {"ruleId": "R2", "level": "error", "message": {"text": "b"}, "locations": [{"uri": "y.py"}]},
            ],
        }
    ],
}
SBOM = {
    "bomFormat": "CycloneDX",
    "serialNumber": "urn:uuid:1",
    "metadata": {"timestamp": "t1", "tools": [{"name": "t", "version": "v"}]},
    "components": [{"name": "b", "version": "1"}, {"name": "a", "version": "2"}],
}
GPU = {
    "meta": {
        "zero_dependency_mode": False,
        "session": {
            "engine": "e",
            "timestamp": "t1",
            "duration_seconds": 1.0,
            "target_directory": "/m",
            "git_audit": {"c": 1},
        },
        "schemas": {
            "lookups": {
                "languages": ["py", "c"],
                "authors": ["u"],
                "proofs": ["p"],
                "purposes": ["q"],
                "constellations": ["g"],
                "archetypes": ["A", "B"],
                "imports": ["os", "re"],
                "exts": [".x"],
                "reasons": ["big"],
            }
        },
    },
    "global_summary": {"summary": {"total_files": 2, "ratio": 0.12345678}},
    "galaxy": {
        "paths": ["a.py", "b.c"],
        "names": ["a.py", "b.c"],
        "lang_ids": [0, 1],
        "tel_aid": [0, 0],
        "tel_pid": [0, 0],
        "tel_purp": [0, 0],
        "tel_lt": [1.5, 2],
        "c_ids": [0, 0],
        "a_ids": [[0], [1]],
        "imports": [[0], [1]],
        "pos_x": [5, 6],
        "pos_y": [7, 8],
        "pos_z": [9, 10],
        "risks_flat": [1, 2, 3, 4],
        "hits_flat": [5, 6, 7, 8],
        "edges": [[1], []],
        "outbound_edges": [[], [0]],
        "locs": [10, 20],
        "satellite_data_flat": [1, 2, 3, 4],
        "satellite_offsets": [0, 1, 2],
    },
    "singularity": {"paths": ["z.bin"], "exts": [0], "reasons": [0], "sizes": [9], "confidences": [900]},
    "story": {},
}
LLM = """# BRIEF
| **Engine** | `v` |
| **Git Remote** | `git@x` |
| **Function archetypes** | **VALIDATED**, 98% |
## 1. SUMMARY
files: 2
"""


def _write_scan(d: Path, sarif=SARIF, sbom=SBOM, gpu=GPU, llm=LLM, loc=5, ts="t1") -> Path:
    d.mkdir(exist_ok=True)
    (d / "x_galaxy_audit.json").write_text("{}")
    (d / "x_galaxy_sarif.json").write_text(json.dumps(sarif))
    s = copy.deepcopy(sbom)
    s["metadata"]["timestamp"] = ts
    (d / "x_galaxy_sbom.json").write_text(json.dumps(s))
    g = copy.deepcopy(gpu)
    g["meta"]["session"]["timestamp"] = ts
    (d / "x_galaxy_gpu.json").write_text(json.dumps(g))
    (d / "x_galaxy_llm.md").write_text(llm)
    gp = d / "x_galaxy_graph.sqlite"
    gp.unlink(missing_ok=True)
    c = sqlite3.connect(gp)
    c.executescript(
        f"""
        CREATE TABLE meta (key TEXT, value TEXT);
        INSERT INTO meta VALUES ('engine','e'), ('timestamp','{ts}'), ('commit','{ts}'), ('branch','{ts}');
        CREATE TABLE artifacts (id INTEGER PRIMARY KEY, path TEXT, total_loc INTEGER, file_impact REAL);
        INSERT INTO artifacts VALUES (1,'a.py',{loc},1.0), (2,'b.c',7,2.0);
        CREATE TABLE directory_groups (name TEXT PRIMARY KEY, file_count INTEGER);
        INSERT INTO directory_groups VALUES ('g',2);
        CREATE TABLE functions (id INTEGER PRIMARY KEY, artifact_id INT, name TEXT, type_id TEXT, loc INT,
            impact REAL, docstring TEXT, calls_out_to TEXT);
        INSERT INTO functions VALUES (1,1,'f','F',3,1.0,'','[]');
        CREATE TABLE dna_hits (artifact_id INT, signal_type TEXT, hit_count INT);
        INSERT INTO dna_hits VALUES (1,'io',2);
        CREATE TABLE outbound_dependencies (artifact_id INT, imported_path TEXT);
        CREATE TABLE inbound_dependencies (artifact_id INT, imported_by_path TEXT);
        """
    )
    c.commit()
    c.close()
    return d / "x_galaxy_audit.json"


def _snap(tmp: Path, name: str, **kw):
    return gos.snapshot(_write_scan(tmp / name if (tmp / name).exists() else _mk(tmp, name), **kw))


def _mk(tmp: Path, name: str) -> Path:
    (tmp / name).mkdir()
    return tmp / name


def test_every_output_is_snapshotted(tmp_path):
    snap = _snap(tmp_path, "a")
    assert set(snap) == {gos.SARIF_KEY, gos.SBOM_KEY, gos.GRAPH_KEY, gos.GPU_KEY, gos.LLM_KEY}


def test_masked_and_reordered_fields_do_not_diff(tmp_path):
    base = _snap(tmp_path, "a")
    sarif = copy.deepcopy(SARIF)
    sarif["runs"][0]["results"].reverse()
    sbom = copy.deepcopy(SBOM)
    sbom["serialNumber"] = "urn:uuid:2"
    sbom["components"].reverse()
    llm = LLM.replace("git@x", "git@y").replace("98%", "50%")
    other = _snap(tmp_path, "b", sarif=sarif, sbom=sbom, llm=llm, ts="t2")
    assert golden_diff.deep_compare(base, other) == []


def test_gpu_coordinates_and_scan_order_do_not_diff(tmp_path):
    gpu = copy.deepcopy(GPU)
    g = gpu["galaxy"]
    g["pos_x"] = [99, 98]
    # same two files, scan order swapped; ids/indices re-derived
    swap = [1, 0]
    for col in ("paths", "names", "lang_ids", "tel_aid", "tel_pid", "tel_purp", "tel_lt", "c_ids", "a_ids", "locs"):
        g[col] = [g[col][i] for i in swap]
    g["risks_flat"] = [3, 4, 1, 2]
    g["hits_flat"] = [7, 8, 5, 6]
    g["imports"] = [[1], [0]]
    g["edges"] = [[], [0]]
    g["outbound_edges"] = [[1], []]
    g["satellite_data_flat"] = [3, 4, 1, 2]
    base, other = _snap(tmp_path, "a"), _snap(tmp_path, "b", gpu=gpu)
    assert golden_diff.deep_compare(base[gos.GPU_KEY], other[gos.GPU_KEY]) == []


def _mutations():
    def sarif(s):
        s["runs"][0]["results"][0]["level"] = "error"

    def sbom(s):
        s["components"][0]["version"] = "9"

    def llm(s):
        return s.replace("files: 2", "files: 3")

    def gpu_loc(s):
        s["galaxy"]["locs"][0] = 11

    def gpu_edge(s):
        s["galaxy"]["edges"] = [[], []]

    def gpu_sing(s):
        s["singularity"]["sizes"] = [10]

    def gpu_summary(s):
        s["global_summary"]["summary"]["total_files"] = 3

    return {
        "sarif": ("sarif", sarif, gos.SARIF_KEY),
        "sbom": ("sbom", sbom, gos.SBOM_KEY),
        "llm": ("llm", llm, gos.LLM_KEY),
        "gpu-loc": ("gpu", gpu_loc, gos.GPU_KEY),
        "gpu-edge": ("gpu", gpu_edge, gos.GPU_KEY),
        "gpu-singularity": ("gpu", gpu_sing, gos.GPU_KEY),
        "gpu-summary": ("gpu", gpu_summary, gos.GPU_KEY),
    }


def test_each_output_catches_a_deliberate_change(tmp_path):
    base = _snap(tmp_path, "base")
    for name, (kw, fn, key) in _mutations().items():
        src = {"sarif": SARIF, "sbom": SBOM, "gpu": GPU, "llm": LLM}[kw]
        mutated = copy.deepcopy(src)
        out = fn(mutated)
        mutated = out if out is not None else mutated
        other = _snap(tmp_path, name, **{kw: mutated})
        assert golden_diff.deep_compare(base, other), f"{name}: mutation not detected"
        assert golden_diff.deep_compare(base[key], other[key]), f"{name}: wrong section"


def test_graph_sqlite_catches_a_deliberate_change(tmp_path):
    base = _snap(tmp_path, "a")
    other = _snap(tmp_path, "b", loc=6)
    diffs = golden_diff.deep_compare(base[gos.GRAPH_KEY], other[gos.GRAPH_KEY])
    assert diffs and any("a.py" in str(d) for d in diffs)


def test_attach_is_noop_for_fixture_directories(tmp_path):
    assert gos.siblings(tmp_path) == {}
    audit = {"x": 1}
    assert gos.attach(audit, tmp_path) == {"x": 1}


def test_load_and_sanitize_attaches_section(tmp_path):
    audit = _write_scan(tmp_path)
    data = golden_diff.load_and_sanitize(str(audit))
    assert gos.SECTION in data
