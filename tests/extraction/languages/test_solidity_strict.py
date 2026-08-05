"""solidity strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# SOLIDITY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #611)
# ==============================================================================
SOLIDITY_RULES = LANGUAGE_DEFINITIONS["solidity"]["rules"]

_SOLIDITY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { return; }", None),
    ("args", "function transfer(address to, uint256 amount) public {", None),
    ("structural_boundaries", "pragma solidity ^0.8.20;", None),
    ("func_start", "function transfer(address to) public {", None),
    ("class_start", "contract Token {", None),
    ("safety", 'require(x > 0, "must be positive");', None),
    ("safety_bypasses", "unchecked { x++; }", None),
    ("high_risk_execution", "selfdestruct(payable(owner));", None),
    ("api", "function foo() external {", None),
    ("state_mutation", "balances[msg.sender] = amount;", None),
    ("dead_code", "// function foo() public {", "// just a note"),
    ("doc", "/// @notice does a thing", None),
    ("test", "assertEq(a, b);", None),
    ("globals", "msg.sender", None),
    ("generics", "mapping(address => uint256) public balances;", None),
    ("scientific", "keccak256(abi.encodePacked(x));", None),
    ("reflection_metaprogramming", "fallback() external payable {}", None),
    ("import", 'import "./Token.sol";', None),
    ("ownership", "// SPDX-License-Identifier: MIT", None),
    ("planned_debt", "// TODO: optimize gas", None),
    ("fragile_debt", "// HACK: workaround for reentrancy", None),
    ("spec_exposure", "// ERC-20 compliant", None),
    ("events", "emit Transfer(from, to, amount);", None),
    ("pointers", "uint256[] memory arr;", None),
    ("memory_alloc", "new uint256[](10);", None),
    ("inline_asm", "assembly { let x := 1 }", None),
    ("telemetry", 'console.log("debug");', None),
    ("explicit_casts", "uint256(x);", None),
    ("panics_and_aborts", 'revert("error");', None),
    ("bitwise_ops", "a & b;", None),
    ("sync_locks", "function foo() public nonReentrant {", None),
    ("immutability_locks", "uint256 public constant MAX = 100;", None),
    ("cleanup", "delete balances[msg.sender];", None),
    ("encapsulation", "uint256 private secret;", None),
    ("serialization_parsing", "abi.encode(a, b);", None),
    ("regex_execution", "keccak256(abi.encodePacked(a, b));", None),
    ("time_date_logic", "uint256 x = block.timestamp + 1 days;", None),
    ("ipc_rpc_bridges", "target.delegatecall(data);", None),
    # --- Issue #1072: signature keys with zero _SIMPLE_CASES coverage ---
    ("hardcoded_secrets", 'secret = "0xABCDEF1234567890";', 'secretary = "Jane Doe";'),
]


@pytest.mark.parametrize("signature,positive,negative", _SOLIDITY_SIMPLE_CASES)
def test_solidity_signature_positive_and_negative(signature, positive, negative):
    pattern = SOLIDITY_RULES[signature]
    assert pattern is not None, f"solidity's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"solidity {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"solidity {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_solidity_args_redos_immunity():
    pattern = SOLIDITY_RULES["args"]
    poison = "function foo(" + "a, " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_solidity_func_start_name_capture_and_redos_immunity():
    pattern = SOLIDITY_RULES["func_start"]
    m = pattern.search("function transfer(address to) public {")
    assert m is not None
    assert m.group(1) == "transfer"

    m2 = pattern.search("modifier onlyOwner() {")
    assert m2 is not None
    assert m2.group(1) == "onlyOwner"

    poison = "function" + " " * 60000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_solidity_class_start_captures_name_with_inheritance():
    pattern = SOLIDITY_RULES["class_start"]
    m = pattern.search("contract Token is ERC20 {")
    assert m is not None
    assert m.group(1) == "Token"

    m2 = pattern.search("abstract contract Base {")
    assert m2 is not None
    assert m2.group(1) == "Base"

    m3 = pattern.search("interface IERC20 {")
    assert m3 is not None
    assert m3.group(1) == "IERC20"

    poison = "contract" + " " * 60000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_solidity_import_dependency_capture():
    dep_pattern = SOLIDITY_RULES["_dependency_capture"]
    m = dep_pattern.search('import "./interfaces/IToken.sol";')
    assert m is not None
    assert "./interfaces/IToken.sol" in m.groups()

    m2 = dep_pattern.search('import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";')
    assert m2 is not None
    assert "@openzeppelin/contracts/token/ERC20/IERC20.sol" in m2.groups()


def test_solidity_ipc_rpc_bridges_boundary_regressions():
    """
    Regression test for 2 real bugs found inside the shared \\b(...)\\b
    wrapper:
    - `.call{value:` ends on `:` (non-word), so the trailing \\b only fired
      when a word char immediately followed -- the idiomatic spaced form
      `target.call{value: amount}(...)` never matched at all.
    - `emit\\s+[A-Z]` only ever consumed a single uppercase letter (no `+`/
      `*`), so for any real multi-character event name the char right
      after the matched letter was itself a word char -- word-to-word is
      not a \\b transition, so the trailing \\b failed for every event name
      longer than one letter (effectively all of them).
    """
    pattern = SOLIDITY_RULES["ipc_rpc_bridges"]
    assert pattern.search('(bool ok, ) = target.call{value: amount}("");'), (
        "the idiomatic spaced .call{value: ...} form still didn't match"
    )
    assert pattern.search('target.call{value:amount}("");')
    assert pattern.search("emit Transfer(from, to, amount);"), "a real multi-character event name still didn't match"
    assert pattern.search("target.delegatecall(data);")
    assert pattern.search("target.staticcall(data);")
    assert pattern.search("selfdestruct(payable(owner));")


def test_solidity_generics_nested_mapping_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the nested
    alternative's `[^)]+` was unbounded. Against an adversarial run of
    `mapping(mapping(uint => ` with no closing paren, this scaled
    ~4x per doubling of n (0.18s/0.72s/2.86s/11.4s at n=5k/10k/20k/40k)
    before being bounded to `{1,200}`.
    """
    pattern = SOLIDITY_RULES["generics"]
    poison = "mapping(" + "mapping(uint => " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    # Correctness must survive the bound: real nested mappings still match.
    assert pattern.search("mapping(address => mapping(address => uint256)) public allowances;")
    assert pattern.search("mapping(address => uint256) public balances;")


