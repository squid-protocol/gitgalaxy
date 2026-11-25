"""Tests for cross-function return types and chained receiver resolution."""

import pytest

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.return_types import extract_call_assigns, extract_expr_chain, extract_return_type
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _scan(lang: str, files: dict[str, str]) -> list[dict]:
    ext = StructuralExtractor(lang, LANGUAGE_DEFINITIONS)
    parsed = []
    for path, code in files.items():
        res = ext.splice(code, path)
        res["path"] = path
        res["lang_id"] = lang
        parsed.append(res)
    return parsed


def _site(sites: list[dict], src_name: str, callee: str) -> dict:
    matches = [s for s in sites if s["src_name"] == src_name and s["callee"] == callee]
    assert len(matches) == 1, f"Expected 1 site for {src_name} -> {callee}, got {matches}"
    return matches[0]


def test_extract_return_type_languages():
    assert extract_return_type("python", "def get_store(x: int) -> Store:\n    pass\n") == "Store"
    assert extract_return_type("python", "async def get_store() -> Optional[pkg.Store]:\n    pass\n") == "Store"
    assert extract_return_type("python", "def get_store() -> Store | None:\n    pass\n") == "Store"
    assert extract_return_type("python", "def items() -> list[Store]:\n    pass\n") is None
    assert extract_return_type("python", "def count() -> int:\n    pass\n") is None

    assert extract_return_type("typescript", "function getStore(): Store {\n}\n") == "Store"
    assert extract_return_type("typescript", "function items(): Promise<Store> {\n}\n") is None

    assert extract_return_type("go", "func GetStore() *pkg.Store {\n}\n") == "Store"
    assert extract_return_type("go", "func GetStore() (*Store, error) {\n}\n") == "Store"
    assert extract_return_type("go", "func Count() int {\n}\n") is None

    assert extract_return_type("rust", "pub fn get_store() -> Result<Store, Err> {\n}\n") == "Store"
    assert extract_return_type("rust", "fn clone_self(&self) -> Self {\n}\n", parent_class="Store") == "Store"

    assert extract_return_type("java", "public static Store getStore() {\n}\n") == "Store"
    assert extract_return_type("csharp", "public async Store GetStore() {\n}\n") == "Store"
    assert extract_return_type("kotlin", "fun getStore(): Store? {\n}\n") == "Store"
    assert extract_return_type("cpp", "const Store& getStore() {\n}\n") == "Store"
    assert extract_return_type("cpp", "auto getStore() -> std::unique_ptr<Store> {\n}\n") == "Store"


def test_extract_expr_chain():
    s1 = "get_store().save(x)"
    assert extract_expr_chain(s1, s1.index("save"), (".",)) == "get_store()"

    s2 = "self.factory.get_store(1, 2).save()"
    assert extract_expr_chain(s2, s2.index("save"), (".",)) == "self.factory.get_store()"

    s3 = "a().b().c()"
    assert extract_expr_chain(s3, s3.index("c("), (".",)) == "a().b()"

    s4 = "xs[0].save()"
    assert extract_expr_chain(s4, s4.index("save"), (".",)) is None


def test_python_factory_assignment_and_chained_receiver():
    files = {
        "models.py": (
            "class Store:\n    def save(self):\n        pass\n\nclass Other:\n    def save(self):\n        pass\n"
        ),
        "factory.py": ("from models import Store\n\ndef get_store() -> Store:\n    return Store()\n"),
        "app.py": (
            "from factory import get_store\n\n"
            "def run_var():\n"
            "    s = get_store()\n"
            "    s.save()\n\n"
            "def run_chain():\n"
            "    get_store().save()\n"
        ),
    }
    parsed = _scan("python", files)
    deps = [
        {"src": "factory.py", "dst": "models.py"},
        {"src": "app.py", "dst": "factory.py"},
    ]
    sites, _ = resolve_calls(parsed, deps)

    # 1. Variable assigned from factory call: s = get_store(); s.save()
    var_site = _site(sites, "run_var", "save")
    assert var_site["step"] == "typed"
    assert var_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert var_site["dst_name"] == "save"
    assert var_site["dst_line"] == 2

    # 2. Chained call: get_store().save()
    chain_site = _site(sites, "run_chain", "save")
    assert chain_site["step"] == "typed"
    assert chain_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert chain_site["dst_name"] == "save"
    assert chain_site["dst_line"] == 2

    # 3. calls_out_qualifiers still keeps "<expr>" for backward compatibility
    app_funcs = {f["name"]: f for f in next(p for p in parsed if p["path"] == "app.py")["functions"]}
    assert app_funcs["run_chain"]["calls_out_qualifiers"]["save"] == ["<expr>"]
    assert app_funcs["run_chain"]["calls_out_expr_chains"]["save"] == ["get_store()"]


