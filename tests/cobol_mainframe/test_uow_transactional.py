import pytest
import shutil
from pathlib import Path
from unittest.mock import patch

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as c2j


@pytest.fixture
def uow_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()

    (corpus / "UOWCICS.cbl").write_text("""\
       ID DIVISION.
       PROGRAM-ID. UOWCICS.
       PROCEDURE DIVISION.
       MAIN-SECTION.
           EXEC CICS SYNCPOINT END-EXEC.
           EXEC CICS SYNCPOINT ROLLBACK END-EXEC.
           EXEC CICS ABEND ABCODE('ABC1') END-EXEC.
           EXEC CICS HANDLE ABEND LABEL(ERR-PARA) END-EXEC.
           EXEC CICS HANDLE CONDITION NOTFND(ERR-PARA) END-EXEC.
           EXEC CICS READ DATASET('FILE1') INTO(WS-DATA) RIDFLD(WS-KEY) RESP(WS-RESP) END-EXEC.
           IF WS-RESP = DFHRESP(NORMAL)
               CONTINUE
           END-IF.
           EXEC CICS READ DATASET('FILE2') INTO(WS-DATA) RIDFLD(WS-KEY) RESP(WS-RESP) END-EXEC.
           EXEC CICS RETURN END-EXEC.
       ERR-PARA.
           CONTINUE.
""")

    (corpus / "UOWBATCH.cbl").write_text("""\
       ID DIVISION.
       PROGRAM-ID. UOWBATCH.
       PROCEDURE DIVISION.
       MAIN-SECTION.
           EXEC SQL COMMIT WORK END-EXEC.
           GOBACK.
""")

    (corpus / "UOWPLAIN.cbl").write_text("""\
       ID DIVISION.
       PROGRAM-ID. UOWPLAIN.
       PROCEDURE DIVISION.
       MAIN-SECTION.
           GOBACK.
""")

    (corpus / "CSD.csd").write_text("""\
DEFINE TRANSACTION(UOWC) PROGRAM(UOWCICS)
""")

    return corpus


def test_uow_transactional(uow_corpus: Path, tmp_path: Path):
    db_path = scan_to_db(uow_corpus, tmp_path / "scan")

    work = tmp_path / "work"
    shutil.copytree(uow_corpus, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db_path)]):
        refractor.main()

    (clean,) = tmp_path.glob("work_gitgalaxy_clean_*")

    # write config
    config = tmp_path / "target.yml"
    config.write_text("project:\n  package: com.test\n")

    with patch("sys.argv", ["cobol-to-java", str(clean), "--config", str(config)]):
        c2j.main()

    (java_dir,) = tmp_path.glob("work_gitgalaxy_java_spring_*")

    # Assert UowCicsService
    uow_cics = (java_dir / "src/main/java/com/test/service/UowcicsService.java").read_text()
    assert "@Transactional" in uow_cics
    assert "public void commitPointL5()" in uow_cics
    assert "public void rollbackL6()" in uow_cics
    assert "public void abendAbc1L7()" in uow_cics
    assert "public void onAbendL8(CicsAbendException e)" in uow_cics
    assert "public void onConditionNotfndL9(CicsConditionException e)" in uow_cics
    assert "READ at line 10 tests NORMAL" in uow_cics
    assert "TODO: the RESP of READ at line 14 (paragraph MAIN-SECTION) is never tested" in uow_cics

    # Assert UowBatchService
    uow_batch = (java_dir / "src/main/java/com/test/service/UowbatchService.java").read_text()
    assert "@Transactional" in uow_batch
    assert "public void commitPointL5()" in uow_batch

    # Assert UowPlainService has no @Transactional and byte-identical (no uow methods)
    uow_plain = (java_dir / "src/main/java/com/test/service/UowplainService.java").read_text()
    assert "@Transactional" not in uow_plain
    assert "commitPoint" not in uow_plain

    # Assert exceptions
    assert (java_dir / "src/main/java/com/test/exception/CicsAbendException.java").exists()
    assert (java_dir / "src/main/java/com/test/exception/CicsConditionException.java").exists()
    assert (java_dir / "src/main/java/com/test/exception/UnitOfWorkRollbackException.java").exists()

    # Assert advice
    assert (java_dir / "src/main/java/com/test/web/CicsExceptionAdvice.java").exists()


def test_uow_transactional_plain_classes(uow_corpus: Path, tmp_path: Path):
    db_path = scan_to_db(uow_corpus, tmp_path / "scan2")

    work = tmp_path / "work2"
    shutil.copytree(uow_corpus, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db_path)]):
        refractor.main()

    (clean,) = tmp_path.glob("work2_gitgalaxy_clean_*")

    config = tmp_path / "target2.yml"
    config.write_text("project:\n  package: com.test\njava:\n  data_classes: plain\n")

    with patch("sys.argv", ["cobol-to-java", str(clean), "--config", str(config)]):
        c2j.main()

    (java_dir,) = tmp_path.glob("work2_gitgalaxy_java_spring_*")
    uow_cics = (java_dir / "src/main/java/com/test/service/UowcicsService.java").read_text()
    assert "@Transactional" in uow_cics


def test_a_cics_program_without_handlers_needs_no_exception_classes(tmp_path: Path):
    """@Transactional for the CICS task, but nothing imports or generates the exception
    package when no service throws or handles one (it would not compile otherwise)."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "PLAINCICS.cbl").write_text(
        "       ID DIVISION.\n       PROGRAM-ID. PLAINCICS.\n       PROCEDURE DIVISION.\n"
        "       MAIN-SECTION.\n           EXEC CICS RETURN END-EXEC.\n"
    )
    (corpus / "CSD.csd").write_text("DEFINE TRANSACTION(PLCI) PROGRAM(PLAINCICS)\n")
    db_path = scan_to_db(corpus, tmp_path / "scan")
    work = tmp_path / "work"
    shutil.copytree(corpus, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db_path)]):
        refractor.main()
    (clean,) = tmp_path.glob("work_gitgalaxy_clean_*")
    with patch("sys.argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        c2j.main()
    (java_dir,) = tmp_path.glob("work_gitgalaxy_java_spring_*")
    src = java_dir / "src/main/java/com/gitgalaxy/modernized"
    service = (src / "service/PlaincicsService.java").read_text()
    assert "@Transactional" in service and ".exception." not in service
    assert not (src / "exception").exists() and not (src / "web").exists()
