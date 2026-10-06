"""
#4544: Rust `use` paths resolve by the module tree and the Cargo manifests.

The name search read `use crate::render::bsp::Node` as a file called `Node`, so a Rust
workspace's import graph was nearly empty (room4doom: 2,603 `use` lines, 336 edges). The
fixture below is a small Cargo workspace written to disk; its imports are extracted by the
real Rust `_dependency_capture` rule and resolved by the real sensor, and the edge set is
pinned exactly.
"""

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.core.rust_modules import (
    Manifest,
    inline_module_spans,
    parse_cargo_manifest,
    rescope_to_file,
)
from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_RUST = LANGUAGE_DEFINITIONS["rust"]

WORKSPACE = {
    "Cargo.toml": (
        "[workspace]\n"
        'members = [\n  "core",  # the engine\n  "app",\n  "util-lib",\n  "legacy",\n]\n'
        "[workspace.dependencies]\n"
        'core-kit = { path = "core" }\n'
    ),
    # --- core-kit: modules, re-exports, #[path], inline test modules
    "core/Cargo.toml": '[package]\nname = "core-kit"\nedition = "2021"\n',
    "core/src/lib.rs": (
        "pub mod geom;\n"
        "mod render;\n"
        "pub use render::Renderer;\n"
        "pub use geom::shapes::*;\n"
        "use std::io;\n"  # std, never core/src/io.rs
    ),
    "core/src/io.rs": "pub fn read() {}\n",
    "core/src/geom/mod.rs": "pub mod shapes;\nuse super::render::Canvas;\npub struct Point;\n",
    "core/src/geom/shapes.rs": (
        "pub mod detail;\n"
        "use crate::geom::Point;\n"
        "use self::detail::Inner;\n"
        "use std::fmt;\n"
        "pub struct Circle;\n"
        "#[cfg(test)]\n"
        "mod tests {\n"
        "    use super::*;\n"  # this file, not geom/mod.rs
        "    use super::super::Point;\n"  # geom (already an edge)
        "}\n"
    ),
    "core/src/geom/shapes/detail.rs": "pub struct Inner;\n",
    "core/src/render.rs": '#[path = "backends/soft.rs"]\nmod soft;\npub struct Renderer;\npub struct Canvas;\n',
    "core/src/backends/soft.rs": "pub fn draw() {}\n",
    # --- app: workspace dependency, renamed path dependency, extern crate, grouped use
    "app/Cargo.toml": (
        '[package]\nname = "app"\nedition = "2021"\n\n'
        "[dependencies]\n"
        "core-kit.workspace = true\n"
        'helpers = { path = "../util-lib", package = "util-lib" }\n'
    ),
    "app/src/main.rs": (
        "extern crate helpers;\n"
        "use core_kit::{Renderer, Circle, geom::{self, shapes::detail}};\n"
        "mod cli;\n"
        "fn main() {}\n"
    ),
    "app/src/cli.rs": "use helpers::Tool;\nuse serde::Deserialize;\n",
    # --- util-lib: hyphenated package, its own integration test
    "util-lib/Cargo.toml": '[package]\nname = "util-lib"\nedition = "2018"\n',
    "util-lib/src/lib.rs": "mod tool;\npub use tool::Tool;\n",
    "util-lib/src/tool.rs": "pub struct Tool;\n",
    "util-lib/tests/it.rs": "use util_lib::Tool;\n",
    # --- legacy: Rust 2015 (no edition) paths are crate-relative
    "legacy/Cargo.toml": '[package]\nname = "legacy"\nversion = "0.1.0"\n',
    "legacy/src/lib.rs": "mod a;\nmod b;\n",
    "legacy/src/a.rs": "use b::Thing;\n",
    "legacy/src/b.rs": "pub struct Thing;\n",
}

EXPECTED = {
    # mod declarations, including #[path]
    ("core/src/lib.rs", "core/src/geom/mod.rs"),
    ("core/src/lib.rs", "core/src/render.rs"),
    ("core/src/geom/mod.rs", "core/src/geom/shapes.rs"),
    ("core/src/geom/shapes.rs", "core/src/geom/shapes/detail.rs"),
    ("core/src/render.rs", "core/src/backends/soft.rs"),
    ("app/src/main.rs", "app/src/cli.rs"),
    ("util-lib/src/lib.rs", "util-lib/src/tool.rs"),
    ("legacy/src/lib.rs", "legacy/src/a.rs"),
    ("legacy/src/lib.rs", "legacy/src/b.rs"),
    # lib.rs's own `pub use` lines (re-exports are imports too)
    ("core/src/lib.rs", "core/src/geom/shapes.rs"),
    # crate:: / self:: / super::
    ("core/src/geom/mod.rs", "core/src/render.rs"),
    ("core/src/geom/shapes.rs", "core/src/geom/mod.rs"),
    # workspace crate through [workspace.dependencies]; re-exports followed one hop
    ("app/src/main.rs", "core/src/render.rs"),  # Renderer: `pub use render::Renderer`
    ("app/src/main.rs", "core/src/geom/shapes.rs"),  # Circle: `pub use geom::shapes::*`
    ("app/src/main.rs", "core/src/geom/mod.rs"),  # geom::{self}
    ("app/src/main.rs", "core/src/geom/shapes/detail.rs"),
    # renamed path dependency, via extern crate and via use
    ("app/src/main.rs", "util-lib/src/lib.rs"),
    ("app/src/cli.rs", "util-lib/src/tool.rs"),
    # an integration test uses its package's library by name (hyphen -> underscore)
    ("util-lib/tests/it.rs", "util-lib/src/tool.rs"),
    # Rust 2015: `use b::Thing` is crate-relative
    ("legacy/src/a.rs", "legacy/src/b.rs"),
}


