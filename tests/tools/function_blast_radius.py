"""
Function blast radius from a master DB (#3330, Epic #3265 feature 3).

Which functions reach a given function through confident call links -- the
callers a change to it can break -- with the depth each is found at:

    python tests/tools/function_blast_radius.py out_master.db parse_config
    python tests/tools/function_blast_radius.py out_master.db save --file app/store.py --depth 3
    python tests/tools/function_blast_radius.py out_master.db save --downstream   # what it reaches

Reads fcall_data only (the rows core/call_resolver.py writes); ambiguous links
(nearest / receiver / tie) are never followed, the same rule func_pagerank and
func_upstream use. The query is a recursive CTE, so it also works from sqlite3:
see docs/function_call_graph.md.
"""

from __future__ import annotations

import argparse
import sqlite3

CONFIDENT = "('class', 'qualified', 'file', 'import', 'unique')"

# S608: interpolates only the CONFIDENT constant; the target ids are int()-ed before use.
UPSTREAM_SQL = f"""
WITH RECURSIVE reach(func_id, depth) AS (
    SELECT id, 0 FROM function_data WHERE id IN ({{targets}})
    UNION
    SELECT c.src_func_id, r.depth + 1
    FROM fcall_data c JOIN reach r ON c.dst_func_id = r.func_id
    WHERE c.step IN {CONFIDENT} AND c.src_func_id IS NOT NULL AND r.depth < ?
)
SELECT fd.file_path, fn.func_name, fn.start_line, MIN(r.depth)
FROM reach r JOIN function_data fn ON fn.id = r.func_id JOIN file_data fd ON fd.id = fn.file_id
WHERE r.depth > 0
GROUP BY r.func_id ORDER BY MIN(r.depth), fd.file_path, fn.start_line
"""  # noqa: S608

DOWNSTREAM_SQL = UPSTREAM_SQL.replace(
    "SELECT c.src_func_id, r.depth + 1\n    FROM fcall_data c JOIN reach r ON c.dst_func_id = r.func_id",
    "SELECT c.dst_func_id, r.depth + 1\n    FROM fcall_data c JOIN reach r ON c.src_func_id = r.func_id",
).replace("c.src_func_id IS NOT NULL", "c.dst_func_id IS NOT NULL")


def blast_radius(
    db: str, name: str, file: str | None = None, depth: int = 50, downstream: bool = False
) -> list[tuple[str, str, int, int]]:
    conn = sqlite3.connect(db)
    try:
        sql = "SELECT fn.id FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id WHERE fn.func_name = ?"
        args: list = [name]
        if file:
            sql += " AND fd.file_path = ?"
            args.append(file)
        targets = [r[0] for r in conn.execute(sql, args)]
        if not targets:
            return []
        query = (DOWNSTREAM_SQL if downstream else UPSTREAM_SQL).replace(
            "{targets}", ",".join(str(int(t)) for t in targets)
        )
        return [tuple(r) for r in conn.execute(query, (depth,))]
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("db")
    ap.add_argument("function")
    ap.add_argument("--file", help="restrict the target to one file (a name defined in several)")
    ap.add_argument("--depth", type=int, default=50)
    ap.add_argument("--downstream", action="store_true", help="what the function reaches, not what reaches it")
    a = ap.parse_args(argv)
    rows = blast_radius(a.db, a.function, a.file, a.depth, a.downstream)
    if not rows:
        print("no confident call links reach that function (or it was not found)")
        return 1
    for path, func, line, d in rows:
        print(f"{d:>3}  {path}:{line}  {func}")
    print(f"\n{len(rows)} function(s) {'reached' if a.downstream else 'upstream'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
