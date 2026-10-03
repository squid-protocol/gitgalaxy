"""#4060: the code page a port reads and writes record bytes in is a deployment fact, declared once
(data.record_charset), generated into CobolRecords.charset(), stated in every porting ticket and set by the
equivalence harness from the case's data encoding -- never a model's guess (one guessed IBM037 for Latin-1 data)."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java import cobol_to_java_port_tickets as pt
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge
from gitgalaxy.tools.cobol_to_java.java_target import ConfigError, JavaTarget, target_from_dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_java as ej  # noqa: E402


def test_the_record_charset_is_configured_and_validated():
    assert JavaTarget().data.record_charset == "latin-1"  # what an ASCII transfer gives, and what ran before
    assert target_from_dict({"data": {"record_charset": "cp037"}}).data.record_charset == "cp037"
    with pytest.raises(ConfigError, match="data.record_charset 'klingon'"):
        target_from_dict({"data": {"record_charset": "klingon"}})


def test_cobol_records_returns_the_declared_charset_unless_overridden():
    def source(charset: str) -> str:
        forge = RepositoryForge({}, {}, "com.acme", target=target_from_dict({"data": {"record_charset": charset}}))
        return forge.records_source(needed=True) or ""

    latin = source("latin-1")
    assert 'private static final String RECORD_CHARSET = "ISO-8859-1";' in latin
    assert 'Charset.forName(System.getProperty("gitgalaxy.data.charset", RECORD_CHARSET))' in latin
    assert 'RECORD_CHARSET = "IBM037";' in source("cp037")  # the JDK's name for the page
    assert 'RECORD_CHARSET = "UTF-8";' in source("utf-8")


def test_every_ticket_says_where_record_bytes_come_from():
    rule = next(r for r in pt.PORTING_RULES if "CobolRecords.charset()" in r)
    assert "never Charset.forName" in rule and "data.record_charset" in rule


def test_the_harness_sets_the_charset_from_the_case_data():
    assert ej.data_charset_arg({"name": "c"}) == "-Dgitgalaxy.data.charset=ISO-8859-1"
    assert ej.data_charset_arg({"name": "c", "data_encoding": "utf-8"}) == "-Dgitgalaxy.data.charset=UTF-8"
