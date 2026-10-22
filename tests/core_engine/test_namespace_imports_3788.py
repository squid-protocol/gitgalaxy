"""
#3788: `import * as processors from "./json-schema-processors.js"; processors.dateProcessor()`.
The call resolver matched a qualifier only against the stems and directories of the files a
caller imports, so an alias that is not the file's name found nothing. A JS/TS file now records
its namespace aliases (`namespace_imports`), the import pass resolves each to a file, and the
resolver's `import` step reaches that module (and a barrel's re-exports) through the alias.
"""

import sqlite3

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.galaxyscope import extract_namespace_imports
from gitgalaxy.recorders.record_keeper import RecordKeeper

_MOD = "src/json-schema-processors.ts"
_USER = "src/to-json.ts"


@pytest.mark.parametrize(
    "code, expected",
    [
        ('import * as processors from "./json-schema-processors.js";\n', {"processors": "./json-schema-processors.js"}),
        ("import type * as t from '../types';\n", {"t": "../types"}),
        ('import z = require("zod");\n', {"z": "zod"}),
        ('const util = require("./util");\nlet {a} = require("./x");\n', {"util": "./util"}),
        ('import { a as b } from "./x";\nimport def from "./y";\n', {}),
        ('import * as a from "./one";\nimport * as a from "./two";\n', {}),  # ambiguous alias
        ('import * as a from "./one";\nimport * as a from "./one";\n', {"a": "./one"}),
    ],
)
def test_namespace_alias_capture(code, expected):
    assert extract_namespace_imports(code, "typescript") == expected


def test_only_js_ts_capture_aliases():
    assert extract_namespace_imports('import * as a from "./x"\n', "python") == {}


def _universe(with_alias=True):
    return [
        {
            "path": _USER,
            "lang_id": "typescript",
            "raw_imports": ["./json-schema-processors.js"],
            "namespace_imports": {"processors": "./json-schema-processors.js"} if with_alias else {},
            "classes": [],
            "functions": [
                {
                    "name": "toJSON",
                    "start_line": 1,
                    "calls_out_to": ["dateProcessor"],
                    "calls_out_qualifiers": {"dateProcessor": ["processors"]},
                }
            ],
        },
        {
            "path": _MOD,
            "lang_id": "typescript",
            "raw_imports": [],
            "classes": [],
            "functions": [{"name": "dateProcessor", "start_line": 5, "calls_out_to": [], "def_shape": "binding"}],
        },
        {
            "path": "other/dates.ts",
            "lang_id": "typescript",
            "raw_imports": [],
            "classes": [],
            "functions": [{"name": "dateProcessor", "start_line": 2, "calls_out_to": [], "def_shape": "binding"}],
        },
    ]


def _resolve(files):
    sensor = NetworkRiskSensor()
    edges = [{"src": s, "dst": d, "edge_kind": "import"} for s, d in sensor.resolve_import_edges(files)]
    return resolve_calls(files, edges, sensor.namespace_aliases, sensor.star_exports)[0], sensor


def test_alias_that_is_not_the_file_name_resolves_through_the_import_step():
    sites, sensor = _resolve(_universe())
    assert sensor.namespace_aliases == {_USER: {"processors": _MOD}}
    (row,) = [s for s in sites if s["callee"] == "dateProcessor"]
    assert (row["step"], row["dst_path"]) == ("import", _MOD)


def test_without_the_alias_the_call_stays_unresolved():
    (row,) = [s for s in _resolve(_universe(with_alias=False))[0] if s["callee"] == "dateProcessor"]
    assert row["step"] != "import"
    assert row["dst_path"] != _MOD or row["resolution"] != "scoped"


def test_alias_reaches_what_a_barrel_re_exports():
    files = _universe()
    files[0]["raw_imports"] = ["./barrel"]
    files[0]["namespace_imports"] = {"processors": "./barrel"}
    files.append(
        {
            "path": "src/barrel/index.ts",
            "lang_id": "typescript",
            "raw_imports": ["../json-schema-processors"],
            "functions": [],
        }
    )
    sites, _ = _resolve(files)
    (row,) = [s for s in sites if s["callee"] == "dateProcessor"]
    assert (row["step"], row["dst_path"]) == ("import", _MOD)


