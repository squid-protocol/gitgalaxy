---
description: "Use LanguageDeltaModel and StyleAxis in structural_fingerprint.lattice to remove language syntax offsets and attribute AI model or author style across languages."
---
# How to Attribute AI Model & Author Style Across Languages

Raw 32-keyword-family distributions (`kw_JSD`) separate generating models with **`0.944` ROC AUC** when both repositories are in the **same task and language**. Across different languages, however, syntax idioms (e.g. Python vs. C vs. Rust) dominate the raw vector.

In `structural_fingerprint.lattice`, **`LanguageDeltaModel`** and **`StyleAxis`** factor out language syntax via **additive translation vectors (`delta_lang`)**—which match or outperform 32×32 Orthogonal Procrustes (`0.698` vs. `0.645` on held-out `chess`) and transfer zero-shot across tasks (`0.730` ROC AUC on held-out `explore/`).

---

## 1. Extract 32-Keyword-Family Profiles

```python
from pathlib import Path
from structural_fingerprint import blind as BL
from structural_fingerprint.fingerprint import build
from structural_fingerprint.lattice import (
    fit_language_deltas,
    fit_style_axis,
    keyword_lattice_profile,
)
from structural_fingerprint.reference import load_reference
from structural_fingerprint.scan_io import load_scan, resolve_scans

ref = load_reference("portable")

def kw_dist(scan_dir: Path):
    sc = load_scan(resolve_scans([scan_dir])[0], ref.signal_columns)
    ft = build(sc, ref, min_loc=3, keyword_mode="composition").functions
    bv = BL.blind_view(ft)
    _, _, dist = keyword_lattice_profile(sc.signals, bv.rows)
    return dist
```

---

## 2. Center Languages with `LanguageDeltaModel`

Fit per-language centroids on a domain-matched calibration set (e.g. `chess` runs across C, Python, Rust, Java, COBOL):

```python
dists_by_lang = {
    "c": [kw_dist(p) for p in c_scans],
    "python": [kw_dist(p) for p in py_scans],
    "rust": [kw_dist(p) for p in rs_scans],
}
lang_model = fit_language_deltas(dists_by_lang)

# Language-centered comparison across two different languages
d_centered = lang_model.centered_distance(
    kw_dist(cand_c), "c",
    kw_dist(cand_py), "python",
)

# Predict how a C profile shifts when translated to Go or Java
predicted_py = lang_model.predict_translation(kw_dist(cand_c), "c", "python")
```

---

## 3. Score Model / Author Style with `StyleAxis`

Fit a linear difference-of-means axis in language-centered space and apply it zero-shot to new tasks or languages:

```python
claude_centered = [lang_model.center(d, lang) for d, lang in claude_runs]
codex_centered = [lang_model.center(d, lang) for d, lang in codex_runs]

axis = fit_style_axis(
    claude_centered,
    codex_centered,
    pos_label="claude",
    neg_label="codex",
)

score = axis.score(lang_model.center(kw_dist(held_out_scan), "cobol"))
```

Both `LanguageDeltaModel` and `StyleAxis` support `.to_dict()` and `.from_dict()` for JSON persistence.

---

## 4. Choosing `delta_lang`: Domain-Matched vs. `keyword-rosetta`

- **Use domain-matched `delta_lang`** when attributing **subtle model or author style** across languages (e.g. `chess ↔ sat` or `explore/`). General-purpose `keyword-rosetta` centroids introduce domain mismatch that can mask small model residuals (`0.660 → 0.601` on `chess`).
- **Use `keyword-rosetta` centroids** when predicting **coarse `C → target` language shifts** on large translations (all 5 tested DOOM translations—`mochadoom`, `doomf77`, `managed-doom`, `gore`, `dartdoom`—improved JSD zero-shot by `-0.048` to `-0.165`).

---

**[⬅️ Back to Master Index](../index.md)**