def test_python_multi_hop_chained_receiver():
    files = {
        "store.py": (
            "class Store:\n"
            "    def save(self):\n"
            "        pass\n\n"
            "class Other:\n"
            "    def save(self):\n"
            "        pass\n\n"
            "class Factory:\n"
            "    def get_store(self) -> Store:\n"
            "        return Store()\n\n"
            "def make_factory() -> Factory:\n"
            "    return Factory()\n\n"
            "def run():\n"
            "    make_factory().get_store().save()\n"
        )
    }
    parsed = _scan("python", files)
    sites, _ = resolve_calls(parsed, [])
    site = _site(sites, "run", "save")
    assert site["step"] == "typed"
    assert site["resolution"] in CONFIDENT_RESOLUTIONS
    assert site["dst_name"] == "save"
    assert site["dst_line"] == 2


def test_unannotated_return_inference():
    assert extract_return_type("python", "def get_store():\n    return Store()\n") == "Store"
    assert (
        extract_return_type("python", "def get_store(ok):\n    if ok:\n        return Store()\n    return None\n")
        == "Store"
    )
    assert (
        extract_return_type("python", "def get_store(ok):\n    if ok:\n        return Store()\n    return Other()\n")
        is None
    )
    assert extract_return_type("python", "def get_store(x):\n    if x:\n        return x\n    return Store()\n") is None
    assert extract_return_type("javascript", "function getStore() {\n    return new Store();\n}\n") == "Store"

    files = {
        "store.py": (
            "class Store:\n"
            "    def save(self):\n"
            "        pass\n\n"
            "class Other:\n"
            "    def save(self):\n"
            "        pass\n\n"
            "def get_store():\n"
            "    return Store()\n\n"
            "def run():\n"
            "    s = get_store()\n"
            "    s.save()\n"
            "    get_store().save()\n"
        )
    }
    parsed = _scan("python", files)
    sites, _ = resolve_calls(parsed, [])
    site = _site(sites, "run", "save")
    assert site["step"] == "typed"
    assert site["resolution"] in CONFIDENT_RESOLUTIONS
    assert site["dst_name"] == "save"
    assert site["dst_line"] == 2


def test_typescript_factory_assignment_and_chain():
    files = {
        "store.ts": (
            "export class Store {\n"
            "  save(): void {}\n"
            "}\n"
            "export class Other {\n"
            "  save(): void {}\n"
            "}\n"
            "export function getStore(): Store {\n"
            "  return new Store();\n"
            "}\n"
            "export function run() {\n"
            "  const s = getStore();\n"
            "  s.save();\n"
            "}\n"
            "export function runChain() {\n"
            "  getStore().save();\n"
            "}\n"
        )
    }
    parsed = _scan("typescript", files)
    sites, _ = resolve_calls(parsed, [])

    var_site = _site(sites, "run", "save")
    assert var_site["step"] == "typed"
    assert var_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert var_site["dst_line"] == 2

    chain_site = _site(sites, "runChain", "save")
    assert chain_site["step"] == "typed"
    assert chain_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert chain_site["dst_line"] == 2