def _write(tmp_path, files):
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)


def _parsed(files):
    rule = _RUST["rules"]["_dependency_capture"]
    return [
        {
            "path": rel,
            "lang_id": "rust",
            "raw_imports": sorted(extract_raw_imports(rule, text, _RUST)),
            "functions": [],
            "classes": [],
        }
        for rel, text in files.items()
        if rel.endswith(".rs")
    ]


def _edges(tmp_path, files, root=True):
    _write(tmp_path, files)
    sensor = NetworkRiskSensor()
    sensor.root = str(tmp_path) if root else None
    return set(sensor.resolve_import_edges(_parsed(files)))


def test_a_cargo_workspace_resolves_to_exactly_these_edges(tmp_path):
    assert _edges(tmp_path, WORKSPACE) == EXPECTED


def test_without_manifests_only_the_crate_relative_forms_resolve(tmp_path):
    # No scan root: no Cargo.toml to name other crates, so only crate::/self::/super::
    # and mod declarations draw edges -- and std never does.
    edges = _edges(tmp_path, WORKSPACE, root=False)
    assert ("core/src/geom/shapes.rs", "core/src/geom/mod.rs") in edges
    assert not any(dst == "core/src/io.rs" for _, dst in edges)
    assert not any(src.startswith("app/") and dst.startswith(("core/", "util-lib/")) for src, dst in edges)


def test_an_external_crate_or_std_path_draws_no_edge(tmp_path):
    files = {
        "Cargo.toml": '[package]\nname = "x"\nedition = "2021"\n',
        "src/lib.rs": "mod fmt;\nuse std::fmt;\nuse serde::de::Visitor;\nuse fmt::Pretty;\n",
        "src/fmt.rs": "pub struct Pretty;\n",
        "src/de.rs": "",
    }
    # `use fmt::Pretty` (2018 uniform path) is the child module; `std::fmt` is std.
    assert _edges(tmp_path, files) == {("src/lib.rs", "src/fmt.rs")}


def test_extraction_records_path_modules_extern_crates_and_inline_scopes():
    src = (
        "extern crate alloc;\n"
        "extern crate foo_bar as fb;\n"
        '#[path = "plat/unix.rs"]\n#[cfg(unix)]\nmod sys;\n'
        "fn f() { let s = \"}\"; let c = '}'; }\n"
        "mod tests {\n    use super::*;\n    use super::super::q;\n"
        "    mod inner { use super::h; use self::k::Z; }\n}\n"
        "use super::after;\n"
    )
    tokens = extract_raw_imports(_RUST["rules"]["_dependency_capture"], src, _RUST)
    assert tokens == {
        "alloc",
        "foo_bar",
        "./plat/unix.rs",
        "self::*",
        "super::q",
        "self::tests::h",
        "self::tests::inner::k::Z",
        "super::after",
    }


def test_rescope_and_inline_spans():
    assert rescope_to_file("super::super::x", ["tests"]) == "super::x"
    assert rescope_to_file("super::x", ["a", "b"]) == "self::a::x"
    assert rescope_to_file("crate::x", ["tests"]) == "crate::x"
    assert [name for *_, name in inline_module_spans('mod a { mod b { "}" } }')] == ["a", "b"]


def test_the_manifest_reader():
    text = (
        "[package]\n"
        'name = "render-backend"  # a comment\n'
        "edition.workspace = true\n"
        'build = "../build.rs"\n'
        "[lib]\n"
        'path = "lib/root.rs"\n'
        "[dependencies]\n"
        'sdl2 = { version = "0.38", features = [\n  "a",\n  "b",\n] }\n'
        'common = { package = "render-common", path = "../common" }\n'
        "math.workspace = true\n"
        "[dependencies.wad]\n"
        'path = "../../wad"\n'
    )
    m = Manifest("render/backend", parse_cargo_manifest(text))
    assert (m.lib_name, m.lib_path, m.build, m.edition_2015) == ("render_backend", "lib/root.rs", "../build.rs", False)
    assert m.deps == {"common": ("../common", False), "math": (None, True), "wad": ("../../wad", False)}
    assert m.rel(m.deps["wad"][0]) == "wad"
