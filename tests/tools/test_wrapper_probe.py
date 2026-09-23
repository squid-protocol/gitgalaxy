"""
#3315 (epic #3313 step 1): the thin-wrapper probe's candidate, call-site and
resolution rules, each pinned on the smallest real shape that decided it.

  - fortran/wrf's `wrf_error_fatal` (`print *,string` then `stop`), called from
    another file: the case the epic exists for.
  - go/core's `func (cr *connReader) lock()`: a METHOD, reachable only as
    `cr.lock()`. The step-0 census credited it 209 bare `lock(` calls that go to
    a different, out-of-sample `lock`; the method rule makes that impossible.
  - a qualified call (`obj.log_it(...)`) is a call on something else.
  - two same-named definitions: a caller's own file wins; from a third file the
    name is ambiguous and credits nothing.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wrapper_probe as wp  # noqa: E402

from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

LABELS_FILE = Path(__file__).resolve().parent / "wrapper_labels.json"


def _probe(tmp_path, lang, files, rules):
    crucible = tmp_path / "data"
    group = crucible / lang / "repo"
    for rel, text in files.items():
        path = group / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    return wp.probe_group(lang, group, tuple(rules), 12, prism, crucible)


def _by_name(result):
    return {(c["name"], c["rule"], c["file"]): c for c in result["candidates"].values()}


WRF_WRAPPER = """\
subroutine wrf_error_fatal (string)
   character (len=*) :: string
   print *,string
   stop
end subroutine wrf_error_fatal
"""

WRF_CALLER = """\
subroutine init_domain (n)
   integer :: n
   if (n < 0) then
      call wrf_error_fatal('negative domain')
   end if
   if (n > 99) then
      call wrf_error_fatal('too many domains')
   end if
   call wrf_error_fatal('unreachable in practice')
end subroutine init_domain
"""


def test_a_thin_wrapper_is_credited_with_its_cross_file_call_sites(tmp_path):
    result = _probe(
        tmp_path,
        "fortran",
        {"wrapper.F": WRF_WRAPPER, "caller.F": WRF_CALLER},
        ["debug_prints", "panics_and_aborts"],
    )
    cands = _by_name(result)
    for rule in ("debug_prints", "panics_and_aborts"):
        wrapper = cands[("wrf_error_fatal", rule, "wrapper.F")]
        assert wrapper["sites"] == 3, "three calls from another file"
        assert (wrapper["branches"], wrapper["header_has_name"], wrapper["method"]) == (0, True, False)


GO_METHOD = """\
package http

func (cr *connReader) lock() {
	cr.mu.Lock()
}
"""

GO_CALLER = """\
package runtime

func park() {
	lock(&sched.lock)
	unlock(&sched.lock)
}
"""


def test_a_method_never_receives_unqualified_calls(tmp_path):
    """The census's go/core false attribution: bare `lock(` calls reach some other
    `lock`, never a method that can only be called as `cr.lock()`."""
    result = _probe(tmp_path, "go", {"server.go": GO_METHOD, "proc.go": GO_CALLER}, ["sync_locks"])
    lock = _by_name(result)[("lock", "sync_locks", "server.go")]
    assert lock["method"] is True
    assert lock["sites"] == 0


PY_WRAPPER = """\
def log_it(message):
    print(message)
"""

PY_CALLER = """\
def handler(obj):
    obj.log_it("a method on something else")
    log_it("the module-level helper")
"""


def test_a_qualified_call_is_a_call_on_something_else(tmp_path):
    result = _probe(tmp_path, "python", {"log.py": PY_WRAPPER, "handler.py": PY_CALLER}, ["debug_prints"])
    assert _by_name(result)[("log_it", "debug_prints", "log.py")]["sites"] == 1


PY_OTHER_WRAPPER = """\
def log_it(message):
    print("other:", message)


def local_caller():
    log_it("resolves to this file's own log_it")
"""

PY_THIRD = """\
def elsewhere():
    log_it("which log_it? two are defined")
"""


def test_same_file_wins_and_an_ambiguous_name_credits_nothing(tmp_path):
    result = _probe(
        tmp_path,
        "python",
        {"a.py": PY_WRAPPER, "b.py": PY_OTHER_WRAPPER, "c.py": PY_THIRD},
        ["debug_prints"],
    )
    cands = _by_name(result)
    assert cands[("log_it", "debug_prints", "b.py")]["sites"] == 1, "b.py's own caller"
    assert cands[("log_it", "debug_prints", "a.py")]["sites"] == 0
    assert result["unattributed_sites"] == {"debug_prints": 1}, "c.py's call is ambiguous"


def test_method_definitions_by_shape():
    assert wp.is_method_definition("go", "func (cr *connReader) lock() {", "lock")
    assert not wp.is_method_definition("go", "func lock(l *mutex) {", "lock")
    assert wp.is_method_definition("python", "def log(self, msg):", "log")
    assert not wp.is_method_definition("python", "def log(msg):", "log")
    assert wp.is_method_definition("lua", "function M.log(msg)", "log")
    assert wp.is_method_definition("cpp", "void Logger::log(const char *m) {", "log")


def test_the_label_file_is_well_formed():
    """Every verdict is one of the four labels and says why. A label is read from
    the body the probe prints, never set from a guess."""
    doc = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels = doc["labels"]
    assert len(labels) >= 60
    for key, entry in labels.items():
        group, file, name, rule = key.split("::")
        assert group and file and name and rule in wp.DEFAULT_RULES, key
        assert entry["label"] in wp.LABELS, key
        assert entry["reason"].strip(), key


def _filter(doc, max_loc):
    kept = {}
    for key, entry in doc["labels"].items():
        ev = entry["evidence"]
        if ev["sites"] and ev["loc"] <= max_loc and ev["header_has_name"] and ev["branches"] == 0:
            kept[key] = entry
    return kept


def test_the_recorded_filter_decision_reproduces_from_the_labels():
    """#3315's decision -- max_loc 8, aligned span, no branches -- re-scored from the
    committed labels and their recorded evidence, so the claim in the PR and on the
    epic cannot drift from the data it came from."""
    doc = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    max_loc = doc["filter"]["recommended_max_loc"]
    judged = {k: e for k, e in doc["labels"].items() if e["evidence"]["sites"] and e["evidence"]["loc"] <= max_loc}
    kept = _filter(doc, max_loc)

    def sites(entries, label=None):
        return sum(e["evidence"]["sites"] for e in entries.values() if label is None or e["label"] == label)

    assert sites(kept, "wrapper") == sites(judged, "wrapper"), "the filter drops a labelled wrapper's call sites"
    strict = sum(1 for e in kept.values() if e["label"] == "wrapper") / len(kept)
    assert strict >= 0.7
    assert sites(kept, "wrapper") / sites(kept) >= 0.95
