"""#5876: the Tier 4 verdict never depends on wall-clock time (doom-fx convert/ConvSound1 flipped run to run)."""

import random
import time

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_TEXT = "#define A 1\nint main(void) { return 0; }\nif (x) { y(); }\nwhile (z) { w(); }\n"


def test_extensionless_verdict_ignores_the_clock(tmp_path, monkeypatch):
    f = tmp_path / "ConvSound1"
    f.write_text(_TEXT)
    verdicts = set()
    for seed in range(40):
        rng = random.Random(seed)
        monkeypatch.setattr(time, "time", lambda rng=rng: rng.random() * 10)
        det = LanguageDetector(LANGUAGE_DEFINITIONS, {})
        r = det.inspect(f, _TEXT, ext_tally={})
        verdicts.add((r.get("lang_id"), r.get("source_proof")))
    assert len(verdicts) == 1