def test_alias_does_not_reach_a_file_it_is_not_bound_to():
    files = _universe()
    files[0]["namespace_imports"] = {"processors": "./json-schema-processors.js"}
    files[1]["functions"] = []  # the aliased module no longer defines it
    sites, _ = _resolve(files)
    (row,) = [s for s in sites if s["callee"] == "dateProcessor"]
    assert row["dst_path"] != "other/dates.ts" or row["step"] != "import"


def test_namespace_imports_persist_and_rehydrate(tmp_path):
    db = tmp_path / "n.db"
    session = {"target": "NsRepo", "git_audit": {"commit_hash": "n3788", "latest_commit_date": "2026-10-03T00:00:00Z"}}
    RecordKeeper().record_mission(_universe(), [], {}, session, str(db))
    conn = sqlite3.connect(db)
    try:
        rows = dict(conn.execute("SELECT file_path, namespace_imports FROM file_data").fetchall())
    finally:
        conn.close()
    assert rows[_USER] == '{"processors": "./json-schema-processors.js"}'
    assert rows[_MOD] is None
    cache = StateRehydrator(str(db)).load_state("NsRepo")["ram_cache"]
    assert cache[_USER]["namespace_imports"] == {"processors": "./json-schema-processors.js"}
    assert cache[_MOD]["namespace_imports"] == {}


# ----------------------------------------------------------------------------- #4253: `export * from` chains


def _ts(path, code_imports=(), stars=(), aliases=None, functions=()):
    ns = dict(aliases or {})
    ns.update({f"export * from {s}": s for s in stars})
    return {
        "path": path,
        "lang_id": "typescript",
        "raw_imports": list(code_imports) + list(stars),
        "namespace_imports": ns,
        "classes": [],
        "functions": list(functions),
    }


def _zod(extra=()):
    """zod's shape: v4/index -> classic/index -> external -> schemas, all `export * from`."""
    caller_fn = {
        "name": "run",
        "start_line": 1,
        "calls_out_to": ["makeSchema"],
        "calls_out_qualifiers": {"makeSchema": ["zz"]},
    }
    defn = {"name": "makeSchema", "start_line": 3, "calls_out_to": [], "def_shape": "binding"}
    return [
        _ts("app.ts", ["./v4/index"], aliases={"zz": "./v4/index"}, functions=[caller_fn]),
        _ts("v4/index.ts", stars=["./classic/index"]),
        _ts("classic/index.ts", stars=["./external"]),
        _ts("classic/external.ts", stars=["./schemas"]),
        _ts("classic/schemas.ts", functions=[defn]),
        _ts("decoy/schemas.ts", functions=[dict(defn, start_line=9)]),
        *extra,
    ]


def test_star_export_specifiers_are_captured():
    code = 'export * from "./a";\nexport type * from \'./b\';\nexport * as ns from "./c";\nexport { x } from "./d";\n'
    assert extract_namespace_imports(code, "typescript") == {"export * from ./a": "./a", "export * from ./b": "./b"}


def test_ns_call_resolves_through_a_star_export_chain():
    sites, sensor = _resolve(_zod())
    assert sensor.star_exports["v4/index.ts"] == {"classic/index.ts"}
    assert sensor.namespace_aliases == {"app.ts": {"zz": "v4/index.ts"}}
    (row,) = [s for s in sites if s["callee"] == "makeSchema"]
    assert (row["step"], row["dst_path"]) == ("import", "classic/schemas.ts")


def test_star_export_cycle_terminates():
    files = _zod([_ts("classic/loop.ts", stars=["./external"])])
    files[3]["namespace_imports"]["export * from ./loop"] = "./loop"  # external -> loop -> external
    files[3]["raw_imports"].append("./loop")
    (row,) = [s for s in _resolve(files)[0] if s["callee"] == "makeSchema"]
    assert row["dst_path"] == "classic/schemas.ts"


def test_star_export_chain_is_bounded():
    from gitgalaxy.core import call_resolver

    depth = call_resolver._STAR_HOPS + 3
    stars = {f"m{i}.ts": {f"m{i + 1}.ts"} for i in range(depth)}
    reached = call_resolver._star_closure({"m0.ts"}, stars)
    assert reached == {f"m{i}.ts" for i in range(1, call_resolver._STAR_HOPS + 1)}
