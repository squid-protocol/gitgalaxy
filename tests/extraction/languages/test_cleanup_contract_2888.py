# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `cleanup` contract (#2888, docs/cleanup_rule_contract.md), held across
every edited corpus language in one place.

    A site that explicitly destroys state or releases a held resource --
    a deallocation or finalization call, a handle or connection close,
    removal of an entry from a live container or of external state the
    program owns, or the opener of a guaranteed-teardown region -- in
    call or statement form.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
audit found the old rules disagreeing on:

  C1 a declaration is not a site: `def close(self):`, `fn drop(&mut self)`,
     `void dispose() {`, `dispose(): void;`, `sub DESTROY {`, `- free`,
     an ABAP ALIASES line, a makefile `clean:` target header -- each names
     or declares the routine; the hit is where teardown actually runs.
  C2 termination is not release: shell `exit`/`logout` end the process
     (panics_and_aborts owns them) and agc `EXIT` transfers control;
     `ENDOFJOB`/`RESUME` stay as the executive's own release forms.
  C3 a name is not a site: a token inside a string or POD heading, a
     hyphenated COBOL paragraph name, a scheme handler-table argument, a
     perl `return undef` placeholder -- the rule must anchor the operative
     form (call parens, statement position, an operand).
  C4 configuring the reclaimer is not reclaiming: lua
     `collectgarbage("stop"/"restart"/"count")` tune or query the
     collector; only collecting forms count.
  C5 one owner per token: go `Unlock`/`RUnlock` are sync_locks', js/ts
     `.delete(` is state_mutation's container mutator (#2765), cobol
     `END-DECLARATIVES` is structure (#2869's END-* family), the root-form
     `rm -rf /` is high_risk_execution's.
  #2843 resolved: destruction of external state the program owns is
     cleanup's (the sqlite DROP TABLE precedent): c gains `remove(`, tcl
     gains `file delete`, cobol gains `DELETE`, shell gains the non-root
     `rm` flags-with-f family.

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="cleanup"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: a declaration is not a site ------------------------------------------
    "python": (
        ["conn.close()", "gc_root.__exit__(None, None, None)", "pool.shutdown()"],
        ["def close(self):", "async def close(self) -> None:"],
    ),
    "embedded_python": (
        ["conn.close()", "gc.collect()"],
        ["def close(self):", "def __exit__(self, t, v, tb):"],
    ),
    "rust": (
        ["drop(conn);", "self.data.drop(cap, len);", "close(fd);"],
        ["fn drop(&mut self) {", "pub(crate) unsafe fn drop(&mut self, cap: usize) {"],
    ),
    "csharp": (
        ["stack.Free();", "GC.Collect();", "GC.SuppressFinalize(conn);"],
        ["public void Dispose()", "void Dispose();"],
    ),
    "dart": (
        ["super.dispose();", "_cursorTimer?.cancel();", "dispose(conn);"],
        ["void dispose() {"],
    ),
    "java": (
        ["context.close();", "release(conn);"],
        ["private static void close(ApplicationContext context) {"],
    ),
    "perl": (
        ["undef $conn;", "undef($conn);", "$sth->finish;", "finish($conn);", "close($fh);"],
        ["return undef;", "func(undef, $x);", "sub finish {", "sub DESTROY {", "=head2 finish"],
    ),
    "objective-c": (
        ["free(style);", "[super free];", "[pool release];"],
        ["- free", "- (void)free"],
    ),
    "scala": (
        ["close(channel.id)", "receive.close()", "} finally {", "bracket"],
        ['def close(): Unit = {', 'error(s"session close with correlation")'],
    ),
    "typescript": (
        ["conn.close();", "subscription.dispose();", "clearTimeout(id);"],
        ["dispose(): void;", "dispose() {", "function close() {"],
    ),
    "javascript": (
        ["conn.close();", "disposable.dispose();", "removeEventListener('abort', fn);"],
        ["dispose() {"],
    ),
    "zig": (
        ["defer arena_allocator.deinit();", "errdefer msg.destroy(sema.gpa);", "free(conn);"],
        ["pub fn deinit(self: *Analyser) void {"],
    ),
    "abap": (
        ["CLEAR ls_object.", "FREE cv_conn.", "CLEAR: ls_item-path, ls_item-name."],
        ["    clear FOR zif_abapgit_ajson~clear,"],
    ),
    # --- C2: termination is not release -------------------------------------------
    "shell": (
        ["rm -f scratch", "rm -rf build/", 'rm -fr "${testdir}"', "unset scratch", "trap cleanup_tmp EXIT"],
        ["exit 0", "exit 1", "logout", "-s exit:2", "rm -rf /"],
    ),
    "agc_assembly": (
        ["TC\tENDOFJOB", "TCF\tRESUME"],
        ["EXIT"],
    ),
    # --- C3: a name is not a site --------------------------------------------------
    "cobol": (
        ["CLOSE XREF-FILE", "FREE HANDLE-A.", "DELETE TRANSACT-FILE RECORD"],
        ["PERFORM 9000-DALYTRAN-CLOSE.", "move OP-CLOSE to opcode", "'CLOSE CUR1'", "END-DECLARATIVES."],
    ),
    "scheme": (
        ["(close-port conn)", "(close-input-port conn)", "(on-reset (close-port ip)"],
        ["(call-port-handler close-port who port)", "(set-who! close-port", "close-port"],
    ),
    "matlab": (
        ["clear ALLEEG;", "delete(EEGMENU(end));", "close; error('ABORT');", "onCleanup(conn);", "if x, fclose(fid); end"],
        ["x = close_price + 1", "disp('use clear when done')"],
    ),
    # --- C4: configuring the reclaimer is not reclaiming ---------------------------
    "lua": (
        ["collectgarbage()", 'collectgarbage("collect")', 'collectgarbage("step", 0)', "io.close()", "f:close()"],
        ['collectgarbage("stop")', 'collectgarbage("restart")', 'collectgarbage("count")'],
    ),
    # --- C5: one owner per token ---------------------------------------------------
    "go": (
        ["c.rwc.Close()", "Stop(conn)", "defer w.Close()"],
        ["defer s.mu.Unlock()", "proxier.mu.RUnlock()"],
    ),
    # --- #2843: destruction of external state is cleanup's -------------------------
    "c": (
        ["free(conn);", "fclose(fp);", "remove(tmppath);"],
        [],
    ),
    "tcl": (
        ["close $fd", "unset scratch", "file delete -force $tmp"],
        [],
    ),
    "makefile": (
        ["\trm -f leftovers", "\trm -rf build/"],
        ["clean:", "distclean:", "clean::"],
    ),
}