def test_solidity_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 4 pairs the automated ambiguity sweep flagged for sharing
    literal keywords ("function"/"contract"): args<->dead_code,
    args<->func_start, class_start<->dead_code, dead_code<->func_start.
    dead_code's leading `//` comment-prefix requirement fully
    disambiguates it from func_start/class_start (which are line-anchored
    and never match a commented-out line), and args<->func_start both
    correctly firing on the same real `function foo(...) {` line is
    intentional overlap, not a false collision.
    """
    args = SOLIDITY_RULES["args"]
    dead_code = SOLIDITY_RULES["dead_code"]
    func_start = SOLIDITY_RULES["func_start"]
    class_start = SOLIDITY_RULES["class_start"]

    live_func = "function transfer(address to, uint256 amount) public {"
    assert args.search(live_func) and func_start.search(live_func), (
        "both args and func_start should legitimately match the same live function signature"
    )
    assert not dead_code.search(live_func), "dead_code incorrectly matched a live (non-commented) function"

    commented_func = "// function transfer(address to) public {"
    assert dead_code.search(commented_func)
    assert not func_start.search(commented_func), "func_start incorrectly matched a commented-out function"

    live_contract = "contract Token is ERC20 {"
    assert class_start.search(live_contract)
    assert not dead_code.search(live_contract)

    commented_contract = "// contract Token {"
    assert dead_code.search(commented_contract)
    assert not class_start.search(commented_contract), "class_start incorrectly matched a commented-out contract"


def test_solidity_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity check from the issue template: explicit_casts (value
    type casting) and pointers (memory/storage/calldata location
    keywords) don't share tokens and correctly co-fire independently on
    the same declaration when both are actually present.
    """
    casts = SOLIDITY_RULES["explicit_casts"]
    pointers = SOLIDITY_RULES["pointers"]
    assert casts.search("uint256(x);")
    assert not casts.search("uint256 memory x;"), "explicit_casts incorrectly matched a memory location keyword"
    assert pointers.search("uint256 memory arr;")
    assert not pointers.search("uint256(x);"), "pointers incorrectly matched an explicit cast"
