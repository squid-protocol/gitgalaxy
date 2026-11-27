"""SOP-002-v1 gap-cell decoy suite for TypeScript (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers the 10 typescript code-stream families that had a rule but no decoy row:
cryptography, dl_frameworks, exfiltration_camouflage, explicit_casts, hardware_bridge,
llm_api, llm_orchestrator, llm_vector_store, rce_funnel, telemetry.
This is not a full-language graduation; the other typescript families keep their SOP-001-v1 rows.

Comment forms (TypeScript follows ECMA-262 12.4): `//` line comments, `/* */` block comments
(single- and multi-line, and `/** */` TSDoc), which do NOT nest, and the first-line hashbang `#!`.
TypeScript does not accept the Annex B HTML-like `<!--` / `-->` comments, so they are not tested here.
TSX `{/* */}` is the block form inside a JSX expression container.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = "typescript"
_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor(_LANG, LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_ISSUE = "https://github.com/squid-protocol/gitgalaxy/issues/"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, _LANG)
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# Req C / G1: one authentic positive control per gap cell (single line, so every comment form wraps it whole).
TS_FAMILIES: dict[str, str] = {
    "cryptography": 'import { createHash } from "node:crypto";',
    "dl_frameworks": 'import * as tf from "@tensorflow/tfjs";',
    "exfiltration_camouflage": 'fetch("https://collector.example.com/telemetry", { method: "POST" });',
    "explicit_casts": 'const el = document.getElementById("app") as HTMLElement;',
    "hardware_bridge": 'import { SerialPort } from "serialport";',
    "llm_api": 'import OpenAI from "openai";',
    "llm_orchestrator": 'import { ChatOpenAI } from "@langchain/openai";',
    "llm_vector_store": 'import { ChromaClient } from "chromadb";',
    "rce_funnel": 'child_process.spawn("python", ["train.py"]);',
    "telemetry": 'logger.info("request served");',
}

# Every package name in each import-anchored rule's alternation (Req B branches); scoped arms use a real package.
TS_IMPORT_BRANCHES: dict[str, tuple[str, ...]] = {
    "cryptography": (
        "crypto",
        "node:crypto",
        "tls",
        "node:tls",
        "crypto-js",
        "bcrypt",
        "ssl",
        "jsonwebtoken",
        "argon2",
        "x509",
        "@peculiar/x509",
    ),
    "dl_frameworks": (
        "tensorflow",
        "torch",
        "keras",
        "transformers",
        "@tensorflow/tfjs",
        "@tensorflow-models/coco-ssd",
        "@huggingface/transformers",
        "@xenova/transformers",
    ),
    "hardware_bridge": (
        "serialport",
        "@serialport/parser-readline",
        "usb",
        "bluetooth",
        "socket.io",
        "socket.io-client",
        "@socket.io/redis-adapter",
        "websocket",
        "printer",
    ),
    "llm_api": ("openai", "anthropic", "@openai/agents", "@anthropic-ai/sdk", "@azure/openai"),
    "llm_orchestrator": (
        "langchain",
        "llamaindex",
        "ai",
        "@langchain/core",
        "@llamaindex/core",
        "@ai-sdk/openai",
        "@mastra/core",
    ),
    "llm_vector_store": ("chromadb", "@pinecone-database/pinecone"),
}

_IMPORT_BRANCH_CASES = [(fam, pkg) for fam, pkgs in sorted(TS_IMPORT_BRANCHES.items()) for pkg in pkgs]


def _glued(pkg: str) -> str:
    """The package name with a letter glued onto the segment the rule names (`openaix`, `cryptox-js`,
    `@tensorflowx/tfjs`; for the any-scope arms `@<scope>/x509` and `@<scope>/openai`, `@peculiar/x509x`)."""
    if pkg in ("@peculiar/x509", "@azure/openai"):
        return pkg + "x"
    if pkg.startswith("@"):
        scope, rest = pkg.split("/", 1)
        return f"{scope}x/{rest}"
    return re.sub(r"^([a-z]+)", r"\1x", pkg)


def test_typescript_gap_families_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    code_fams = (defined[_LANG] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(TS_FAMILIES) <= code_fams


def test_typescript_baseline_has_sop002_row_per_gap_family():
    decoys = json.loads(_BASELINE.read_text(encoding="utf-8"))["decoys"][_LANG]
    for fam in TS_FAMILIES:
        row = decoys.get(fam)
        assert row is not None, f"no baseline decoy row for typescript.{fam}"
        assert row["protocol"] == "SOP-002-v1"
        assert row["corpus"] == "decoy-spec"
        assert row["string_counts"] is True


@pytest.mark.parametrize(("family", "snippet"), sorted(TS_FAMILIES.items()))
def test_typescript_positive_control_and_comment_forms(family: str, snippet: str):
    # G1: positive control
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for typescript.{family}: {snippet!r}"
    # G2 (Req A): `//` line comment, consecutive lines, indented
    assert _hits(family, f"// {snippet}\n") == 0
    assert _hits(family, f"//{snippet}\n// {snippet}\n") == 0
    assert _hits(family, f"function f() {{\n  // {snippet}\n}}\n") == 0
    # G3: block comment single-line, multi-line, JSDoc
    assert _hits(family, f"/* {snippet} */\n") == 0
    assert _hits(family, f"/*\n{snippet}\n*/\n") == 0
    assert _hits(family, f"/**\n * {snippet}\n */\n") == 0
    # JSX expression-container comment
    assert _hits(family, f"const v = <div>{{/* {snippet} */}}</div>;\n") == 0
    # G4: inline trailing comments add nothing over their prefix
    assert _hits(family, f"x = 1; // {snippet}\n") <= _hits(family, "x = 1; // SENTINEL_NOOP\n")
    assert _hits(family, f"x = 1; /* {snippet} */\n") <= _hits(family, "x = 1; /* SENTINEL_NOOP */\n")


@pytest.mark.parametrize(("family", "snippet"), sorted(TS_FAMILIES.items()))
def test_typescript_block_comments_do_not_nest(family: str, snippet: str):
    """ECMA-262: a block comment ends at the first `*/`; text after it is code and must count."""
    assert _hits(family, f"/* outer /* inner */ {snippet}\n") >= 1


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9451")
@pytest.mark.parametrize(("family", "snippet"), sorted(TS_FAMILIES.items()))
def test_typescript_hashbang_comment(family: str, snippet: str):
    """The first-line hashbang comment (TypeScript accepts it, as ES2023 does)."""
    assert _hits(family, f"#!/usr/bin/env node {snippet}\nconst a = 1;\n") == 0


@pytest.mark.parametrize(("family", "snippet"), sorted(TS_FAMILIES.items()))
def test_typescript_string_literal_and_string_comment_boundary(family: str, snippet: str):
    # G6: the snippet inside a string literal counts today (strings count by design, #2535).
    assert _hits(family, f"const s = '{snippet.replace(chr(39), chr(34))}';\n") >= 1
    # G6b: URLs, escaped quotes and template literals before a comment do not leak the comment
    for prefix in ('const s = "http://x";', "const s = 'a \\' b';", "const s = `http://x`;", 'const s = "a \\" b";'):
        assert _hits(family, f"{prefix} // {snippet}\n") <= _hits(family, f"{prefix} // SENTINEL_NOOP\n")
    # a comment opener inside a string does not start a comment: the code after it still counts
    assert _hits(family, f'const s = "/*"; {snippet}\n') >= 1
    assert _hits(family, f'const s = "//"; {snippet}\n') >= 1


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9452")
def test_typescript_regex_literal_with_slashes_is_not_a_comment():
    assert _hits("telemetry", 'if (/^https?:\\/\\//.test(u)) logger.info("x");\n') >= 1


@pytest.mark.parametrize(("family", "pkg"), _IMPORT_BRANCH_CASES)
def test_typescript_import_branch_positive_and_boundaries(family: str, pkg: str):
    """Req B over every package arm of the import-anchored rules."""
    assert _hits(family, f'import x from "{pkg}";\n') >= 1
    assert _hits(family, f"const x = require('{pkg}');\n") >= 1
    assert _hits(family, f'const x = await import("{pkg}");\n') >= 1
    assert _hits(family, f'import "{pkg}/sub";\n') >= 1
    # the package name embedded in a longer name, a local file of that name, a look-alike loader call
    assert _hits(family, f'import x from "my-{pkg.lstrip("@")}";\n') == 0
    assert _hits(family, f'import x from "{_glued(pkg)}";\n') == 0
    assert _hits(family, f'import x from "./{pkg.lstrip("@")}";\n') == 0
    assert _hits(family, f'const x = my_require("{pkg}");\n') == 0
    assert _hits(family, f'const x = myrequire("{pkg}");\n') == 0
    assert _hits(family, f'const x = my_import("{pkg}");\n') == 0
    # the bare package name in a string with no import keyword
    assert _hits(family, f'const s = "{pkg}";\n') == 0


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req D: "one hit per import statement, none for a use of the imported name" (signal_contracts.py)
        ("dl_frameworks", "const t = tf.tensor([1, 2]);\n"),
        ("llm_api", "const client = new OpenAI();\n"),
        ("llm_orchestrator", 'const model = new ChatOpenAI({ model: "x" });\n'),
        ("llm_vector_store", "const client = new ChromaClient();\n"),
        ("cryptography", 'const h = crypto.createHash("sha256");\n'),
        ("hardware_bridge", 'const port = new SerialPort({ path: "/dev/ttyUSB0" });\n'),
        # the Anthropic tokenizer is a local utility, excluded from llm_api by design
        ("llm_api", 'import { countTokens } from "@anthropic-ai/tokenizer";\n'),
        # a different package whose name starts with a listed one
        ("cryptography", 'import x from "cryptography-utils";\n'),
        ("llm_orchestrator", 'import x from "airbnb-prop-types";\n'),
    ],
)
def test_typescript_import_family_negative_controls(family: str, src: str):
    assert _hits(family, src) == 0


# --- exfiltration_camouflage ---


@pytest.mark.parametrize(
    "src",
    [
        'fetch("https://x.io/checkmarx", opts);\n',
        'fetch("https://x.io/telemetry", opts);\n',
        'axios.post("https://x.io/metrics", data);\n',
        'https.request("https://x.io/audit");\n',
        'fetch("https://x.io/log", opts);\n',
    ],
)
def test_typescript_exfiltration_every_branch_fires(src: str):
    assert _hits("exfiltration_camouflage", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        'my_fetch("/telemetry");\n',
        'prefetch("/telemetry");\n',
        'myaxios.post("/log");\n',
        'myhttps.request("/audit");\n',
        'axios.postForm("/metrics");\n',
        # Req D: a GET is not an outbound send, and `login` is not log-shaped
        'axios.get("/telemetry");\n',
        'fetch("/login");\n',
    ],
)
def test_typescript_exfiltration_boundaries(src: str):
    assert _hits("exfiltration_camouflage", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9455")
@pytest.mark.parametrize("src", ['fetch("/api/blog");\n', 'fetch("/changelog");\n'])
def test_typescript_exfiltration_keyword_left_boundary(src: str):
    assert _hits("exfiltration_camouflage", src) == 0


# --- rce_funnel ---


@pytest.mark.parametrize("method", ["spawn", "exec", "execSync"])
@pytest.mark.parametrize("interp", ["python", "bash", "sh", "bun", "node"])
def test_typescript_rce_funnel_every_branch_fires(method: str, interp: str):
    assert _hits("rce_funnel", f'child_process.{method}("{interp}", args);\n') >= 1


@pytest.mark.parametrize(
    "src",
    [
        'child_process.spawnx("python");\n',
        'child_process.spawn("pythonista");\n',
        'child_process.exec("node_modules/.bin/x");\n',
        # Req D: a spawn whose command is not a shell or interpreter
        'child_process.spawn("ls", ["-l"]);\n',
    ],
)
def test_typescript_rce_funnel_boundaries(src: str):
    assert _hits("rce_funnel", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9457")
@pytest.mark.parametrize("src", ['my_child_process.spawn("python");\n', 'xchild_process.exec("bash");\n'])
def test_typescript_rce_funnel_left_boundary(src: str):
    assert _hits("rce_funnel", src) == 0


# --- telemetry ---

_TELEMETRY_OBJECTS = ("logger", "winston", "pino", "morgan", "datadog", "prometheus", "newrelic", "sentry")
_TELEMETRY_METHODS = ("info", "error", "warn", "debug", "trace", "log")


@pytest.mark.parametrize("obj", _TELEMETRY_OBJECTS)
def test_typescript_telemetry_every_branch_and_boundaries(obj: str):
    for method in _TELEMETRY_METHODS:
        assert _hits("telemetry", f'{obj}.{method}("x");\n') >= 1
    assert _hits("telemetry", f'my_{obj}.info("x");\n') == 0
    assert _hits("telemetry", f'my{obj}.info("x");\n') == 0
    assert _hits("telemetry", f'{obj}x.info("x");\n') == 0
    assert _hits("telemetry", f'{obj}.information("x");\n') == 0


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req D: a bare console print is debug_prints, not telemetry ...
        ("telemetry", 'console.log("x");\n'),
        ("telemetry", 'console.info("x");\n'),
        ("telemetry", 'console.error("x");\n'),
        # ... and a structured logger call is telemetry, not debug_prints
        ("debug_prints", 'logger.info("x");\n'),
    ],
)
def test_typescript_telemetry_vs_debug_prints(family: str, src: str):
    assert _hits(family, src) == 0


# --- explicit_casts ---


@pytest.mark.parametrize(
    "src",
    [
        'const el = document.getElementById("app") as HTMLElement;\n',
        "const v = x as unknown as Foo;\n",
        "const n = <Node>obj;\n",
    ],
)
def test_typescript_explicit_casts_every_branch_fires(src: str):
    assert _hits("explicit_casts", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        # `as` embedded in a longer word (TSX text) and the lowercase `as const` assertion
        "const v = <p>Ideas Matter</p>;\n",
        "const k = x as const;\n",
        # Req D: generic type arguments are not `<Type>value` casts
        "const m = new Map<string, Foo>();\n",
        "let a: Array<Node> = x;\n",
        "function f<T>(x: T) {}\n",
        "interface I extends Base<T> {}\n",
    ],
)
def test_typescript_explicit_casts_boundaries(src: str):
    assert _hits("explicit_casts", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9458")
@pytest.mark.parametrize(
    "src", ['import * as React from "react";\n', 'import { A as B } from "./a";\n', "export { X as Y };\n"]
)
def test_typescript_explicit_casts_import_export_alias(src: str):
    assert _hits("explicit_casts", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9459")
@pytest.mark.parametrize("src", ["class A extends B<T> implements C {}\n", "type T = Foo<Bar> extends X ? 1 : 0;\n"])
def test_typescript_explicit_casts_generic_before_keyword(src: str):
    assert _hits("explicit_casts", src) == 0
