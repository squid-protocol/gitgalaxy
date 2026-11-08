#!/usr/bin/env python3
"""Recompute the real matches drawn by copyfinding_explainer.py (prints a JSON table).

Uses the temporal-crucible LAY study's own scoring code (tools/lay_eval.py, tools/ut_eval.py) unchanged:
  L1    = negative Euclidean distance between sfs vectors (the coarse fingerprint)
  L2    = Jaccard of calls_out_to sets (own name removed)
  L3    = Jaccard of control-flow-skeleton 3-shingles
  L1+L2 = reciprocal-rank fusion (k = 60) of L1 and L2
  FUSED = reciprocal-rank fusion of L1, L2, L3 (LAY's layered fingerprint)
Ranks are pessimistic (ties put the true copy last) among every BoringSSL function of >= 6 lines (6,802), as in LAY.

Queries: the OpenSSL quarterly snapshot 2172e0c098cd (2026-03-31) from the study's scan DB; BoringSSL head e375adcf13f8
(2026-11-06, C++) from UT's fork scan. Truth is LAY's rule -- same function name, token Jaccard >= 0.5 -- with one
extension for the renamed set: OpenSSL's `ossl_` prefix is stripped before comparing names. No match uses names.

  cd <temporal-crucible checkout> && SFS_SRC=<popan>/structural-fingerprint-scanner/src \\
      <engine venv>/bin/python <this file> --tools tools --scratch /tmp/cfx/scratch > copyfinding_data.json
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

FILE = "crypto/x509/v3_utl.c"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", type=pathlib.Path, required=True)
    ap.add_argument("--scratch", type=pathlib.Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.tools.resolve()))
    import lay_eval as LE  # noqa: E402

    U = LE.U
    ref = U.load_reference("structure")
    fk = U.Fork("boringssl", ref)
    cand = np.flatnonzero(fk.ft.loc >= 6)
    calls = LE.db_calls(U.POOL_DIR / "ut_forks" / "boringssl" / "boringssl_galaxy_master.db")
    C2, SK, NM, PT, BODY = [], [], [], [], []
    for i in cand:
        p, nm = str(fk.ft.path[i]), str(fk.ft.name[i])
        body = fk.body(i) or ""
        C2.append(calls.get((p, nm), set()) - {U.short(nm)})
        SK.append(LE.skeleton(body, U.lang_of(p)) if body else set())
        NM.append(nm), PT.append(p), BODY.append(body)
    V = fk.ft.vectors[cand]
    snap = U.snapshots("openssl")[-1]
    db = U.export("openssl", snap["sha"], a.scratch / f"openssl_{snap['sha'][:12]}")
    q = U.build(U.load_scan(db, ref.signal_columns, name="openssl"), ref, min_loc=3).functions
    qcalls = LE.db_calls(db)

    def key(n):
        k = U.short(n)
        return k[5:] if k.startswith("ossl_") else k

    byname = collections.defaultdict(list)
    for i, n in enumerate(NM):
        byname[key(n)].append(i)
    srcs = {}
    out = {"openssl_sha": snap["sha"], "boringssl_sha": fk.sha, "candidates": int(len(cand)), "file": [], "renamed": []}
    for qi, (p, nm) in enumerate(zip(map(str, q.path), map(str, q.name))):
        if not (p.startswith(("crypto/", "ssl/")) and p.endswith(".c")) or q.loc[qi] < 6 or key(nm) not in byname:
            continue
        renamed_q = U.short(nm).startswith("ossl_")
        if p != FILE and not renamed_q:
            continue
        if p not in srcs:
            src = U._git(U.POOL_DIR / "openssl", "show", f"{snap['sha']}:{p}", text=False)
            srcs[p] = {n2: (s, b) for s, _e, n2, b in U.spans(src, "c")}
        if nm not in srcs[p]:
            continue
        line, body = srcs[p][nm]
        best = max((U.jacc(body, BODY[i]), i) for i in byname[key(nm)] if BODY[i])
        if best[0] < 0.5:
            continue
        t = best[1]
        own = U.short(nm)
        qc = qcalls.get((p, nm), set()) - {own}
        qsk = LE.skeleton(body, "c")
        s1 = -np.linalg.norm(V - q.vectors[qi], axis=1)
        s2 = np.array([LE.jac(qc, c) for c in C2])
        s3 = np.array([LE.jac(qsk, s) for s in SK])
        rr = lambda *ss: sum(1.0 / (LE.K_RRF + LE.all_ranks(s)) for s in ss)  # noqa: E731
        sc = {"L1": s1, "L2": s2, "L3": s3, "L12": rr(s1, s2), "FUSED": rr(s1, s2, s3)}
        bline = next(
            (
                s
                for s, _e, n2, _b in U.spans(U._git(fk.repo, "show", f"{fk.sha}:{PT[t]}", text=False), U.lang_of(PT[t]))
                if U.short(n2) == U.short(NM[t])
            ),
            0,
        )
        row = {
            "a_path": p,
            "a": nm,
            "a_line": line,
            "loc": int(q.loc[qi]),
            "b_path": PT[t],
            "b": NM[t],
            "b_line": bline,
            "tok_jaccard": round(best[0], 2),
            **{m: LE.pess_rank(s, t) for m, s in sc.items()},
        }
        out["file" if p == FILE and not renamed_q else "renamed"].append(row)
    out["file"].sort(key=lambda r: r["a_line"])
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
