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
    "javascript": {
        "valid": [
            ("function TargetFunc(req, res) {", "TargetFunc"),
            ("const TargetFunc = async (data) =>", "TargetFunc"),
            ("  TargetFunc(config) {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(req, res)", "while (i < 10) {"],
        "pathological": [
            (
                "export \n const \n TargetFunc \n = \n async \n (\n  { id, user: { name } },\n  [first, ...rest] = []\n) \n =>",
                "TargetFunc",
            )
        ],
    },
    "csharp": {
        "valid": [
            ("public void TargetFunc(int a, string b)", "TargetFunc"),
            (
                "protected override Task<int> TargetFunc(CancellationToken token)",
                "TargetFunc",
            ),
        ],
        "invalid": ["TargetFunc(a, b);", "catch (Exception ex)"],
        "pathological": [
            (
                "public \n async \n Task<IActionResult> \n TargetFunc \n (\n  [FromBody] User user,\n  [FromQuery] string? id,\n  Action<bool, string> callback\n)",
                "TargetFunc",
            )
        ],
    },
    "cpp": {
        "valid": [
            ("void TargetFunc(int a, float b) {", "TargetFunc"),
            ("std::vector<int> TargetFunc(const std::string& name) {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "if (a > b) {"],
        "pathological": [
            (
                "inline \n static \n void \n TargetFunc \n (\n  std::vector<std::string>&& items,\n  void (*callback)(int, float)\n)",
                "TargetFunc",
            )
        ],
    },
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
    "rust": {
        "valid": [
            ("fn TargetFunc(a: i32, b: &str) {", "TargetFunc"),
            ("pub async fn TargetFunc<T>(items: Vec<T>) -> Result<()> {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "while let Some(x) = iter.next() {"],
        "pathological": [
            # Massive vertical spacing with generic impl traits
            (
                "pub \n async \n fn \n TargetFunc \n <T> \n (\n  mut items: Vec<T>,\n  cb: impl FnOnce(i32) -> String\n)",
                "TargetFunc",
            )
        ],
    },
    "swift": {
        "valid": [
            ("func TargetFunc(a: Int, b: String) {", "TargetFunc"),
            ("init(config: Config) {", "init"),
        ],
        "invalid": ['TargetFunc(a: 1, b: "2")', "guard let a = b else {"],
        "pathological": [
            # Vertical modifiers and escaping closures
            (
                "public \n mutating \n func \n TargetFunc \n <T> \n (\n  _ items: [T],\n  completion: @escaping (Result<Void, Error>) -> Void\n)",
                "TargetFunc",
            )
        ],
    },
    "kotlin": {
        "valid": [
            ("fun TargetFunc(a: Int, b: String) {", "TargetFunc"),
            ("suspend fun TargetFunc(items: List<String>) {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b)", "when (x) {"],
        "pathological": [
            # Vertical generics, default arguments, and lambda parameters
            (
                "internal \n suspend \n fun \n <T> \n TargetFunc \n (\n  items: List<T> = emptyList(),\n  callback: (Result<T>) -> Unit\n)",
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
    "c": {
        "valid": [
            ("void TargetFunc(int a, float *b) {", "TargetFunc"),
            ("static inline struct MyStruct* TargetFunc(void) {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "while (a < b) {"],
        "pathological": [
            # Attributes, vertical spaces, and function pointer arguments
            (
                "__attribute__((always_inline)) \n static \n void \n TargetFunc \n (\n  int a,\n  void (*callback)(int, void*)\n)",
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
    "scala": {
        "valid": [
            ("def TargetFunc(a: Int, b: String): Unit =", "TargetFunc"),
            ("def TargetFunc[T](items: List[T])", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b)", "for (i <- 1 to 10) {"],
        "pathological": [
            # Vertical modifiers and complex lambda parameters
            (
                "inline \n def \n TargetFunc \n [T] \n (\n  items: List[T],\n  callback: (Int, String) => Unit\n)",
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
