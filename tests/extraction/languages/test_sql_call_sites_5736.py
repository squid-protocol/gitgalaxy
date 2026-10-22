"""#5736: a Db2 SQL `CALL name` to a routine the file does not create is a call site (`call_site_data`),
resolved to the SQL file that creates it; a CALL of a routine the same file creates, a comment or a string
stays out, and a COBOL program of the same name is never the target."""

from gitgalaxy.core.invocation_resolver import resolve_invocations
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

CALLER = """\
-- CALL commented_out;
CREATE PROCEDURE HR.RAISE_PAY (IN P_ID INTEGER)
LANGUAGE SQL
BEGIN
  /* CALL in_block_comment(1); */
  CALL HR.AUDIT_LOG(P_ID);
  CALL "Notify_One";
  CALL LOCAL_HELPER(P_ID);
  SET V = 'CALL in_string';
  SELECT TAX_OF(P_ID) FROM T;
END;

CREATE PROCEDURE LOCAL_HELPER (IN P INTEGER)
BEGIN
  CALL audit_log(P);
END;
"""


def _sites(src: str) -> list[tuple[str, str, int]]:
    code = _PRISM.split_streams(src, "db2_sql")["code_stream"]
    calls = extract_boundary("sql", code)["calls"]
    return [(c["verb"], c["target"], c["line"]) for c in calls]


def test_declared_on_db2_sql_only_calls_leaving_the_file():
    assert LANGUAGE_DEFINITIONS["db2_sql"]["boundary_extraction"] == "sql"
    assert _sites(CALLER) == [("CALL", "AUDIT_LOG", 6), ("CALL", "NOTIFY_ONE", 7), ("CALL", "AUDIT_LOG", 15)]


def test_no_call_no_site():
    assert _sites("CREATE TABLE T (A INT);\nSELECT FOO(A) FROM T;\n") == []
    assert extract_boundary("sql", "") == {"calls": [], "datasets": [], "records": [], "transactions": []}


def _file(path: str, lang: str, functions=(), classes=(), sites=()):
    return {
        "path": path,
        "lang_id": lang,
        "functions": [{"name": n} for n in functions],
        "classes": [{"name": n} for n in classes],
        "call_sites": list(sites),
    }


def test_resolves_to_the_sql_file_never_a_cobol_program():
    site = {"verb": "CALL", "form": "literal", "operand": "AUDIT_LOG", "target": "AUDIT_LOG", "line": 6}
    files = [
        _file("db/caller.sql", "db2_sql", ["RAISE_PAY"], sites=[site]),
        _file("db/audit.sql", "db2_sql", ["audit_log"]),
        _file("src/AUDIT_LOG.cbl", "cobol", classes=["AUDIT_LOG"]),
    ]
    sites, edges = resolve_invocations(files)
    assert [(s["src_path"], s["resolved_path"]) for s in sites] == [("db/caller.sql", "db/audit.sql")]
    assert [(e["src"], e["dst"], e["edge_kind"]) for e in edges] == [("db/caller.sql", "db/audit.sql", "call")]


def test_a_cobol_call_still_ignores_sql_routines():
    site = {"verb": "CALL", "form": "literal", "operand": "AUDIT_LOG", "target": "AUDIT_LOG", "line": 3}
    files = [_file("src/MAIN.cbl", "cobol", classes=["MAIN"], sites=[site]), _file("db/a.sql", "db2_sql", ["AUDIT_LOG"])]
    sites, edges = resolve_invocations(files)
    assert sites[0]["resolved_path"] is None and edges == []