def test_go_and_rust_factory_assignments():
    go_files = {
        "store.go": (
            "package main\n"
            "type Store struct{}\n"
            "func (s *Store) Save() {}\n"
            "type Other struct{}\n"
            "func (o *Other) Save() {}\n"
            "func NewStore() *Store {\n"
            "  return &Store{}\n"
            "}\n"
            "func Run() {\n"
            "  s := NewStore()\n"
            "  s.Save()\n"
            "}\n"
        )
    }
    go_sites, _ = resolve_calls(_scan("go", go_files), [])
    go_site = _site(go_sites, "Run", "Save")
    assert go_site["step"] == "typed"
    assert go_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert go_site["dst_line"] == 3

    rs_files = {
        "lib.rs": (
            "struct Store;\n"
            "impl Store {\n"
            "    fn save(&self) {}\n"
            "}\n"
            "struct Other;\n"
            "impl Other {\n"
            "    fn save(&self) {}\n"
            "}\n"
            "fn make_store() -> Store {\n"
            "    Store\n"
            "}\n"
            "fn run() {\n"
            "    let s = make_store();\n"
            "    s.save();\n"
            "}\n"
        )
    }
    rs_sites, _ = resolve_calls(_scan("rust", rs_files), [])
    rs_site = _site(rs_sites, "run", "save")
    assert rs_site["step"] == "typed"
    assert rs_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert rs_site["dst_line"] == 3


def test_cpp_std_namespace_and_test_dir_isolation():
    files = {
        "include/fmt.h": "void move(int x) {}\n",
        "test/helper_test.cc": "void tm(int x) {}\n",
        "src/app.cpp": ('#include "include/fmt.h"\nvoid run(int x) {\n    std::move(x);\n    tm(x);\n}\n'),
    }
    sites, _ = resolve_calls(_scan("cpp", files), [{"src": "src/app.cpp", "dst": "include/fmt.h"}])
    move_site = _site(sites, "run", "move")
    assert move_site["step"] == "none"
    assert move_site["resolution"] == "external"

    tm_site = _site(sites, "run", "tm")
    assert tm_site["step"] == "unseen"
    assert tm_site["resolution"] not in CONFIDENT_RESOLUTIONS


def test_java_builder_chain_disambiguated_by_file_scope():
    files = {
        "FunSpec.java": (
            "public class FunSpec {\n"
            "  public static class Builder {\n"
            "    public Builder addCode(String s) { return this; }\n"
            "    public FunSpec build() { return new FunSpec(); }\n"
            "  }\n"
            "  public static Builder builder(String name) { return new Builder(); }\n"
            "}\n"
        ),
        "TypeSpec.java": (
            "public class TypeSpec {\n"
            "  public static class Builder {\n"
            "    public Builder addCode(String s) { return this; }\n"
            "    public TypeSpec build() { return new TypeSpec(); }\n"
            "  }\n"
            "  public static Builder builder(String name) { return new Builder(); }\n"
            "}\n"
        ),
        "App.java": (
            'public class App {\n  public void run() {\n    FunSpec.builder("f").addCode("x").build();\n  }\n}\n'
        ),
    }
    deps = [{"src": "App.java", "dst": "FunSpec.java"}, {"src": "App.java", "dst": "TypeSpec.java"}]
    sites, _ = resolve_calls(_scan("java", files), deps)
    add_site = _site(sites, "run", "addCode")
    assert add_site["step"] == "typed"
    assert add_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert add_site["dst_path"] == "FunSpec.java"

    build_site = _site(sites, "run", "build")
    assert build_site["step"] == "typed"
    assert build_site["resolution"] in CONFIDENT_RESOLUTIONS
    assert build_site["dst_path"] == "FunSpec.java"


# #8916: a name in another script, or a decomposed one, must read as its ASCII twin does. `\w` has no combining marks
# (Mn / Mc) or ZWJ, so a Devanagari / Tamil / NFD suffix cut the name and the header or assignment never matched.
_SUFFIXES = {
    "ascii": "",
    "nfd": "e" + chr(0x301),
    "devanagari": "".join(map(chr, (0x928, 0x93E, 0x92E))),
    "devanagari_zwj": "".join(map(chr, (0x915, 0x94D, 0x200D, 0x937))),
    "tamil": "".join(map(chr, (0xBAA, 0xBC6, 0xBAF, 0xBB0, 0xBCD))),
}
_HEADERS = {
    "python": "def get{n}() -> Store:\n    pass\n",
    "typescript": "function get{n}(): Store {{\n}}\n",
    "go": "func Get{n}() *Store {{\n}}\n",
    "rust": "pub fn get{n}() -> Store {{\n}}\n",
    "java": "public static Store get{n}() {{\n}}\n",
    "csharp": "public async Store Get{n}() {{\n}}\n",
    "kotlin": "fun get{n}(): Store {{\n}}\n",
    "cpp": "const Store& get{n}() {{\n}}\n",
}


