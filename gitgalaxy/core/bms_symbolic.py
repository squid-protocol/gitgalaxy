# ==============================================================================
# GitGalaxy Core: COBOL symbolic maps generated from BMS source (#3490)
#
# PURPOSE:
# A CICS program COPYs the symbolic map of its screen -- the copybook the BMS
# assembler (DFHMAPS, TYPE=DSECT) generates from the map source. That copybook
# is a BUILD artefact and is usually not in the repository (CBSA ships none of
# its ten), so every `MOVE CUSTNAMI TO ...` left the screen field unresolved and
# field lineage (#3452) stopped at the terminal. The layout is fully determined
# by the BMS source, which the screen-field channel (#3347) already reads, so it
# is generated here as COBOL copybook TEXT -- the reader parses it with the same
# record parser as any real copybook.
#
# LAYOUT (per DFHMDI map M, named DFHMDF fields F in source order):
#
#   01  MI.                               01  MO REDEFINES MI.
#       02  FILLER PIC X(12).   (TIOAPFX)     02  FILLER PIC X(12).
#       02  FL    COMP  PIC  S9(4).           02  FILLER PICTURE X(3).
#       02  FF    PICTURE X.                  02  FC    PICTURE X.  } one per
#       02  FILLER REDEFINES FF.              02  FP    PICTURE X.  } extended
#         03 FA    PICTURE X.                 02  FH ... FV ...     } attribute
#       02  FILLER   PICTURE X(k).  (k attrs) 02  FO  PIC X(len) | PICOUT.
#       02  FI  PIC X(len) | PICIN.
#
# Extended attributes come from DSATTS= (map, else mapset), or all four
# (COLOR, PS, HILIGHT, VALIDN) under EXTATT=YES; they are laid out in the fixed
# order C (COLOR) P (PS) H (HILIGHT) V (VALIDN) U (OUTLINE) M (SOSI) T (TRANSP).
# Verified byte-for-byte against the 21 generated copybooks CardDemo checks in.
#
# SCOPE AND NON-SCOPE:
#   - COBOL only (a PL/I or assembler symbolic map has other syntax).
#   - A field with OCCURS=n becomes `02 FD OCCURS n TIMES.` over its L/F/A/I items
#     in the input map and `02 DFHMSn OCCURS n TIMES.` over its attribute and O
#     items in the output map -- IBM's documented form; no generated copybook
#     with an OCCURS field exists in the pinned corpora to verify it against.
#   - GRPNAME field groups are laid out as separate fields.
# ==============================================================================
import re
from typing import Any, Optional

_ATTR_ORDER = (("COLOR", "C"), ("PS", "P"), ("HILIGHT", "H"), ("VALIDN", "V"), ("OUTLINE", "U"), ("SOSI", "M"),
               ("TRANSP", "T"))  # fmt: skip
_EXTATT_YES = ("COLOR", "PS", "HILIGHT", "VALIDN")


def _operand(attributes: Optional[str], key: str) -> Optional[str]:
    """The value of KEY= in a statement's kept operand text (parenthesised lists whole)."""
    m = re.search(rf"(?<![A-Z0-9]){key}=(\([^)]*\)|[^,]*)", attributes or "", re.I)
    return m.group(1).strip().upper() if m else None


def _suffixes(*scopes: Optional[str]) -> list[str]:
    """The extended-attribute suffix letters of a map, innermost scope first."""
    for attrs in scopes:
        dsatts = _operand(attrs, "DSATTS")
        if dsatts:
            names = set(dsatts.strip("()").split(","))
            return [letter for name, letter in _ATTR_ORDER if name in names]
        if _operand(attrs, "EXTATT") == "YES":
            return [letter for name, letter in _ATTR_ORDER if name in _EXTATT_YES]
    return []


def _pic(pic: Optional[str], length: int) -> str:
    return pic if pic else f"X({length})"


def symbolic_maps(screen_rows: list[Any]) -> dict[str, str]:
    """Mapset name -> the COBOL symbolic-map copybook text its BMS source generates.

    `screen_rows` are one BMS file's screen-field rows (dicts or EngineScreenField,
    #3347). A mapset with no DFHMDI generates nothing."""

    def get(r: Any, k: str) -> Any:
        return r.get(k) if isinstance(r, dict) else getattr(r, k)

    by_ordinal = {get(r, "ordinal"): r for r in screen_rows}
    out: dict[str, list[str]] = {}
    for m in (r for r in screen_rows if get(r, "kind") == "map" and get(r, "name")):
        mapset = by_ordinal.get(get(m, "parent_ordinal"))
        ms_attrs = get(mapset, "attributes") if mapset is not None else None
        ms_name = (get(mapset, "name") if mapset is not None else None) or get(m, "name")
        prefix = "YES" in (_operand(get(m, "attributes"), "TIOAPFX"), _operand(ms_attrs, "TIOAPFX"))
        letters = _suffixes(get(m, "attributes"), ms_attrs)
        fields = [
            f
            for f in screen_rows
            if get(f, "kind") == "field" and get(f, "parent_ordinal") == get(m, "ordinal") and get(f, "name")
        ]
        name = get(m, "name").upper()
        inp = [f"       01  {name}I."]
        outp = [f"       01  {name}O REDEFINES {name}I."]
        if prefix:
            inp.append("           02  FILLER PIC X(12).")
            outp.append("           02  FILLER PIC X(12).")
        dfhms = 0
        for f in fields:
            fname, length = get(f, "name").upper(), get(f, "length") or 1
            occurs = get(f, "occurs")
            lvl, ind = ("03", "  ") if occurs else ("02", "")
            if occurs:
                dfhms += 1
                inp.append(f"           02  {fname}D OCCURS {occurs} TIMES.")
                outp.append(f"           02  DFHMS{dfhms} OCCURS {occurs} TIMES.")
            inp += [
                f"           {ind}{lvl}  {fname}L    COMP  PIC  S9(4).",
                f"           {ind}{lvl}  {fname}F    PICTURE X.",
                f"           {ind}{lvl}  FILLER REDEFINES {fname}F.",
                f"           {ind}  {int(lvl) + 1:02d} {fname}A    PICTURE X.",
            ]
            if letters:
                inp.append(f"           {ind}{lvl}  FILLER   PICTURE X({len(letters)}).")
            inp.append(f"           {ind}{lvl}  {fname}I  PIC {_pic(get(f, 'picin'), length)}.")
            outp.append(f"           {ind}{lvl}  FILLER PICTURE X(3).")
            outp += [f"           {ind}{lvl}  {fname}{c}    PICTURE X." for c in letters]
            outp.append(f"           {ind}{lvl}  {fname}O  PIC {_pic(get(f, 'picout'), length)}.")
        out.setdefault(ms_name.upper(), []).extend(inp + outp)
    return {k: "\n".join(v) + "\n" for k, v in out.items()}
