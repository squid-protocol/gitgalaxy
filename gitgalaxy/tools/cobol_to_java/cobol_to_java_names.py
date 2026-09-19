#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Clean-Room Key -> Java Name
#
# PURPOSE:
# One place to turn a clean-room output key into the Java identifiers generated
# from it, so every forge names the same program the same way.
#
# ARCHITECTURAL DECISION (#3221):
# The clean room keys its outputs per path: the program's stem when that stem is
# unique in the repository, else the path under the target flattened with `__`
# (`multiroot__sam__SAM2`) -- see `_output_keys` in cobol_refractor_controller.py
# (#3218). The Java forges used to re-derive their class names from the IR's
# `metadata.file_name` (or a schema's `title`) instead, which throws that
# disambiguation away: two programs named SAM2.cbl both produced Sam2Service.java
# and the later one in filename order silently overwrote the earlier.
#
# Deriving the name from the key -- and only from the key -- restores the
# clean room's one-output-file-per-input-file invariant on the Java side. A key
# that is just a unique stem produces exactly the name the old code produced, so
# only a genuinely colliding program is renamed.
# ==============================================================================
import re
from pathlib import Path
from typing import Optional

# `COBOL__SAM2` -> ["COBOL", "SAM2"]; `WS-CUST_REC` -> ["WS", "CUST", "REC"].
_SEPARATORS = re.compile(r"[^A-Za-z0-9]+")

# A Java class name that would shadow something every generated file imports.
RESERVED_CLASSES = frozenset(
    {
        "Entity",
        "Class",
        "System",
        "Object",
        "String",
        "Enum",
        "Record",
        "Thread",
    }
)


def output_key(path: Path, suffix: str) -> str:
    """The clean-room key a generated artifact was written under.

    `suffix` is the artifact's trailing tag, e.g. `_ir` for `COBOL__SAM2_ir.json`
    or `_slice` for `COBOL__SAM2_slice.json`. Splitting on `_` does not work: a
    flattened key contains `__`, so `name.split("_")[0]` returns `COBOL`.
    """
    stem = path.stem
    return stem[: -len(suffix)] if suffix and stem.endswith(suffix) else stem


def java_class_base(key: str, prefix: str = "Legacy") -> str:
    """`COBOL__SAM2` -> `CobolSam2`; `SAM1LIB` -> `Sam1lib`; `BNK1CAC` -> `Bnk1cac`.

    A key that is a plain stem yields exactly what `"".join(w.capitalize() ...)`
    over the old program id yielded, which is why non-colliding programs keep
    their current class names.
    """
    name = "".join(word.capitalize() for word in _SEPARATORS.split(key) if word)
    if not name or name[0].isdigit() or name in RESERVED_CLASSES:
        # An empty, digit-leading or shadowing name is not a legal or safe class
        # name; `prefix` is what the entity forge already used for the last case.
        name = prefix + name
    return name


def java_url_segment(key: str) -> str:
    """The `@RequestMapping` path for a program: `COBOL__SAM2` -> `cobol-sam2`.

    Two programs that share a stem must not share a URL either -- Spring refuses
    to start on an ambiguous mapping.
    """
    return "-".join(word.lower() for word in _SEPARATORS.split(key) if word) or "legacy"


def program_key_from_ir(ir_state: dict, explicit: Optional[str] = None) -> str:
    """`explicit` (the caller's clean-room key) when given, else the IR's own file
    name. The fallback keeps the single-file CLIs and older callers working."""
    if explicit:
        return explicit
    raw = ir_state.get("metadata", {}).get("file_name", "") or ""
    return raw.split(".")[0]