@pytest.mark.parametrize("script", sorted(_SUFFIXES))
@pytest.mark.parametrize("lang", sorted(_HEADERS))
def test_extract_return_type_reads_a_non_ascii_name_like_its_twin(lang, script):
    assert extract_return_type(lang, _HEADERS[lang].format(n=_SUFFIXES[script])) == "Store"


@pytest.mark.parametrize("script", sorted(_SUFFIXES))
@pytest.mark.parametrize(
    "lang,tmpl",
    [
        ("typescript", "const s{n} = make{n}();"),
        ("go", "s{n} := Make{n}()"),
        ("rust", "let s{n} = make{n}();"),
        ("cpp", "auto s{n} = make{n}();"),
    ],
)
def test_extract_call_assigns_reads_a_non_ascii_name_like_its_twin(lang, tmpl, script):
    n = _SUFFIXES[script]
    got = extract_call_assigns(lang, tmpl.format(n=n), {"s" + n})
    assert got == {"s" + n: "make" + n if lang != "go" else "Make" + n}


@pytest.mark.parametrize("script", sorted(_SUFFIXES))
def test_call_resolver_declaration_regexes_read_a_non_ascii_name_like_its_twin(script):
    from gitgalaxy.core import call_resolver as cr

    n = _SUFFIXES[script]
    assert cr._CLASS_DECL.search(f"class Impl{n} : Base {{").group(1) == "Impl" + n
    assert cr._PARENT_NAME.fullmatch(f"pkg{n}.Base{n}")
    m = cr._ALIAS_DECL.search(f"using Base{n} = Priv{n}<Pub>;")
    assert m and m.group(3) == "Base" + n and m.group(4) == "Priv" + n


def test_qualified_nested_classes_and_chained_call_assigns():
    # Return types preserve `Outer.Inner` for nested classes
    assert extract_return_type("kotlin", "fun builder(): TypeSpec.Builder {\n}\n") == "TypeSpec.Builder"
    assert extract_return_type("kotlin", "fun KClass<*>.toTypeSpec(): TypeSpec {\n}\n") == "TypeSpec"
    assert extract_return_type("java", "public static TypeSpec.Builder builder() {\n}\n") == "TypeSpec.Builder"

    # Safe-call chains (`?.`) and 5-6 hop chains
    s_safe = "a?.b()?.c()?.d()?.e()"
    assert extract_expr_chain(s_safe, s_safe.index("e("), (".",)) == "a.b().c().d()"

    # Chained RHS call-assigns + rejection of trailing property/index
    kt_code = (
        "val b = TypeSpec.builder(name)\n"
        "val spec = AnnotationSpec.builder(x).addMember(y).build()\n"
        "val prop = getSpec().name\n"
        "val first = getSpecs()[0]\n"
    )
    assert extract_call_assigns("kotlin", kt_code, {"b", "spec", "prop", "first"}) == {
        "b": "TypeSpec.builder",
        "spec": "AnnotationSpec.builder().addMember().build",
    }


