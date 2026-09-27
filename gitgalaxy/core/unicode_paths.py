# ==============================================================================
# GitGalaxy Core: Unicode path normalisation (#3815, epic #3811)
#
# macOS (HFS+ / APFS exports) and some zip / git checkouts write file names
# DECOMPOSED (NFD: `e` + U+0301), everything else composed (NFC: `é`). Without
# one form, the same estate scanned on two machines records two different
# paths, a delta scan sees a rename, and a `COPY` / `%INCLUDE` / `#include`
# spelled in one form never resolves a file stored in the other.
#
# The engine therefore STORES and REPORTS every path in NFC, and compares a
# name it read in source text (a copybook member, an include) in NFC too. The
# path it OPENS stays the real on-disk name: the orchestrator keeps that
# mapping for the few names where the two differ.
#
# An ASCII string is its own NFC form, so it is returned untouched: pure-ASCII
# estates stay byte-identical, and the check costs nothing on them.
# ==============================================================================
import unicodedata
from pathlib import Path


def nfc(text: str) -> str:
    """`text` in Unicode Normalization Form C (composed); ASCII comes back as it is."""
    return text if text.isascii() else unicodedata.normalize("NFC", text)


def on_disk(root: Path, rel: str) -> Path:
    """`root / rel` as the file system spells it: a consumer holding a STORED (NFC) path opens
    the real file even where the checkout wrote its name decomposed. Each missing component is
    looked up by its NFC form among its directory's entries; a path with no match anywhere comes
    back as `root / rel`, so the caller's own not-found handling still applies."""
    direct = root / rel
    if rel.isascii() or direct.exists():
        return direct
    cur = root
    for part in Path(rel).parts:
        nxt = cur / part
        if not nxt.exists() and cur.is_dir():
            want = nfc(part)
            nxt = next((c for c in sorted(cur.iterdir()) if nfc(c.name) == want), nxt)
        cur = nxt
    return cur if cur.exists() else direct
