"""#4309: the oracle every proof compares against is pinned (tests/equivalence/gnucobol.Dockerfile) and recorded.

Pure parts here: the pin is read from the Dockerfile and IS a pin (a digest, an exact package version), a
fingerprint that differs from it is named value by value, strict mode refuses it, and `--reuse` carries the earlier
run's oracle. The fingerprint of a real image needs Docker: EQUIVALENCE_E2E=1.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_oracle as eo  # noqa: E402

PINNED = eo.pin()


def _observed(**over):
    labels = {eo.LABEL + "base": PINNED["base"], eo.LABEL + "gnucobol3": PINNED["gnucobol3"],
              eo.LABEL + "cobc": PINNED["cobc"]}  # fmt: skip
    labels.update(over.pop("labels", {}))
    return {"labels": labels, "cobc": PINNED["cobc"], "gnucobol3": PINNED["gnucobol3"], **over}


def test_the_dockerfile_pins_the_base_by_digest_and_gnucobol_by_exact_version():
    assert re.fullmatch(r"debian:bookworm-slim@sha256:[0-9a-f]{64}", PINNED["base"])
    assert re.fullmatch(r"\d+\.\d+\.\d+-[0-9A-Za-z.+~]+", PINNED["gnucobol3"])  # a Debian revision, not a range
    assert PINNED["cobc"] == "cobc (GnuCOBOL) 3.1.2.0"  # #4309: the version every proof so far rests on
    text = eo.DOCKERFILE.read_text(encoding="utf-8")
    assert "gnucobol3=${GNUCOBOL}" in text, "apt-get must install the pinned version, not the current one"
    assert re.search(r"^FROM \$\{BASE\}$", text, re.M), "the image must be built FROM the pinned base"
    for key in ("base", "gnucobol3", "cobc"):
        assert f"{eo.LABEL}{key}=" in text, f"the image must carry its pin as a label ({key})"


def test_the_db2_image_builds_from_the_oracle_image():
    text = (eo.DOCKERFILE.parent / "gnucobol-db2.Dockerfile").read_text(encoding="utf-8")
    assert re.search(rf"^FROM {re.escape(eo.IMAGE)}$", text, re.M)


def test_the_pinned_image_matches():
    assert eo.mismatches(_observed(), PINNED) == []


@pytest.mark.parametrize(("over", "named"), [
    ({"cobc": "cobc (GnuCOBOL) 3.2.0"}, "cobc"),
    ({"gnucobol3": "3.2-1"}, "gnucobol3"),
    ({"labels": {eo.LABEL + "base": None}}, "base"),  # an image built before the pin carries no labels
    ({"labels": {eo.LABEL + "gnucobol3": "3.2-1"}}, "gnucobol3 label"),  # a --build-arg override
])  # fmt: skip
def test_a_difference_from_the_pin_is_named(over, named):
    wrong = eo.mismatches(_observed(**over), PINNED)
    assert wrong and wrong[0].startswith(named + ":"), wrong


def _fake(monkeypatch, observed):
    monkeypatch.setattr(eo, "_cache", {})
    monkeypatch.setattr(eo, "_inspect", lambda image: {"id": "sha256:" + "0" * 64, "labels": observed["labels"]})
    monkeypatch.setattr(eo, "_probe", lambda image: (observed["cobc"], observed["gnucobol3"]))


def test_a_mismatch_warns_and_is_recorded(monkeypatch, capsys):
    monkeypatch.delenv(eo.STRICT_ENV, raising=False)
    _fake(monkeypatch, _observed(cobc="cobc (GnuCOBOL) 3.2.0"))
    fp = eo.checked()
    assert fp["matches_pin"] is False and fp["cobc"] == "cobc (GnuCOBOL) 3.2.0"
    assert "WARNING" in capsys.readouterr().err
    assert all(not k.startswith("_") for k in fp), "the report records no process-local keys"
    json.dumps(fp)


def test_strict_refuses_a_mismatched_oracle(monkeypatch):
    monkeypatch.setenv(eo.STRICT_ENV, "1")
    _fake(monkeypatch, _observed(gnucobol3="3.2-1"))
    with pytest.raises(eo.OracleMismatch, match="gnucobol3"):
        eo.checked()


def test_the_pinned_oracle_is_recorded_quietly(monkeypatch, capsys):
    monkeypatch.setenv(eo.STRICT_ENV, "1")
    _fake(monkeypatch, _observed())
    fp = eo.for_case({"name": "x"})
    assert fp["matches_pin"] is True and fp["mismatches"] == [] and fp["pin"] == PINNED
    assert fp["image"]["name"] == eo.IMAGE
    assert capsys.readouterr().err == ""


def test_a_reused_run_records_the_earlier_runs_oracle(monkeypatch, tmp_path):
    monkeypatch.setattr(eo, "_cache", {})
    monkeypatch.setattr(eo, "_inspect", lambda image: pytest.fail("a reused run must not fingerprint again"))
    earlier = {"format": eo.FORMAT, "image": {"name": eo.IMAGE, "id": "sha256:" + "1" * 64}, "cobc": PINNED["cobc"],
               "gnucobol3": PINNED["gnucobol3"], "base": PINNED["base"], "pin": PINNED, "matches_pin": True,
               "mismatches": []}  # fmt: skip
    (tmp_path / "report.json").write_text(json.dumps({"oracle": earlier}), encoding="utf-8")
    eo.adopt_from({"name": "x"}, tmp_path)
    assert eo.for_case({"name": "x"}) == earlier


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker and the built oracle image")
def test_the_built_image_is_the_pinned_oracle(monkeypatch):
    monkeypatch.setattr(eo, "_cache", {})
    fp = eo.fingerprint()
    assert fp["matches_pin"], fp["mismatches"]