def test_kotlin_nested_builder_class_properties_and_lambda_it():
    files = {
        "CodeBlock.kt": (
            "class CodeBlock {\n"
            "  fun isEmpty(): Boolean = true\n"
            "  class Builder {\n"
            "    fun addStatement(s: String): Builder = this\n"
            "    fun build(): CodeBlock = CodeBlock()\n"
            "  }\n"
            "  companion object {\n"
            "    fun builder(): CodeBlock.Builder = Builder()\n"
            "  }\n"
            "}\n"
        ),
        "AnnotationSpec.kt": (
            "class AnnotationSpec {\n"
            "  fun toBuilder(): AnnotationSpec.Builder = Builder()\n"
            "  class Builder {\n"
            "    fun useSiteTarget(t: String): AnnotationSpec.Builder = this\n"
            "    fun build(): AnnotationSpec = AnnotationSpec()\n"
            "  }\n"
            "}\n"
        ),
        "FunSpec.kt": (
            "class FunSpec(val body: CodeBlock, val annotations: List<AnnotationSpec>) {\n"
            "  fun check() {\n"
            "    body.isEmpty()\n"
            '    annotations.map { it.toBuilder().useSiteTarget("get").build() }\n'
            "  }\n"
            "  class Builder {\n"
            "    internal val body = CodeBlock.builder()\n"
            "    fun addCode(s: String): Builder {\n"
            "      body.addStatement(s)\n"
            "      return this\n"
            "    }\n"
            "  }\n"
            "}\n"
        ),
        "OtherSpec.kt": (
            "class OtherSpec {\n"
            "  class Builder {\n"
            "    fun addStatement(s: String): Builder = this\n"
            "    fun useSiteTarget(t: String): Builder = this\n"
            "    fun build(): OtherSpec = OtherSpec()\n"
            "  }\n"
            "}\n"
        ),
    }
    deps = [
        {"src": "FunSpec.kt", "dst": "CodeBlock.kt"},
        {"src": "FunSpec.kt", "dst": "AnnotationSpec.kt"},
        {"src": "FunSpec.kt", "dst": "OtherSpec.kt"},
    ]
    sites, _ = resolve_calls(_scan("kotlin", files), deps)

    # 1. FunSpec.Builder.addCode -> body.addStatement resolves to CodeBlock.Builder (not OtherSpec.Builder)
    add_stmt = _site(sites, "addCode", "addStatement")
    assert add_stmt["step"] == "typed"
    assert add_stmt["dst_path"] == "CodeBlock.kt"

    # 2. FunSpec.check -> body.isEmpty resolves to CodeBlock (not leaked from Builder's body)
    is_empty = _site(sites, "check", "isEmpty")
    assert is_empty["step"] == "typed"
    assert is_empty["dst_path"] == "CodeBlock.kt"

    # 3. FunSpec.check -> annotations.map { it.toBuilder().useSiteTarget(...).build() }
    use_site = _site(sites, "check", "useSiteTarget")
    assert use_site["step"] == "typed"
    assert use_site["dst_path"] == "AnnotationSpec.kt"

    build_site = _site(sites, "check", "build")
    assert build_site["step"] == "typed"
    assert build_site["dst_path"] == "AnnotationSpec.kt"


def test_kotlin_lambda_it_conflict_guard():
    from gitgalaxy.core.overload_types import receiver_types

    code = "fun mixed(xs: List<Alpha>, ys: List<Beta>) {\n  xs.map { it.run() }\n  ys.map { it.run() }\n}\n"
    # Conflicting `it` types in the same function must NOT guess either one
    got = receiver_types(code, {"it"}, None, "kotlin")
    assert not got.get("it")


def test_c_object_like_statement_macro_expansion():
    files = {
        "fs.c": (
            "void uv__work_submit(void) {}\n"
            "void uv__strdup(void) {}\n"
            "#define POST do { uv__work_submit(); } while (0)\n"
            "#define PATH do { uv__strdup(); } while (0)\n"
            "void uv_fs_access(void) {\n"
            "    PATH;\n"
            "    POST;\n"
            "}\n"
        )
    }
    sites, _ = resolve_calls(_scan("c", files), [])
    submit = _site(sites, "uv_fs_access", "uv__work_submit")
    assert submit["resolution"] in CONFIDENT_RESOLUTIONS
    assert submit["dst_line"] == 1
    strdup = _site(sites, "uv_fs_access", "uv__strdup")
    assert strdup["resolution"] in CONFIDENT_RESOLUTIONS
    assert strdup["dst_line"] == 2


