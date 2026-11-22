"""#7155 part 2: each canary-control job's `if:` cron string must match an `on.schedule` entry, or the job never runs."""

import re
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "canary-control.yml"


def _doc() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _crons(doc: dict) -> list[str]:
    on = doc.get(True) or doc.get("on")
    return [s["cron"] for s in on["schedule"]]


def _job_crons(doc: dict) -> dict[str, list[str]]:
    return {
        name: re.findall(r"github\.event\.schedule == '([^']+)'", job.get("if", ""))
        for name, job in doc["jobs"].items()
    }


def test_every_schedule_entry_is_claimed_by_exactly_one_job():
    doc = _doc()
    claimed = [c for crons in _job_crons(doc).values() for c in crons]
    assert sorted(claimed) == sorted(_crons(doc))


def test_every_job_cron_is_a_real_schedule_entry():
    doc = _doc()
    for name, crons in _job_crons(doc).items():
        assert crons, f"job {name} has no schedule condition"
        assert set(crons) <= set(_crons(doc)), f"job {name} waits on a cron that is not scheduled"


def _minutes_into_the_week(cron: str) -> int:
    minute, hour, _dom, _mon, dow = cron.split()
    return int(dow) * 1440 + int(hour) * 60 + int(minute)


def test_results_run_after_open_not_before():
    doc = _doc()
    jobs = _job_crons(doc)
    opened = _minutes_into_the_week(jobs["open"][0])
    settled = _minutes_into_the_week(jobs["results"][0])
    assert settled > opened
    # the control PR's gates need time to finish; the tool counts a check pending past 24 h as a miss
    assert settled - opened >= 6 * 60