@pytest.mark.parametrize("lang", sorted(CASES))
def test_cleanup_contract_cases(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for snippet in positives:
        assert rule.search(snippet), f"{lang}: expected cleanup hit in {snippet!r}"
    for snippet in negatives:
        assert not rule.search(snippet), f"{lang}: unexpected cleanup hit in {snippet!r}"


# The tokens #2888 hands to (or confirms with) another owner: the OTHER rule
# must fire so the construct stays measured, just once.
DUALS = [
    ("go", "sync_locks", "defer s.mu.Unlock()"),
    ("typescript", "state_mutation", "mySet.delete('x');"),
    ("javascript", "state_mutation", "mySet.delete('x');"),
    ("shell", "panics_and_aborts", "exit 1"),
    ("shell", "high_risk_execution", "rm -rf /"),
    ("makefile", "func_start", "clean:"),
]


@pytest.mark.parametrize("lang,owner,snippet", DUALS)
def test_cleanup_retired_tokens_have_a_live_owner(lang, owner, snippet):
    assert not _rule(lang).search(snippet), f"{lang}: cleanup still claims {snippet!r}"
    assert _rule(lang, owner).search(snippet), f"{lang}: {owner} does not claim {snippet!r}"


def test_cleanup_contract_redos_sweep():
    """Detonate every edited pattern on payloads aimed at its new anchors."""
    payloads = [
        "rm -" + "a" * 50000,
        "collectgarbage(" + " " * 50000,
        "undef" + " " * 50000,
        "close" + "(" * 200 + "x" * 50000,
        "trap " + "x" * 50000,
        "\t" * 200 + "rm -f " + "y" * 50000,
        "-" * 50000 + "CLOSE",
    ]
    for lang in sorted(CASES):
        rule = _rule(lang)
        for payload in payloads:
            assert_redos_immune(rule, payload, timeout_sec=3.0)
