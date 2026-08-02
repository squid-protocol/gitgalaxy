import sys
from pathlib import Path

import pytest

# Insert the parent directory (tests/extraction) onto sys.path so we can import the harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _extraction_harness as harness

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# Get the solidity rules
solidity_rules = LANGUAGE_DEFINITIONS["solidity"]["rules"]

FUNC_START = solidity_rules["func_start"]
ARGS = solidity_rules["args"]
CLASS_START = solidity_rules["class_start"]
DEPENDENCY = solidity_rules["_dependency_capture"]

FUNCTION_CASES = {
    "valid": [
        ("function TargetFunc()", "TargetFunc"),
        ("modifier TargetFunc()", "TargetFunc"),
        ("function TargetFunc(uint256 x) public returns (uint256)", "TargetFunc"),
        ("function TargetFunc() external payable", "TargetFunc"),
        ("function TargetFunc(uint[] memory array)", "TargetFunc"),
        ("function TargetFunc(mapping(uint => string) storage m) internal", "TargetFunc"),
    ],
    "invalid": [
        "contract TargetFunc",
        "struct TargetFunc",
        "bool functionLike = true;",
        'string memory s = "function TargetFunc() {";',
    ],
    "pathological": [
        ("function \n TargetFunc \n (", "TargetFunc"),
        ("function TargetFunc() public payable override returns (uint)", "TargetFunc"),
        ("function\tTargetFunc\t()", "TargetFunc"),
    ],
}

ARGS_CASES = {
    "valid": [
        ("function TargetFunc(uint256 x)", None),
        ("modifier TargetFunc(uint256 y)", None),
        ("error TargetError(string msg)", None),
        ("event TargetEvent(address indexed sender)", None),
        ("constructor(string memory name)", None),
    ],
    "invalid": [
        "contract TargetFunc(uint)",
        "if (functionLike == true)",
    ],
    "pathological": [
        ("function TargetFunc(uint256[] memory a, mapping(uint => bool) storage b)", None),
        ("function TargetFunc(\n\tuint256 x,\n\tuint256 y\n)", None),
    ],
}

CLASS_CASES = {
    "valid": [
        ("contract TargetClass {", "TargetClass"),
        ("interface TargetClass {", "TargetClass"),
        ("library TargetClass {", "TargetClass"),
        ("abstract contract TargetClass {", "TargetClass"),
        ("contract TargetClass is Ownable {", "TargetClass"),
    ],
    "invalid": [
        "struct TargetClass {",
        "enum TargetClass {",
        "contractLike = true;",
    ],
    "pathological": [
        ("contract \n TargetClass \n is \n Base {", "TargetClass"),
        ("abstract \n contract \n TargetClass \n {", "TargetClass"),
        ("contract TargetClass is A, B, C {", "TargetClass"),
    ],
}

DEPENDENCY_CASES = {
    "valid": [
        ('import "token.sol";', "token.sol"),
        ('import "./token.sol";', "./token.sol"),
        ('import { ERC20 } from "token.sol";', "token.sol"),
        ('import {ERC20 as MyERC20} from "token.sol";', "token.sol"),
        ('import * as Token from "token.sol";', "token.sol"),
        ('import "token.sol" as Token;', "token.sol"),
    ],
    "invalid": [
        'string memory importPath = "token.sol";',
    ],
    "pathological": [
        ('import \n { \n ERC20 \n } \n from \n "token.sol";', "token.sol"),
        ('import \n * \n as \n Token \n from \n "token.sol";', "token.sol"),
    ],
}


@pytest.mark.parametrize("payload, expected_name", FUNCTION_CASES["valid"])
def test_valid_function_extraction(payload, expected_name):
    harness.assert_valid_match(FUNC_START, payload, expected_name, "solidity valid func")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_invalid_function_extraction(payload):
    harness.assert_invalid_no_match(FUNC_START, payload, "solidity invalid func")


@pytest.mark.parametrize("payload, expected_name", FUNCTION_CASES["pathological"])
def test_pathological_function_extraction(payload, expected_name):
    harness.assert_pathological_match(FUNC_START, payload, expected_name, "solidity pathological func")


@pytest.mark.parametrize("payload, expected_name", ARGS_CASES["valid"])
def test_valid_args_extraction(payload, expected_name):
    harness.assert_valid_match(ARGS, payload, expected_name, "solidity valid args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_invalid_args_extraction(payload):
    harness.assert_invalid_no_match(ARGS, payload, "solidity invalid args")


@pytest.mark.parametrize("payload, expected_name", ARGS_CASES["pathological"])
def test_pathological_args_extraction(payload, expected_name):
    harness.assert_pathological_match(ARGS, payload, expected_name, "solidity pathological args")


@pytest.mark.parametrize("payload, expected_name", CLASS_CASES["valid"])
def test_valid_class_extraction(payload, expected_name):
    harness.assert_valid_match(CLASS_START, payload, expected_name, "solidity valid class")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_invalid_class_extraction(payload):
    harness.assert_invalid_no_match(CLASS_START, payload, "solidity invalid class")


@pytest.mark.parametrize("payload, expected_name", CLASS_CASES["pathological"])
def test_pathological_class_extraction(payload, expected_name):
    harness.assert_pathological_match(CLASS_START, payload, expected_name, "solidity pathological class")


@pytest.mark.parametrize("payload, expected_path", DEPENDENCY_CASES["valid"])
def test_valid_dependency_extraction(payload, expected_path):
    harness.assert_valid_dependency_match(DEPENDENCY, payload, expected_path, "solidity valid dep")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_invalid_dependency_extraction(payload):
    harness.assert_invalid_no_match(DEPENDENCY, payload, "solidity invalid dep")


@pytest.mark.parametrize("payload, expected_path", DEPENDENCY_CASES["pathological"])
def test_pathological_dependency_extraction(payload, expected_path):
    harness.assert_pathological_dependency_match(DEPENDENCY, payload, expected_path, "solidity pathological dep")