def test_external_stdlib_receiver_guards_cpp_rust_java_go():
    # C++: `std::string_view` must NOT link to a repo `string_view::data()`
    cpp_files = {
        "core.h": (
            "class basic_string_view {\n"
            "public:\n"
            "    const char* data() { return 0; }\n"
            "};\n"
            "using string_view = basic_string_view;\n"
            "void use_std(std::string_view sv) {\n"
            "    sv.data();\n"
            "}\n"
        )
    }
    cpp_sites, _ = resolve_calls(_scan("cpp", cpp_files), [])
    sv_data = _site(cpp_sites, "use_std", "data")
    assert sv_data["step"] == "none"

    # Rust: foreign trait bound `de::Visitor` must NOT link to a repo struct's `visit_i64`
    rs_files = {
        "lib.rs": (
            "struct NumberVisitor;\n"
            "impl NumberVisitor {\n"
            "    fn visit_i64(&self, v: i64) {}\n"
            "}\n"
            "fn parse<V>(visitor: V) where V: de::Visitor {\n"
            "    visitor.visit_i64(1);\n"
            "}\n"
        )
    }
    rs_sites, _ = resolve_calls(_scan("rust", rs_files), [])
    visit = _site(rs_sites, "parse", "visit_i64")
    assert visit["step"] == "none"

    # Java: external `Map` receiver must NOT link to a repo `Cache.get`
    java_files = {
        "App.java": (
            "class Cache {\n"
            "    Object get(String k) { return null; }\n"
            "}\n"
            "class App {\n"
            "    Object lookup(Map m, String k) { return m.get(k); }\n"
            "}\n"
        )
    }
    java_sites, _ = resolve_calls(_scan("java", java_files), [])
    get_site = _site(java_sites, "lookup", "get")
    assert get_site["step"] == "none"


def test_cpp_qualified_templated_base_class_inheritance_and_kotlin_apply_blocks():
    # C++: `class basic_memory_buffer : public detail::buffer<T>` inherits `size()` from `buffer`
    cpp_files = {
        "buf.h": (
            "namespace detail {\n"
            "template <typename T>\n"
            "class buffer {\n"
            "public:\n"
            "    int size() const { return 0; }\n"
            "};\n"
            "}\n"
            "template <typename T>\n"
            "class basic_memory_buffer : public detail::buffer<T> {\n"
            "public:\n"
            "    void clear() {}\n"
            "};\n"
            "using memory_buffer = basic_memory_buffer<char>;\n"
            "class other_buf {\n"
            "public:\n"
            "    int size() const { return 1; }\n"
            "};\n"
            "int run() {\n"
            "    basic_memory_buffer<char> buf;\n"
            "    return buf.size();\n"
            "}\n"
        )
    }
    cpp_sites, _ = resolve_calls(_scan("cpp", cpp_files), [])
    sz = _site(cpp_sites, "run", "size")
    assert sz["step"] == "typed"
    assert sz["dst_line"] == 5

    # Kotlin: `.apply { addFunction(...) }` resolves bare calls against the builder receiver
    kt_files = {
        "FileSpec.kt": (
            "class FileSpec {\n"
            "    class Builder {\n"
            "        fun addFunction(name: String): Builder = this\n"
            "        fun build(): FileSpec = FileSpec()\n"
            "    }\n"
            "    companion object {\n"
            "        fun builder(pkg: String): FileSpec.Builder = Builder()\n"
            "    }\n"
            "}\n"
        ),
        "Other.kt": (
            "class Other {\n    class Builder {\n        fun addFunction(name: String): Builder = this\n    }\n}\n"
        ),
        "App.kt": (
            "fun makeFile(): FileSpec {\n"
            '    return FileSpec.builder("p").apply {\n'
            '        addFunction("foo")\n'
            "    }.build()\n"
            "}\n"
        ),
    }
    deps = [{"src": "App.kt", "dst": "FileSpec.kt"}, {"src": "App.kt", "dst": "Other.kt"}]
    kt_sites, _ = resolve_calls(_scan("kotlin", kt_files), deps)
    add_fn = _site(kt_sites, "makeFile", "addFunction")
    assert add_fn["step"] == "typed"
    assert add_fn["dst_path"] == "FileSpec.kt"
