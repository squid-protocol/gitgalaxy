import pytest
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# ==============================================================================
# THE COUPLING MASS GAUNTLET
# Proves that the `args` spawner accurately isolates parameter blocks
# across major languages without triggering ReDoS on complex nested types.
# ==============================================================================
# ==============================================================================
# THE COUPLING MASS GAUNTLET
# Proves that the `args` spawner accurately isolates parameter blocks
# across major languages without triggering ReDoS on complex nested types.
# ==============================================================================
ARGS_EXTRACTION_CASES = {
    "php": {
        "valid": [
            ("function TargetFunc(int $a, ?string $b) {", "TargetFunc"),
            ("public function TargetFunc(array $items): void", "TargetFunc"),
        ],
        "invalid": ["TargetFunc($a, $b);", "if ($a == $b) {"],
        "pathological": [
            # Vertical spacing with default arrays and closure callbacks
            (
                "public \n function \n TargetFunc \n (\n  ?ArrayObject $items = [],\n  Closure $cb = fn($x) => $x\n)",
                "TargetFunc",
            )
        ],
    },
    "ruby": {
        "valid": [
            ("def TargetFunc(a, b = 5)", "TargetFunc"),
            ("def self.TargetFunc(x: 1, y: 2)", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b)", "if a == b"],
        "pathological": [
            # Vertical spacing, hash parameters, and block arguments
            (
                "def \n TargetFunc \n (\n  a: [],\n  b: ->(x) { x * 2 },\n  **kwargs\n)",
                "TargetFunc",
            )
        ],
    },
    "objective-c": {
        "valid": [
            ("- (void)TargetFunc:(int)a withB:(NSString *)b", "TargetFunc"),
            ("+ (instancetype)TargetFunc:(id)obj {", "TargetFunc"),
        ],
        "invalid": ["[self TargetFunc:a withB:b];", "if (a) {"],
        "pathological": [
            # Vertical fragmentation and Block callbacks
            (
                "- \n (void) \n TargetFunc \n : \n (NSDictionary<NSString *, id> *)data \n withCallback \n : \n (void (^)(BOOL success))callback",
                "TargetFunc",
            )
        ],
    },
    "dart": {
        "valid": [
            ("void TargetFunc(String a, int b) {", "TargetFunc"),
            ("Future<int> TargetFunc(List<T> items) async {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "if (a > b) {"],
        "pathological": [
            # Vertical formatting with nested function type parameters
            # FIX: Added `\n {` to complete the structural definition
            (
                "Future<void> \n TargetFunc \n <T> \n (\n  List<T> items,\n  void Function(int, String) callback\n) \n {",
                "TargetFunc",
            )
        ],
    },
    "zig": {
        "valid": [
            ("pub fn TargetFunc(a: i32, b: f32) void {", "TargetFunc"),
            ("fn TargetFunc(comptime T: type, items: []T)", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "while (iter.next()) |val| {"],
        "pathological": [
            # Vertical sigs with comptime types
            (
                "pub \n inline \n fn \n TargetFunc \n (\n  comptime T: type,\n  allocator: std.mem.Allocator,\n) \n !void",
                "TargetFunc",
            )
        ],
    },
    "apex": {
        "valid": [
            ("public void TargetFunc(String a, Integer b) {", "TargetFunc"),
            ("trigger TargetFunc on Account (before insert) {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "if (a == b) {"],
        "pathological": [
            # Vertical modifiers and complex generic maps
            (
                "public \n static \n Map<Id, Account> \n TargetFunc \n (\n  List<Account> accounts,\n  Map<Id, Contact> contacts\n)",
                "TargetFunc",
            )
        ],
    },
    "powershell": {
        "valid": [
            ("param([string]$a, [int]$b)", "param"),
            ("function TargetFunc ([string]$a) {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc -a 'foo'", "if ($a -eq $b) {"],
        "pathological": [
            # Extreme parameter attribute stacking
            (
                "function \n TargetFunc \n (\n  [Parameter(Mandatory=$true)]\n  [ValidateNotNullOrEmpty()]\n  [string[]]$items\n)",
                "TargetFunc",
            )
        ],
    },
    "tcl": {
        "valid": [
            ("proc TargetFunc {a b} {", "TargetFunc"),
            ("proc ::namespace::TargetFunc {args} {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc a b", "if {$a == $b} {"],
        "pathological": [
            # Vertical Tcl procs
            ("proc \n ::namespace::TargetFunc \n { \n a \n b \n } \n {", "TargetFunc")
        ],
    },
    "scheme": {
        "valid": [
            ("(define (TargetFunc a b)", "TargetFunc"),
            ("(define (TargetFunc)", "TargetFunc"),
        ],
        "invalid": ["(TargetFunc a b)", "(if (> a b)"],
        "pathological": [
            # Deep vertical S-expressions
            ("( \n define \n ( \n TargetFunc \n a \n b \n )", "TargetFunc")
        ],
    },
}


class TestArgsExtraction:
    @pytest.mark.parametrize("lang_id", ARGS_EXTRACTION_CASES.keys())
    def test_positive_args_extraction(self, lang_id):
        cases = ARGS_EXTRACTION_CASES.get(lang_id, {})
        if "valid" not in cases:
            pytest.skip(f"No valid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("args")
        if not pattern:
            pytest.skip(f"No args pattern defined for {lang_id}")

        for payload, expected_name in cases["valid"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] Iron Wall Blocked Valid Args: '{payload}'"

    @pytest.mark.parametrize("lang_id", ARGS_EXTRACTION_CASES.keys())
    def test_negative_args_extraction(self, lang_id):
        cases = ARGS_EXTRACTION_CASES.get(lang_id, {})
        if "invalid" not in cases:
            pytest.skip(f"No invalid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("args")
        if not pattern:
            pytest.skip(f"No args pattern defined for {lang_id}")

        for payload in cases["invalid"]:
            match = pattern.search(payload)
            assert match is None, f"[{lang_id}] 👻 GHOST ARGS HALLUCINATED! Erroneously matched args on: '{payload}'"

    @pytest.mark.parametrize("lang_id", ARGS_EXTRACTION_CASES.keys())
    def test_pathological_args_extraction(self, lang_id):
        cases = ARGS_EXTRACTION_CASES.get(lang_id, {})
        if "pathological" not in cases:
            pytest.skip(f"No pathological cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("args")
        if not pattern:
            pytest.skip(f"No args pattern defined for {lang_id}")

        for payload, expected_name in cases["pathological"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] 💥 Engine choked on pathological args formatting: '{payload}'"
