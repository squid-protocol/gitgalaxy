"""#3822: generated repositories keep the mainframe's key order and never merge distinct keys.

A KSDS browse follows the key's EBCDIC bytes (lower case before upper, letters before digits); a database's
default collation folds case and accents (MySQL's makes `ABC` = `abc`). With culture.key_collation `ebcdic`
(the default) a String key gets a sort column of its code-page bytes that browses order by; `ebcdic` and
`binary` both give key columns a byte-wise collation; `database` leaves both to the database, as before.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import COBOL_RECORDS_JAVA

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_vsam_repositories as vsam  # noqa: E402 -- the VSAM estate, re-keyed on a text field below

_JDK = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin")
KEYS = ["A001", "a001", "1001", "Ä001", "A-01", "A 01"]


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    """The #3617 estate with ACCT-ID a PIC X(8) key, so the store's key is a String."""
    base = tmp_path_factory.mktemp("key_collation")
    repo = base / "estate"
    files = {
        "cbl/ACCTCICS.cbl": vsam.ACCTCICS,
        "cbl/ACCTBAT.cbl": vsam.ACCTBAT.replace("FD-ACCT-ID       PIC 9(8)", "FD-ACCT-ID       PIC X(8)"),
        "cbl/TCATBAT.cbl": vsam.TCATBAT,
        "cpy/ACCTREC.cpy": vsam.ACCTREC.replace("ACCT-ID          PIC 9(8)", "ACCT-ID          PIC X(8)"),
        "jcl/VSAMJOB.jcl": vsam.JOB,
        "csd/APP.csd": vsam.CSD,
    }
    assert "PIC X(8)" in files["cpy/ACCTREC.cpy"] and "PIC X(8)" in files["cbl/ACCTBAT.cbl"]
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, vsam.scan_to_db(repo, base / "scan")


def _generated(scanned, tmp_path, culture=None, engine="postgresql"):
    config = {"database": {"engine": engine}, "culture": culture or {}}
    _, src = vsam._java(scanned, tmp_path, config)
    read = lambda rel: (src / rel).read_text(encoding="utf-8")  # noqa: E731
    return (read("entity/vsam/AcctRec.java"), read("repository/vsam/AcctRecRepository.java"),
            read("service/AcctcicsService.java"), read("entity/vsam/FdTcatRecKey.java"))  # fmt: skip


def test_ebcdic_browses_by_a_code_page_sort_column(scanned, tmp_path):
    entity, repo, service, key = _generated(scanned, tmp_path)
    assert '@Column(name = "ACCT_ID", columnDefinition = "varchar(8) COLLATE \\"C\\"")' in entity
    assert '@Column(name = "ACCT_ID_SORT", columnDefinition = "varchar(16) COLLATE \\"C\\"")' in entity
    assert "private String acctIdSort;" in entity
    assert '    @PrePersist\n    @PreUpdate\n    void codePageSortKey() {\n        this.acctIdSort = CobolRecords.sortKey(acctId, "cp037");' in entity  # fmt: skip
    assert "findByAcctIdSortGreaterThanEqualOrderByAcctIdSortAsc(String acctIdSort, Pageable page);" in repo
    assert "findByAcctIdSortLessThanEqualOrderByAcctIdSortDesc(String acctIdSort, Pageable page);" in repo
    assert 'findByAcctIdSortGreaterThanEqualOrderByAcctIdSortAsc(CobolRecords.sortKey(from, "cp037"), ' in service
    assert "import com.gitgalaxy.modernized.entity.vsam.CobolRecords;" in service
    assert 'name = "FD_TCAT_TYPE", columnDefinition = "varchar(2) COLLATE \\"C\\""' in key  # a group key's text part


def test_mysql_keys_are_binary_so_case_variants_do_not_collide(scanned, tmp_path):
    entity, *_ = _generated(scanned, tmp_path, engine="mysql")
    assert 'columnDefinition = "varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"' in entity


def test_binary_collates_bytewise_but_orders_by_the_key(scanned, tmp_path):
    entity, repo, service, _ = _generated(scanned, tmp_path, {"key_collation": "binary"})
    assert 'COLLATE \\"C\\"' in entity and "acctIdSort" not in entity
    assert "findByAcctIdGreaterThanEqualOrderByAcctIdAsc(String acctId, Pageable page);" in repo
    assert "findByAcctIdGreaterThanEqualOrderByAcctIdAsc(from, " in service


def test_database_collation_is_the_output_of_before(scanned, tmp_path):
    entity, repo, service, key = _generated(scanned, tmp_path, {"key_collation": "database"})
    assert '    @Id\n    @Column(name = "ACCT_ID", length = 8)\n    private String acctId;' in entity
    assert "COLLATE" not in entity + key and "Sort" not in entity + repo + service


def test_the_porting_rules_order_keys_by_code_page_bytes():
    assert any("#3822" in rule and "CobolRecords.sortKey" in rule for rule in PORTING_RULES)


@pytest.mark.skipif(not (_JDK / "javac").exists(), reason="no JDK 17")
@pytest.mark.parametrize("code_page", ["cp037", "cp273", "cp500"])  # Python has no cp277/278 codec
def test_the_sort_key_orders_as_the_code_page_bytes(tmp_path, code_page):
    runtime = COBOL_RECORDS_JAVA.replace("__PACKAGE__", "t").replace("__POSITIVE__", "").replace("__NEGATIVE__", "")
    (tmp_path / "CobolRecords.java").write_text(runtime, encoding="utf-8")
    keys = ", ".join('"' + k.replace("Ä", "\\u00c4") + '"' for k in KEYS)
    (tmp_path / "Runner.java").write_text(
        "package t;\nimport java.util.*;\npublic class Runner {\n    public static void main(String[] a) {\n"
        f"        List<String> keys = new ArrayList<>(List.of({keys}));\n"
        f'        keys.sort(Comparator.comparing(k -> CobolRecords.sortKey(k, "{code_page}")));\n'
        '        for (String k : keys) System.out.println(k.replace("\\u00c4", "AE"));\n    }\n}\n',
        encoding="utf-8",
    )
    subprocess.run([str(_JDK / "javac"), "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))], check=True)
    out = subprocess.run([str(_JDK / "java"), "-cp", str(tmp_path), "t.Runner"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    want = [k.replace("Ä", "AE") for k in sorted(KEYS, key=lambda k: k.encode(code_page))]
    assert out.stdout.split("\n")[:-1] == want
    if code_page == "cp037":  # the issue's order; CP037 puts Ä (0x63) before the letters
        assert want == ["AE001", "a001", "A 01", "A-01", "A001", "1001"]
