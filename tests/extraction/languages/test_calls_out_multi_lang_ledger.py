"""
Regression tests for Swift, C#, Scala, and Solidity call-graph comparison ledger cells:
- Swift: dotted trailing-closure calls (`q.async { ... }`, `s.write { ... }`), generic calls,
  and switch `case` associated-value patterns (not calls, while `where` guards stay calls).
- C#: standalone attribute lines (`[Obsolete(...)]`, `[Experimental(...)]`) are not calls.
- Scala: `case Some(x) =>` patterns are not calls (while `if` guards stay calls); bracket
  generic calls (`ArrayBuffer[T](...)`) and parenthesis-less `new pkg.Type[T]` are calls.
- Solidity: primitive type casts (`address(x)`, `bytes32(x)`, `uint256(x)`), `type(T)`,
  `emit Event(...)`, and `revert Pkg.Err(...)` are not calls (while argument calls stay).
"""

import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_SCALA, CALLS_OUT_SWIFT
from gitgalaxy.standards.language_standards.languages.csharp import _CSHARP_ATTRIBUTE_LINE
from gitgalaxy.standards.language_standards.languages.scala import _SCALA_CASE_PATTERN
from gitgalaxy.standards.language_standards.languages.solidity import _SOLIDITY_EVENT_OR_ERROR
from gitgalaxy.standards.language_standards.languages.swift import _SWIFT_CASE_PATTERN

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _calls(lang: str, code: str, fn_name: str) -> list[str]:
    units = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(u for u in units if u["name"].split(".")[-1].split("::")[-1] == fn_name)["calls_out_to"]


def test_swift_trailing_closures_and_switch_case_patterns():
    code = (
        "class Req {\n"
        "    func run(q: DispatchQueue, res: Result) -> UploadRequest.Uploadable {\n"
        "        if let existing = mutableState.interceptor {\n"
        "            mutableState.write { state in\n"
        "                q.async { self.finish() }\n"
        "            }\n"
        "        }\n"
        "        for req in map.requests {\n"
        "            use(req)\n"
        "        }\n"
        "        switch res.downloadable {\n"
        "        case .doNotRetryWithError(let err) where shouldLog(err):\n"
        "            log(err)\n"
        "        case let .resumeData(data):\n"
        "            save(data)\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    calls = _calls("swift", code, "run")
    assert {"write", "async", "finish", "use", "shouldLog", "log", "save"} <= set(calls)
    assert not (
        {"Uploadable", "interceptor", "requests", "downloadable", "doNotRetryWithError", "resumeData"} & set(calls)
    )


def test_csharp_attribute_lines_are_not_calls():
    code = (
        "class C {\n"
        '    [Obsolete("legacy", true)]\n'
        "    [Experimental(RoslynExperiments.Preview)]\n"
        "    internal bool Check(int[] arr) {\n"
        "        var v = arr[GetIndex()];\n"
        "        return Validate(v);\n"
        "    }\n"
        "}\n"
    )
    calls = _calls("csharp", code, "Check")
    assert "Obsolete" not in calls
    assert "Experimental" not in calls
    assert "GetIndex" in calls
    assert "Validate" in calls


def test_scala_case_patterns_generic_calls_and_new_without_parens():
    code = (
        "object O {\n"
        "  def handle(opt: Option[Int]): Unit = {\n"
        "    val buf = new mutable.ArrayBuffer[String]\n"
        "    val items = ArrayBuffer[Int](1, 2)\n"
        "    opt match {\n"
        "      case Some(v) if isValid(v) => process(v)\n"
        "      case Left(err) => fail(err)\n"
        "      case None => ()\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    calls = _calls("scala", code, "handle")
    assert {"ArrayBuffer", "isValid", "process", "fail"} <= set(calls)
    assert "Some" not in calls
    assert "Left" not in calls


def test_solidity_primitive_casts_emit_and_revert_are_not_calls():
    code = (
        "contract Access {\n"
        "    function grant(bytes32 role, address account) external {\n"
        "        bytes32 key = bytes32(uint256(uint160(account)));\n"
        "        bytes4 iface = type(IAccess).interfaceId;\n"
        "        if (!hasRole(key, account)) {\n"
        "            emit RoleGranted(role, account, _msgSender());\n"
        "        } else {\n"
        "            revert Errors.AlreadyGranted(getReason());\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    calls = _calls("solidity", code, "grant")
    assert {"hasRole", "_msgSender", "getReason"} <= set(calls)
    assert not (
        {"bytes32", "uint256", "uint160", "type", "emit", "RoleGranted", "revert", "AlreadyGranted"} & set(calls)
    )


def test_multi_lang_ledger_patterns_are_redos_immune():
    assert_redos_immune(CALLS_OUT_SWIFT, "a." + "f<" * 40 + "a" * 40, timeout_sec=3.0)
    assert_redos_immune(CALLS_OUT_SCALA, "new " + "a." * 20 + "T[" + "a" * 80, timeout_sec=3.0)
    assert_redos_immune(_SWIFT_CASE_PATTERN, "case " + "a" * 300, timeout_sec=3.0)
    assert_redos_immune(_CSHARP_ATTRIBUTE_LINE, "[" + "(" * 50 + "a" * 50, timeout_sec=3.0)
    assert_redos_immune(_SCALA_CASE_PATTERN, "case " + "a" * 250, timeout_sec=3.0)
    assert_redos_immune(_SOLIDITY_EVENT_OR_ERROR, "emit " + "a." * 20 + "E", timeout_sec=3.0)
