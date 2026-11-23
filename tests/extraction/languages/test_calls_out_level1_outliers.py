"""
Regression tests for Level-1 call-graph extraction outlier fixes:
- PowerShell: cmdlets in pipelines/RHS/subexpressions/blocks, `$(...)` inside double-quoted
  strings & here-strings, `.NET` instance/static method calls, hashtable key exclusion,
  `enum` body and attribute blanking, and nested-function call blanking.
- Shell: `${VAR}` expansion exclusion, `$(...)` inside double-quoted strings, and `\\`
  line-continuation joining so continued arguments are not scanned as commands.
- Solidity: inline Yul `assembly { ... }` block blanking and call options (`target.call{value: v}(d)`).
- Haskell / generic non-qualified languages: `_drop_nested_unit_calls` blanks nested named
  functions even when the language does not populate `calls_out_qualifiers`.
"""

import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards.languages.powershell import (
    _PS_ATTR_BLOCK,
    _PS_CALLS_OUT,
    _PS_ENUM_BLOCK,
)
from gitgalaxy.standards.language_standards.languages.shell import _SH_LINE_CONT
from gitgalaxy.standards.language_standards.languages.solidity import (
    _SOLIDITY_ASSEMBLY_START,
    _SOLIDITY_CALL_OPTIONS,
)

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _calls(lang: str, code: str, fn_name: str) -> list[str]:
    units = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(u for u in units if u["name"].split(".")[-1].split("::")[-1] == fn_name)["calls_out_to"]


def test_powershell_cmdlets_methods_subexprs_and_non_calls():
    code = (
        "function Invoke-Demo {\n"
        "    [CmdletBinding()]\n"
        "    param(\n"
        "        [Parameter(Mandatory)]\n"
        "        [string]$Path\n"
        "    )\n"
        "    $choice = Read-Host 'Enter'\n"
        "    $env:PATH = \"$(Join-Path $env:USERPROFILE '.local');$env:PATH\"\n"
        '    Write-Host "Action: $($choice.ToLower())"\n'
        "    $sb = [System.Text.StringBuilder]::new()\n"
        "    $sb.AppendLine($Path) | Out-Null\n"
        "    if (Test-Path $Path) {\n"
        "        Get-ChildItem $Path | ForEach-Object { Write-Output $_ }\n"
        "    }\n"
        "    $layout = @{\n"
        "        height = 100\n"
        "        scaling_percent = [math]::Round(96.0, 0)\n"
        "    }\n"
        "    enum Status {\n"
        "        Pass\n"
        "        Fail\n"
        "    }\n"
        '    $cs = @"\n'
        "public struct POINT { int x; }\n"
        '"@\n'
        "    function Stop-Inner {\n"
        "        Stop-Process -Verbose\n"
        "    }\n"
        "}\n"
    )
    calls = set(_calls("powershell", code, "Invoke-Demo"))
    for expected in (
        "Read-Host",
        "Join-Path",
        "Write-Host",
        "ToLower",
        "new",
        "AppendLine",
        "Out-Null",
        "Test-Path",
        "Get-ChildItem",
        "ForEach-Object",
        "Write-Output",
        "Round",
    ):
        assert expected in calls, f"missing {expected} in {sorted(calls)}"
    for forbidden in ("height", "scaling_percent", "Pass", "Fail", "public", "Mandatory", "Stop-Process"):
        assert forbidden not in calls, f"unexpected FP {forbidden} in {sorted(calls)}"
    inner_calls = set(_calls("powershell", code, "Stop-Inner"))
    assert "Stop-Process" in inner_calls


def test_shell_expansions_quoted_subshells_and_line_continuations():
    code = (
        "run_check() {\n"
        '    local dir="${tempDir}/${driver}"\n'
        '    target="$(readlink "$1")"\n'
        "    val=\"$(printf '%s' \"$x\" | tr ',' '\\n' | sort)\"\n"
        '    atf_check -s not-exit:0 -e match:"Not a directory" \\\n'
        "        cp foo bar baz\n"
        "    echo ${FS}\n"
        "}\n"
    )
    calls = set(_calls("shell", code, "run_check"))
    for expected in ("readlink", "tr", "sort", "atf_check"):
        assert expected in calls, f"missing {expected} in {sorted(calls)}"
    for forbidden in ("tempDir", "driver", "FS", "cp", "dir"):
        assert forbidden not in calls, f"unexpected FP {forbidden} in {sorted(calls)}"


def test_solidity_assembly_blanking_and_call_options():
    code = (
        "contract Forwarder {\n"
        "    function _execute(address target, uint256 value, bytes memory data) internal {\n"
        "        (bool ok, ) = target.call{value: value}(data);\n"
        "        _verify(ok);\n"
        "        assembly {\n"
        "            let ok2 := staticcall(gas(), target, add(data, 0x20), mload(data), 0x00, 0x20)\n"
        "            if iszero(ok2) { invalid() }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    calls = set(_calls("solidity", code, "_execute"))
    assert "call" in calls
    assert "_verify" in calls
    for yul_op in ("staticcall", "gas", "add", "mload", "iszero", "invalid"):
        assert yul_op not in calls, f"Yul opcode {yul_op} leaked into Solidity calls: {sorted(calls)}"


def test_haskell_nested_where_calls_do_not_leak_to_outer():
    code = (
        "trimMath :: Text -> Text\n"
        "trimMath = stripBeginSpace\n"
        "  where\n"
        "    stripBeginSpace t =\n"
        "      case dropWhile isSpace t of\n"
        "        xs -> reverse xs\n"
    )
    outer = set(_calls("haskell", code, "trimMath"))
    inner = set(_calls("haskell", code, "stripBeginSpace"))
    assert "dropWhile" in inner
    assert "reverse" in inner
    assert "dropWhile" not in outer
    assert "reverse" not in outer


def test_level1_outlier_patterns_redos_immune():
    cases = [
        (_PS_CALLS_OUT, "$x." + "a" * 5000 + "[" + "b" * 5000),
        (_PS_ENUM_BLOCK, "enum Foo { " + "a " * 5000),
        (_PS_ATTR_BLOCK, "[Parameter(" + "a" * 5000),
        (_SH_LINE_CONT, "\\" + "\n" * 5000 + " " * 5000),
        (LANGUAGE_DEFINITIONS["shell"]["rules"]["calls_out"], "A=" * 2000 + "cmd "),
        (_SOLIDITY_CALL_OPTIONS, "foo{" + "a" * 5000),
        (_SOLIDITY_ASSEMBLY_START, "assembly " + "(" * 5000),
    ]
    for pat, payload in cases:
        assert_redos_immune(pat, payload)
