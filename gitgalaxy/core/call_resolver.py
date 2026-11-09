# ==============================================================================
# GitGalaxy Core: Function Call Resolver (#3328, Epic #3265 step 1)
#
# PURPOSE:
# `calls_out_to` is a list of bare callee NAMES per function (the contract is
# docs/calls_out_rule_contract.md, #3327). A graph built on bare names pools
# every `save()` / `get()` / `run()` together, so a function-level PageRank
# would rank the most common names rather than the most depended-on functions.
# This module sees the whole repository and links each (caller, callee name)
# to the definition it most plausibly means, and says how sure it is.
#
# THE LADDER (first match wins, per (caller function, callee name)):
#   1. `class`   -- a method of the caller's own class, in the caller's file.
#   2. `file`    -- a definition in the caller's own file.
#   2b. `typed`  -- `x.save()` where this function shows x's class
#                   (`x = Store()`, `def f(x: Store)`; the detector's
#                   calls_out_receiver_types): Store's method, or its
#                   nearest ancestor's. Python, Java, and (#8161) C++/Go/Rust/TS/JS.
#   3. `import`  -- a definition in a file the caller's file imports (the
#                   resolved import graph, NetworkRiskSensor.dependency_edges).
#   4. `unique`  -- the name is defined exactly once in the repository.
#                   In a package-scoped language (#3443) a BARE call must also
#                   see that one definition -- imported, or in its own
#                   directory where a directory is a namespace -- or it is
#                   `unseen`: ambiguous, the definition kept as the guess.
#   5. `nearest` -- several definitions; the nearest by path wins
#                   (core/path_proximity.py, the rule both import and
#                   mainframe resolution already use).
#   6. `tie`     -- several definitions that are equally near: no target.
#   7. `none`    -- defined nowhere in the repository: a built-in, the
#                   standard library or a third-party package. Not an edge.
#                   This is what removes most built-in noise without a
#                   per-language ignore list (#3327 decision 1).
# `resolution` groups the steps into the four confidence classes #3331
# reports: scoped (1-3), unique (4), ambiguous (`unseen`, 5-6), external (7).
#
# AMBIGUOUS CALLS ARE NOT EDGES (the decision #3328 asked for). A name with k
# definitions is exactly the collision this module exists to defeat. Splitting
# the weight 1/k across the candidates would still hand every `init()` in the
# repository a share of every `init()` call, and summed over many callers that
# rebuilds the "most common name wins" ranking. So an ambiguous site is a ROW
# (fcall_data keeps the nearest guess, and the candidate count, for whoever
# wants to measure it -- #3330 and #3332) but never a confident edge. That
# matches the import resolver, where "an import that is still ambiguous draws
# nothing" (invocation_resolver.py's header).
#
# THE FILE GRAPH (#3333). The resolved pairs become fcall_data rows, and the
# CONFIDENT cross-file ones (confident_file_pairs) also join the dependency
# graph as edge_kind 'fcall' wherever no import already joins the two files --
# so pagerank_score, popularity, internal_dependency_links and blast radius see
# a C file that calls into another translation unit, or a same-package Java
# class, without an import statement. Ambiguous pairs never do, except an `overload`
# row (#8161): its file is known, only which overload in it is not. #3332 measured
# confident links at ~96% precision against pyan3 before this was switched on.
# ==============================================================================
import posixpath
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

from gitgalaxy.core import overload_types
from gitgalaxy.core.java_arg_types import choose as java_choose

# #6266: the qualifier the detector gives a C++ constructor's bare initializer-list entry (`: Base(a)`, `: type(t)`)
INIT_LIST_QUALIFIER = "<init>"
# #8161 (X4): the `def_shape` of a C/C++ `static` free function (internal linkage: its own translation unit only)
C_STATIC_SHAPE = "static"
# #8161 (PR 5): the `def_shape` of a Kotlin extension function (`fun T.f()`: free, yet reached through a receiver) and a C# extension method
EXTENSION_SHAPE = "extension"

# #5699: languages where a bare `f(` inside a method `f` is never the method (it needs `self.f` /
# `this.f` / `$this->f`), so it may reach a free `f`. The detector keeps such a call for a unit
# inside a class and this resolver prunes it when only the unit itself resolves. Not here:
# Kotlin, Swift, Java, Ruby and C# (a member shadows the free function, so it is recursion).
# Go qualifies by its receiver (`func (s *S) f(`) rather than an enclosing class: the detector
# keeps the call only for a unit whose header names one. Objective-C (and ObjC++) reaches a method
# by message send, so a bare `f(` is always the C function.
BARE_CALL_SKIPS_METHODS = frozenset({"rust", "php", "typescript", "javascript", "python", "go", "objective-c"})

# Languages whose identifiers are case-insensitive, so `CALL Foo` reaches a
# `FOO` definition. The detector's calls_out ignore uses the same list for its
# keywords (detector.py, `_CALLS_OUT_GLOBAL_IGNORE`'s comment).
CASE_INSENSITIVE_CALL_LANGS = frozenset(
    {"abap", "ada", "batch", "cobol", "db2_sql", "fortran", "hlasm", "jcl", "livecode", "pli", "powershell", "rexx"}
)

# A call resolves only to a definition in a language it can link against. Most
# languages link only to themselves. These groups link across a real boundary:
# C/C++/Objective-C/yacc/assembly share one symbol table at link time,
# TypeScript calls JavaScript, the JVM languages call each other, and
# MicroPython is Python. Everything else is its own group.
_LINK_GROUPS = (
    frozenset({"c", "cpp", "objective-c", "yacc", "assembly"}),
    frozenset({"javascript", "typescript"}),
    frozenset({"java", "kotlin", "scala", "groovy"}),
    frozenset({"python", "embedded_python"}),
)
_GROUP_OF = {lang: min(group) for group in _LINK_GROUPS for lang in group}

RESOLUTION_OF_STEP = {
    "class": "scoped",
    "qualified": "scoped",
    "typed": "scoped",
    "file": "scoped",
    "import": "scoped",
    "unique": "unique",
    "unseen": "ambiguous",
    "nearest": "ambiguous",
    # #8161 (C5): C's nearest-path pick, which is confident there (see _ladder)
    "proximate": "unique",
    "tie": "ambiguous",
    "receiver": "ambiguous",
    "overload": "ambiguous",
    "none": "external",
}
CONFIDENT_RESOLUTIONS = frozenset({"scoped", "unique"})
# Best-first, for a callee reached through several qualifiers in one function:
# the ladder's own order, so `self.save()` beats `x.save()` in the same body.
_RANK = {
    step: i
    for i, step in enumerate(
        (
            "class",
            "qualified",
            "typed",
            "import",
            "file",
            "unique",
            "proximate",
            "unseen",
            "overload",
            "nearest",
            "receiver",
            "tie",
            "none",
        )
    )
}

# Receivers that mean "the caller's own object" / "its parent".
_SELF_RECEIVERS = frozenset({"self", "this", "Me", "me"})
_SUPER_RECEIVERS = frozenset({"super", "base", "parent"})


# #8161 (R1): languages whose calls name a PATH (`Type::f()`, `m::f()`, `Self::f()`, `super::f()`) with a
# different separator from a method call on a value (`x.f()`); the detector marks a path qualifier with a
# leading `::` (_SCOPE_QUALIFIER_PREFIX). A method's owner is the type its `impl` block names.
_PATH_QUALIFIED_LANGS = frozenset({"rust"})

# #3784: languages whose detector marks a `ns::f()` qualifier with a leading `::` (`::fmt`, `::` for a global
# `::f()`). A scope qualifier that is no known class is usually a NAMESPACE, which reaches free functions
# first: neither the import-stem step nor the untyped-receiver method ladder lands on a same-name member
# (`formatter<T>::format`) before a free `fmt::format` is tried.
_NAMESPACE_QUALIFIED_LANGS = frozenset({"cpp"})

# #3401: names a BARE call always means as the language's built-in, whatever
# the repository defines. Perl's named operators and built-in functions take
# precedence over a user `sub` of the same name -- `sub map` in Mojo's
# Promise.pm is reachable only as `$promise->map`, `&map` or
# `Mojo::Promise::map` -- so a bare `map(` is never an edge to it. Measured on
# language-crucible: bugzilla's and spamassassin's `map(` all resolved
# `unique` to Mojo's Promise.pm, inflating its Popularity Rank. A language
# where a user definition CAN shadow a built-in (Python, Lua, JS) is not listed.
_BARE_BUILTINS: dict[str, frozenset[str]] = {
    "perl": frozenset(
        {
            "abs",
            "binmode",
            "bless",
            "caller",
            "chdir",
            "chmod",
            "chomp",
            "chop",
            "chown",
            "chr",
            "close",
            "closedir",
            "cos",
            "defined",
            "delete",
            "die",
            "each",
            "eof",
            "eval",
            "exec",
            "exists",
            "exit",
            "exp",
            "fork",
            "grep",
            "hex",
            "index",
            "int",
            "join",
            "keys",
            "kill",
            "lc",
            "lcfirst",
            "length",
            "local",
            "localtime",
            "gmtime",
            "lock",
            "log",
            "map",
            "mkdir",
            "oct",
            "open",
            "opendir",
            "ord",
            "pack",
            "pop",
            "pos",
            "print",
            "printf",
            "push",
            "quotemeta",
            "rand",
            "read",
            "readdir",
            "ref",
            "rename",
            "require",
            "return",
            "reverse",
            "rindex",
            "rmdir",
            "scalar",
            "seek",
            "select",
            "shift",
            "sin",
            "sleep",
            "sort",
            "splice",
            "split",
            "sprintf",
            "sqrt",
            "srand",
            "substr",
            "system",
            "tell",
            "tie",
            "tied",
            "time",
            "uc",
            "ucfirst",
            "undef",
            "unlink",
            "unpack",
            "unshift",
            "untie",
            "values",
            "wait",
            "waitpid",
            "wantarray",
            "warn",
        }
    ),
    # #8161 (X2): Go's predeclared functions. A same-package free function of the name shadows one
    # (see _resolve_one); a method of the name never does (prometheus' `(*memChunk).len` drew 248
    # bare `len(` calls, its #1 hub).
    "go": frozenset(
        {
            *("append", "cap", "clear", "close", "complex", "copy", "delete", "imag", "len", "make", "max"),
            *("min", "new", "panic", "print", "println", "real", "recover"),
        }
    ),
}

# #3756: methods of the JS/TS built-in classes (String, Array, Map, Set, WeakMap,
# Promise, Object, Number, Date, RegExp, Function). `s.trim()` on a receiver the
# scan cannot type is far more often the built-in than a repo class's method of
# the same name: tsc resolved 52 confident zod links (`input.data.trim()`,
# `seen.has(x)`, `set.add(x)`) to lib.d.ts only. A repo method with one of these
# names reached through an UNTYPED non-`this` receiver is therefore the ambiguous
# `receiver` guess, never `file`/`import`. `typed`, `class`, `qualified` and
# alias/import-stem steps (a receiver the scan does know) are unaffected.
_BUILTIN_INSTANCE_METHODS_JS = frozenset(
    {
        # String
        "at",
        "charAt",
        "charCodeAt",
        "codePointAt",
        "concat",
        "endsWith",
        "includes",
        "indexOf",
        "lastIndexOf",
        "localeCompare",
        "match",
        "matchAll",
        "normalize",
        "padEnd",
        "padStart",
        "repeat",
        "replace",
        "replaceAll",
        "search",
        "slice",
        "split",
        "startsWith",
        "substring",
        "substr",
        "toLocaleLowerCase",
        "toLocaleUpperCase",
        "toLowerCase",
        "toUpperCase",
        "trim",
        "trimEnd",
        "trimStart",
        # Array (and TypedArray)
        "copyWithin",
        "entries",
        "every",
        "fill",
        "filter",
        "find",
        "findIndex",
        "findLast",
        "findLastIndex",
        "flat",
        "flatMap",
        "forEach",
        "join",
        "keys",
        "map",
        "pop",
        "push",
        "reduce",
        "reduceRight",
        "reverse",
        "shift",
        "some",
        "sort",
        "splice",
        "unshift",
        "values",
        "with",
        "toReversed",
        "toSorted",
        "toSpliced",
        # Map / Set / WeakMap / WeakSet
        "add",
        "clear",
        "delete",
        "get",
        "has",
        "set",
        # Promise
        "catch",
        "finally",
        "then",
        # Object / Number / Date / RegExp / Function / Symbol
        "hasOwnProperty",
        "isPrototypeOf",
        "propertyIsEnumerable",
        "toLocaleString",
        "toString",
        "valueOf",
        "toFixed",
        "toPrecision",
        "toExponential",
        "getTime",
        "toISOString",
        "toJSON",
        "exec",
        "test",
        "apply",
        "bind",
        "call",
    }
)
# #4991: methods of the java.lang / java.util built-ins (Object, String/CharSequence,
# the Collection / List / Set / Map / Queue / Deque / Iterator families, Optional,
# StringBuilder, Stream, boxed numbers, Class). `list.add(x)` / `map.get(k)` /
# `s.equals(o)` on a receiver the scan cannot type is the JDK method far more often
# than a repo class's method of the same name (scip-java resolves them to the JDK only).
_BUILTIN_INSTANCE_METHODS_JAVA = frozenset(
    {
        # Object / Class / Comparable / boxed numbers
        "equals",
        "hashCode",
        "toString",
        "getClass",
        "compareTo",
        "compare",
        "getName",
        "getSimpleName",
        "isInstance",
        "cast",
        "intValue",
        "longValue",
        "doubleValue",
        "floatValue",
        "shortValue",
        "byteValue",
        "booleanValue",
        # String / CharSequence / StringBuilder
        "length",
        "isEmpty",
        "charAt",
        "substring",
        "indexOf",
        "lastIndexOf",
        "contains",
        "startsWith",
        "endsWith",
        "equalsIgnoreCase",
        "toLowerCase",
        "toUpperCase",
        "trim",
        "strip",
        "split",
        "replace",
        "replaceAll",
        "matches",
        "concat",
        "append",
        "insert",
        "reverse",
        "toCharArray",
        "getBytes",
        "isBlank",
        "format",
        # Collection / List / Set / Queue / Deque
        "add",
        "addAll",
        "remove",
        "removeAll",
        "removeIf",
        "retainAll",
        "containsAll",
        "clear",
        "size",
        "get",
        "set",
        "iterator",
        "listIterator",
        "stream",
        "forEach",
        "toArray",
        "subList",
        "sort",
        "offer",
        "poll",
        "peek",
        "push",
        "pop",
        "addFirst",
        "addLast",
        "removeFirst",
        "removeLast",
        "getFirst",
        "getLast",
        # Map
        "put",
        "putAll",
        "putIfAbsent",
        "containsKey",
        "containsValue",
        "keySet",
        "values",
        "entrySet",
        "getOrDefault",
        "computeIfAbsent",
        "computeIfPresent",
        "compute",
        "merge",
        "getKey",
        "getValue",
        # Iterator / Optional / Stream
        "hasNext",
        "next",
        "isPresent",
        "ifPresent",
        "orElse",
        "orElseGet",
        "orElseThrow",
        "map",
        "flatMap",
        "filter",
        "collect",
        "anyMatch",
        "allMatch",
        "noneMatch",
        "findFirst",
        "findAny",
    }
)
# #4991: methods of the Python built-in types (str / bytes, list, dict, set, tuple, file objects).
# `d.get(k)` / `s.strip()` / `items.append(x)` on a receiver the scan cannot type is the built-in
# far more often than a repo class's method of the same name.
_BUILTIN_INSTANCE_METHODS_PYTHON = frozenset(
    {
        # str / bytes
        *("capitalize", "casefold", "center", "count", "decode", "encode", "endswith", "expandtabs"),
        *("find", "format", "format_map", "hex", "index", "isalnum", "isalpha", "isascii", "isdecimal"),
        *("isdigit", "isidentifier", "islower", "isnumeric", "isprintable", "isspace", "istitle"),
        *("isupper", "join", "ljust", "lower", "lstrip", "partition", "removeprefix", "removesuffix"),
        *("replace", "rfind", "rindex", "rjust", "rpartition", "rsplit", "rstrip", "split"),
        *("splitlines", "startswith", "strip", "swapcase", "title", "translate", "upper", "zfill"),
        # list / tuple / set / frozenset
        *("append", "clear", "copy", "extend", "insert", "pop", "remove", "reverse", "sort"),
        *("add", "difference", "difference_update", "discard", "intersection", "intersection_update"),
        *("isdisjoint", "issubset", "issuperset", "symmetric_difference", "union", "update"),
        # dict
        *("fromkeys", "get", "items", "keys", "popitem", "setdefault", "values"),
        # file objects
        *("close", "flush", "read", "readline", "readlines", "seek", "tell", "write", "writelines"),
    }
)
# #4991: methods of the Kotlin stdlib built-ins (String/CharSequence, Collection / List / Set / Map,
# Sequence / Iterator, the Any scope functions). `s.trim()` / `map.getOrPut(k)` / `list.add(x)` on a
# receiver the scan cannot type is the stdlib method far more often than a repo class's method of the
# same name. Names that are mostly free functions (`run`, `with`, `lazy`) are left out.
_BUILTIN_INSTANCE_METHODS_KOTLIN = frozenset(
    {
        # String / CharSequence
        *("trim", "trimStart", "trimEnd", "split", "substring", "startsWith", "endsWith", "contains"),
        *("replace", "lowercase", "uppercase", "toInt", "toLong", "toDouble", "toIntOrNull", "isEmpty"),
        *("isBlank", "isNotEmpty", "isNotBlank", "padStart", "padEnd", "removePrefix", "removeSuffix"),
        *("lines", "toCharArray", "toBoolean", "toFloat", "toLongOrNull", "toDoubleOrNull"),
        # Collection / List / Set / Map
        *("add", "addAll", "remove", "removeAll", "clear", "get", "set", "put", "putAll", "getOrPut"),
        *("getOrDefault", "getOrElse", "getOrNull", "containsKey", "containsValue", "keys", "values"),
        *("entries", "forEach", "forEachIndexed", "map", "mapNotNull", "mapIndexed", "flatMap", "filter"),
        *("filterNot", "filterIsInstance", "first", "firstOrNull", "last", "lastOrNull", "single"),
        *("any", "all", "none", "count", "fold", "reduce", "sorted", "sortedBy", "sortedWith", "groupBy"),
        *("associate", "associateBy", "zip", "take", "drop", "distinct", "joinToString", "toList"),
        *("toMutableList", "toSet", "toMutableSet", "toMap", "toTypedArray", "asSequence", "indexOf"),
        *("iterator", "plus", "minus", "withIndex", "hasNext", "next"),
        # Any / scope functions
        *("let", "also", "apply", "takeIf", "takeUnless", "equals", "hashCode", "toString", "compareTo"),
    }
)
# #4991: methods of the C# BCL built-ins (string, List<T> / IEnumerable<T> / LINQ, Dictionary, HashSet,
# StringBuilder, object). `s.Trim()` / `dict.TryGetValue(k, out v)` / `list.Add(x)` on a receiver the scan
# cannot type is the BCL method far more often than a repo class's method of the same name.
_BUILTIN_INSTANCE_METHODS_CSHARP = frozenset(
    {
        # string / StringBuilder
        *("Trim", "TrimStart", "TrimEnd", "Split", "Substring", "StartsWith", "EndsWith", "Contains"),
        *("Replace", "ToLower", "ToUpper", "ToLowerInvariant", "ToUpperInvariant", "IndexOf", "PadLeft"),
        *("PadRight", "Insert", "Append", "AppendLine", "AppendFormat", "IsNullOrEmpty", "CompareTo"),
        # List / Dictionary / HashSet / collections
        *("Add", "AddRange", "Remove", "RemoveAt", "RemoveAll", "Clear", "Sort", "Reverse", "ToArray"),
        *("TryGetValue", "ContainsKey", "ContainsValue", "TryAdd", "GetValueOrDefault", "Push", "Pop"),
        *("Peek", "Enqueue", "Dequeue", "UnionWith", "IntersectWith", "ExceptWith", "IsSubsetOf"),
        *("GetEnumerator", "MoveNext", "CopyTo", "ForEach", "Exists", "FindAll", "BinarySearch"),
        # LINQ
        *("Select", "Where", "SelectMany", "OrderBy", "OrderByDescending", "ThenBy", "GroupBy", "Any"),
        *("All", "Count", "First", "FirstOrDefault", "Last", "LastOrDefault", "Single", "SingleOrDefault"),
        *("Skip", "Take", "Distinct", "Union", "Intersect", "Except", "Concat", "Zip", "Aggregate"),
        *("ToList", "ToDictionary", "ToHashSet", "Sum", "Min", "Max", "Average", "Cast", "OfType"),
        # object / IDisposable
        *("Equals", "GetHashCode", "GetType", "ToString", "Dispose"),
    }
)
# #4991: methods of the Ruby core classes (String, Array, Hash, Enumerable, Object). `s.strip` /
# `h.fetch(k)` / `list.map { ... }` on a receiver the scan cannot type is the core method far more
# often than a repo class's method of the same name. `[]` / `<<` are operators, not call names.
_BUILTIN_INSTANCE_METHODS_RUBY = frozenset(
    {
        # String / Symbol
        *("strip", "lstrip", "rstrip", "chomp", "chop", "chars", "upcase", "downcase", "capitalize"),
        *("swapcase", "start_with?", "end_with?", "include?", "gsub", "sub", "split", "scan", "tr"),
        *("to_s", "to_i", "to_f", "to_sym", "to_a", "to_h", "empty?", "length", "size", "slice"),
        *("index", "center", "ljust", "rjust", "format", "concat", "prepend", "freeze", "dup", "clone"),
        # Array / Hash / Enumerable
        *("each", "each_with_index", "each_with_object", "each_pair", "each_key", "each_value", "map"),
        *("collect", "select", "filter", "reject", "find", "detect", "find_all", "reduce", "inject"),
        *("flat_map", "group_by", "partition", "sort", "sort_by", "min_by", "max_by", "sum", "count"),
        *("first", "last", "take", "drop", "push", "pop", "shift", "unshift", "insert", "delete"),
        *("delete_if", "keep_if", "compact", "flatten", "uniq", "zip", "reverse", "rotate", "sample"),
        *("shuffle", "any?", "all?", "none?", "one?", "key?", "has_key?", "value?", "fetch", "dig"),
        *("keys", "values", "merge", "merge!", "update", "store", "tally", "min", "max", "join"),
        # Object / Kernel
        *("nil?", "is_a?", "kind_of?", "respond_to?", "instance_of?", "equal?", "eql?", "hash"),
        *("inspect", "tap", "then", "send", "public_send", "instance_variable_get", "freeze"),
    }
)
# #8161 (X2): standard-library / interface method names that an UNTYPED receiver far more often
# reaches in the standard library than in the repo: Go's `io.Closer`, `error`, `fmt.Stringer`,
# `sync.Mutex`, `atomic.*` and iterator methods (prometheus: 1,873 of 7,682 variable-receiver
# confident links), Rust's slice / `Option` / conversion traits, C++'s container and string members.
_BUILTIN_INSTANCE_METHODS_GO = frozenset(
    {"Close", "Error", "String", "Lock", "Unlock", "RLock", "RUnlock", "Load", "Store", "Next", "Err"}
)
_BUILTIN_INSTANCE_METHODS_RUST = frozenset({"len", "iter", "clone", "into", "unwrap", "as_ref", "fmt"})
_BUILTIN_INSTANCE_METHODS_CPP = frozenset({"size", "data", "begin", "end", "push_back", "c_str"})
_BUILTIN_INSTANCE_METHODS: dict[str, frozenset[str]] = {
    "go": _BUILTIN_INSTANCE_METHODS_GO,
    "rust": _BUILTIN_INSTANCE_METHODS_RUST,
    "cpp": _BUILTIN_INSTANCE_METHODS_CPP,
    "typescript": _BUILTIN_INSTANCE_METHODS_JS,
    "javascript": _BUILTIN_INSTANCE_METHODS_JS,
    "java": _BUILTIN_INSTANCE_METHODS_JAVA,
    "python": _BUILTIN_INSTANCE_METHODS_PYTHON,
    "embedded_python": _BUILTIN_INSTANCE_METHODS_PYTHON,
    "kotlin": _BUILTIN_INSTANCE_METHODS_KOTLIN,
    "csharp": _BUILTIN_INSTANCE_METHODS_CSHARP,
    "ruby": _BUILTIN_INSTANCE_METHODS_RUBY,
}

# #3756: JS/TS global namespaces whose static members (`Number.isFinite`,
# `JSON.parse`, `Object.keys`) are the built-in unless the repo defines a class
# of that name (a repo class is found first by `owned`, so reaching the
# fallback means it does not).
_BUILTIN_NAMESPACES: dict[str, frozenset[str]] = {
    lang: frozenset(
        {
            "Object",
            "Array",
            "String",
            "Number",
            "Boolean",
            "Symbol",
            "BigInt",
            "Math",
            "JSON",
            "Date",
            "RegExp",
            "Promise",
            "Reflect",
            "Proxy",
            "Map",
            "Set",
            "WeakMap",
            "WeakSet",
            "Error",
            "Intl",
            "Atomics",
            "ArrayBuffer",
            "Buffer",
            "process",
            "console",
        }
    )
    for lang in ("typescript", "javascript")
}
_BUILTIN_NAMESPACES["java"] = frozenset(
    {
        # #4991: java.lang / java.util classes whose static members (`Arrays.asList`,
        # `Math.max`, `Objects.equals`) are the JDK's unless the repo defines a class of that name.
        "Arrays",
        "Collections",
        "Objects",
        "Math",
        "String",
        "Integer",
        "Long",
        "Double",
        "Float",
        "Boolean",
        "Character",
        "Byte",
        "Short",
        "System",
        "Optional",
        "List",
        "Set",
        "Map",
        "Collectors",
        "Thread",
        "Files",
        "Paths",
    }
)

# Languages where a directory is a namespace: a class in a sibling file is
# visible without an import (a Java/Kotlin/Scala/Groovy package, a Go package,
# a C# namespace by convention). Elsewhere (Python, JS/TS, Ruby, PHP, C++) a
# sibling file is not visible until imported, so an untyped receiver whose only
# candidate is in the same directory stays an ambiguous `receiver` guess --
# #3333 measured ~3.7k such same-directory Python pairs on cpython alone, which
# would otherwise have become file-graph edges.
_PACKAGE_DIR_LANGS = frozenset({"java", "kotlin", "scala", "groovy", "go", "csharp"})

# #3443: languages where a BARE call reaches only the caller's own module, what
# it imports, and (in _PACKAGE_DIR_LANGS) its own package directory. A name
# defined exactly once elsewhere is not `unique` there: bugzilla's bare
# `remove(` is not Mojo's IOLoop.pm `remove`, a TypeScript `pipe(` is not
# jQuery's. The global-namespace languages (C, Lua, PHP, Ruby, Swift's
# module-wide scope, the mainframe languages) keep `unique`. Measured on
# language-crucible: ~530 pairs moved, most of them links into another
# repository; allowing definitions one import hop (or any number) away
# rescued almost no correct link and let wrong cross-repository Zig links back.
_PACKAGE_SCOPED_LANGS = _PACKAGE_DIR_LANGS | frozenset(
    {"perl", "python", "embedded_python", "javascript", "typescript", "zig", "rust", "dart"}
)


def encode_qualifiers(calls_out_to: list[str], qualifiers: dict[str, list[str]]) -> list[Any] | None:
    """The persisted form of `calls_out_qualifiers` (#3329): a list aligned with
    `calls_out_to`, so the callee names are not stored twice. Each element is the
    single receiver chain as a string (`""` for a bare call -- the common case),
    or a list when one function reaches the callee through several. None when
    the language captures no qualifiers (the map is empty).
    """
    if not qualifiers:
        return None
    out: list[Any] = []
    for callee in calls_out_to:
        seen = qualifiers.get(callee) or [""]
        out.append(seen[0] if len(seen) == 1 else list(seen))
    return out


def decode_qualifiers(calls_out_to: list[str], encoded: Any) -> dict[str, list[str]]:
    """`encode_qualifiers`'s inverse; anything malformed decodes to "not captured"."""
    if not isinstance(encoded, list) or len(encoded) != len(calls_out_to):
        return {}
    out: dict[str, list[str]] = {}
    for callee, q in zip(calls_out_to, encoded, strict=True):
        if isinstance(q, str):
            out[callee] = [q]
        elif isinstance(q, list) and all(isinstance(x, str) for x in q):
            out[callee] = list(q)
        else:
            return {}
    return out


def _group(lang: str) -> str:
    return _GROUP_OF.get(lang, lang)


def _key(name: str, lang: str) -> str:
    return name.casefold() if lang in CASE_INSENSITIVE_CALL_LANGS else name


def _leaf(name: str) -> tuple[str, str | None]:
    """`Foo::bar` / `Foo.bar` -> (`bar`, `Foo`); a plain name -> (name, None).

    Out-of-line C++ definitions (`int Foo::bar(...)`) and some method forms are
    extracted under their qualified name; a call site only ever carries the bare
    name (contract C6), so the definition is indexed by its last segment and the
    prefix stands in for the owning class.
    """
    for sep in ("::", "."):
        if sep in name:
            owner, _, leaf = name.rpartition(sep)
            if leaf:
                return leaf, owner.rpartition(sep)[2] or None
    return name, None


def _stem(path: str) -> str:
    base = posixpath.basename(path.replace("\\", "/"))
    return base.split(".", 1)[0]


def _dirname(path: str) -> str:
    return posixpath.dirname(path.replace("\\", "/"))


# A Maven/Gradle source root: the package starts below `src/<set>/<language>/`, and
# `src/main` and `src/test` (or any other set) of one module share it.
_SOURCE_ROOT = re.compile(r"^(?P<module>(?:.*/)?)src/[^/]+/(?:java|kotlin|scala|groovy)(?:/(?P<rest>.*))?$")
_SOURCE_ROOT_LANGS = frozenset({"java", "kotlin", "scala", "groovy"})


def _package_dir(dir_: str, lang: str) -> str:
    """The directory a file's package lives in, for visibility without an import.

    Where a directory is the package it is `dir_` itself. The JVM languages split
    one package over the source sets of a module (`m/src/main/java/p` and
    `m/src/test/java/p`): both map to `m/` + `p`, so a test sees the class under
    test. The module prefix stays in the key: a same-named package of another
    module is not visible.
    """
    if lang in _SOURCE_ROOT_LANGS:
        m = _SOURCE_ROOT.match(dir_)
        if m:
            return m.group("module") + "|" + (m.group("rest") or "")
    return dir_


def _parts(dir_: str) -> tuple[str, ...]:
    return tuple(dir_.split("/")) if dir_ else ()


def _rank(src_parts: tuple[str, ...], d: "_Definition") -> tuple[int, int]:
    """`path_proximity.proximity_rank` over pre-split directories (same order,
    same ties) -- the resolver ranks millions of candidates on a large repo."""
    shared = 0
    # reason: path parts may differ in length
    for a, b in zip(src_parts, d.parts, strict=False):
        if a != b:
            break
        shared += 1
    return -shared, len(d.parts)


class _Definition:
    __slots__ = (
        "arity",
        "dir",
        "kind",
        "line",
        "max_arity",
        "min_arity",
        "name",
        "owner_key",
        "params",
        "parts",
        "path",
        "pkg",
        "prop",
        "shape",
        "stem",
    )

    def __init__(
        self,
        path: str,
        dir_: str,
        parts: tuple[str, ...],
        stem: str,
        name: str,
        line: int,
        owner_key: str | None,
        kind: str,
        shape: str | None = None,
        arity: int | None = None,
        pkg: str | None = None,
        params: list[str] | None = None,
    ) -> None:
        self.path = path
        self.dir = dir_
        self.pkg = dir_ if pkg is None else pkg  # the package directory (`_package_dir`)
        self.parts = parts
        self.stem = stem
        self.name = name
        self.line = line
        self.owner_key = owner_key  # the owning class's name key, None for a free function
        self.kind = kind  # 'function' | 'class'
        # typescript/javascript (#3757): 'binding' | 'member'; None elsewhere
        self.shape = shape
        # #3835: the declared parameter count (the detector's `args`), for choosing
        # among overloads in OVERLOAD_LANGS; None for a class
        self.arity = arity
        # #8161 (J1): the declared parameter types (java_arg_types), None when unread
        self.params = params
        # #8161 (Y2): a Python `@property` / `@cached_property` getter: reading the attribute runs it
        self.prop = False
        # #8161 (P5): the counts a call may pass (C++ defaults widen the fewest; a variadic has no most)
        self.min_arity: int | None = arity
        self.max_arity: int | None = arity

    def fits(self, n: int) -> bool:
        """Whether a call with `n` arguments can reach this definition (#3835, #8161 P5)."""
        if self.min_arity is None:
            return False
        return self.min_arity <= n and (self.max_arity is None or n <= self.max_arity)


class _Set:
    """One filtered candidate list with the lookups the ladder needs, built once."""

    __slots__ = ("_prefix", "by_dir", "by_path", "defs", "n_paths", "owners")

    def __init__(self, defs: list[_Definition], signatures: tuple[_Definition, ...] = ()) -> None:
        self.defs = defs
        self.by_path: dict[str, _Definition] = {}  # path -> first definition in it
        self.by_dir: dict[str, list[_Definition]] = {}
        # path -> the distinct owners (classes; None = free) defining the name there.
        # #3836: a class that only DECLARES it (an interface, an `abstract` method)
        # counts too: a receiver may be that type, so it is one more candidate
        # class, though never a target itself.
        self.owners: dict[str, set[str | None]] = {}
        for d in signatures:
            self.owners.setdefault(d.path, set()).add(d.owner_key)
        for d in defs:
            self.owners.setdefault(d.path, set()).add(d.owner_key)
            if d.path not in self.by_path:
                self.by_path[d.path] = d
                self.by_dir.setdefault(d.pkg, []).append(d)
        self.n_paths = len(self.by_path)
        self._prefix: dict[tuple[str, ...], list[_Definition]] | None = None

    def nearest(self, src_parts: tuple[str, ...]) -> _Definition | None:
        """`_nearest_of` over the whole set, through a directory-prefix index.

        The deepest directory prefix of the caller that any candidate shares is
        the best shared depth; among the candidates at exactly that depth the
        shallowest wins, and two equally shallow ones are a tie -- the same
        order `_rank` defines, without ranking every candidate.
        """
        if self.n_paths < 16:
            return _nearest_of(list(self.by_path.values()), src_parts)
        if self._prefix is None:
            self._prefix = {}
            for d in self.by_path.values():
                for k in range(len(d.parts) + 1):
                    self._prefix.setdefault(d.parts[:k], []).append(d)
        for k in range(len(src_parts), -1, -1):
            group = self._prefix.get(src_parts[:k])
            if group:
                # every member shares exactly k directories (deeper prefixes were empty)
                return _nearest_of(group, src_parts)
        return None


class _Bucket:
    """Every definition of one name in one link group. The lookup sets are built
    on first use -- most names in a repository are never called by that name:
    `all`, `free` (free functions and classes -- what a bare call may reach),
    `methods` (functions with an owner -- what a receiver may reach)."""

    __slots__ = ("_all", "_free", "_methods", "by_owner", "defs", "signatures")

    def __init__(self) -> None:
        self.defs: list[_Definition] = []
        # owner key -> every definition of this name on a class of that name.
        # Several: two programs can share a PROGRAM-ID (zopeneditor's SAM1 and
        # SAM1LIB), two packages a class name -- `owned()` picks among them.
        self.by_owner: dict[str, list[_Definition]] = {}
        # #3836: bodyless declarations of the name on a class (an interface or
        # `abstract` method): never targets (#3757), but they say the call
        # dispatches to an override the scan cannot pick
        self.signatures: list[_Definition] = []
        self._all: _Set | None = None
        self._free: _Set | None = None
        self._methods: _Set | None = None

    def add(self, d: _Definition) -> None:
        self.defs.append(d)
        if d.kind == "function" and d.owner_key is not None:
            self.by_owner.setdefault(d.owner_key, []).append(d)

    @property
    def all(self) -> _Set:
        if self._all is None:
            self._all = _Set(self.defs)
        return self._all

    @property
    def free(self) -> _Set:
        if self._free is None:
            # #3758/#3759: an object-literal method or a member assignment has no
            # owning class but binds no name either -- a bare call cannot reach it
            self._free = _Set(
                [d for d in self.defs if (d.kind == "class" or d.owner_key is None) and d.shape != "member"]
            )
        return self._free

    @property
    def methods(self) -> _Set:
        if self._methods is None:
            self._methods = _Set(
                [
                    d
                    for d in self.defs
                    if d.kind == "function" and (d.owner_key is not None or d.shape == EXTENSION_SHAPE)
                ],
                tuple(self.signatures),
            )
        return self._methods


def _index(parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], _Bucket]:
    """(link group, name key) -> every definition of that name, in scan order.

    Functions and classes share the index: a constructor call `Foo(...)` names
    the class (contract C3). Synthetic top-level slices are callers, never
    definitions.
    """
    index: dict[tuple[str, str], _Bucket] = {}
    for f in parsed_files:
        path = f.get("path", "")
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        dir_, stem = _dirname(path), _stem(path)
        parts = _parts(dir_)
        pkg = _package_dir(dir_, lang)
        for func in f.get("functions", []) or []:
            if func.get("is_synthetic_slice"):
                continue
            shape = func.get("def_shape") or None
            if shape == "main_line":
                # #7170: a COBOL main line is named after its program but entered at the
                # program's start, never PERFORMed or called by that name: a caller, not a target.
                continue
            name = str(func.get("name") or "")
            leaf, prefix = _leaf(name)
            if not leaf:
                continue
            owner = func.get("parent_class_name") or prefix
            owner_key = _key(_leaf(owner)[0], lang) if owner else None
            if shape == "signature":
                # #3757: an interface member, an `abstract` method, an overload
                # signature -- no code runs there, so no call lands there. A
                # class's declaration is kept aside (#3836, see _Bucket.signatures).
                if owner_key is not None:
                    index.setdefault((group, _key(leaf, lang)), _Bucket()).signatures.append(
                        _Definition(
                            path,
                            dir_,
                            parts,
                            stem,
                            name,
                            int(func.get("start_line", 0) or 0),
                            owner_key,
                            "function",
                            shape,
                            pkg=pkg,
                        )
                    )
                continue
            definition = _Definition(
                path,
                dir_,
                parts,
                stem,
                name,
                int(func.get("start_line", 0) or 0),
                owner_key,
                "function",
                shape,
                int(func.get("args", 0) or 0),
                pkg=pkg,
                params=func.get("param_types"),
            )
            definition.prop = bool(_PROPERTY_DECORATORS.intersection(func.get("decorated_by") or ()))
            rng = func.get("arity_range")
            if isinstance(rng, list) and len(rng) in (2, 3):
                # [fewest, most (None: variadic), the header's parameter count] (#8161 P5)
                definition.min_arity, definition.max_arity = int(rng[0]), (None if rng[1] is None else int(rng[1]))
                if len(rng) == 3:
                    definition.arity = int(rng[2])
            index.setdefault((group, _key(leaf, lang)), _Bucket()).add(definition)
        for cls in f.get("classes", []) or []:
            name = str(cls.get("name") or "")
            if name:
                index.setdefault((group, _key(name, lang)), _Bucket()).add(
                    _Definition(
                        path, dir_, parts, stem, name, int(cls.get("start_line", 0) or 0), None, "class", pkg=pkg
                    )
                )
    return index


# What a language calls a class's constructor, when it is a method (#3642
# follow-up). A call that resolves to a class is linked to this method, so the
# function graph sees `Foo(...)` reach `Foo.__init__`. Languages not listed
# name the constructor after the class (java, c#, c++, dart); go, rust, c and
# the rest have no constructor method at all, and keep the class as the target.
_CONSTRUCTOR_NAMES: dict[str, tuple[str, ...]] = {
    "python": ("__init__", "__new__"),
    "embedded_python": ("__init__", "__new__"),
    "javascript": ("constructor",),
    "typescript": ("constructor",),
    "kotlin": ("constructor",),
    "php": ("__construct",),
    "ruby": ("initialize",),
    "swift": ("init",),
}
_CLASS_NAMED_CONSTRUCTOR_LANGS = frozenset({"java", "csharp", "cpp", "dart", "apex", "objective-c"})


def _constructor_of(index: dict[tuple[str, str], "_Bucket"], cls: _Definition, lang: str) -> _Definition | None:
    """The constructor method of class definition `cls`, if the scan extracted one.

    One in the class's own file, else one beside it with the same stem (a C++
    `foo.h` class, its `Foo::Foo` in `foo.cpp`). Owner keys are bare class
    names, so a constructor anywhere else may belong to another class of the
    same name and is never taken. None when the class has no constructor of
    its own (an inherited or implicit one): the call keeps the class.
    """
    leaf = _leaf(cls.name)[0]
    names = _CONSTRUCTOR_NAMES.get(lang) or ((leaf,) if lang in _CLASS_NAMED_CONSTRUCTOR_LANGS else ())
    group = _group(lang)
    owner = _key(leaf, lang)
    for n in names:
        bucket = index.get((group, _key(n, lang)))
        defs = [d for d in (bucket.by_owner.get(owner, []) if bucket else []) if d.kind == "function"]
        if not defs:
            continue
        for d in defs:
            if d.path == cls.path:
                return d
        for d in defs:
            if d.dir == cls.dir and d.stem == cls.stem:
                return d
    return None


def _include_closure(imports: dict[str, set[str]], path: str, memo: dict[str, set[str]]) -> set[str]:
    """#6266: every file `path` reaches through imports, transitively (a C++ include's own includes are visible too)."""
    if path not in memo:
        seen: set[str] = set()
        todo = list(imports.get(path, ()))
        while todo:
            nxt = todo.pop()
            if nxt not in seen:
                seen.add(nxt)
                todo.extend(imports.get(nxt, ()))
        memo[path] = seen
    return memo[path]


def _include_depths(imports: dict[str, set[str]], path: str) -> dict[str, int]:
    """#6266: how many include hops each file reachable from `path` is away (a direct include is 1)."""
    depth: dict[str, int] = {}
    level = list(imports.get(path, ()))
    hops = 1
    while level:
        level = [f for f in dict.fromkeys(level) if f not in depth]
        depth.update(dict.fromkeys(level, hops))
        level = [n for f in level for n in imports.get(f, ())]
        hops += 1
    return depth


# #6266: a type alias of a class (`typedef Private<PublicType> Base;` / `using Base = Private<P>;`). A ctor-init entry
# naming one (doomsday's DE_PIMPL `Impl(Public *i) : Base(i)`) calls the aliased base's constructor. Capitalised names
# only, and only where the target is a class the repo declares: `typedef int Bool;` shares its name with a data member.
_ALIAS_DECL = re.compile(
    r"\btypedef\b\s*(?:typename\s+)?([A-Za-z_][\w:]*)\s*(?:<[^;{}()]*>)?[\s*&]*([A-Z]\w*)\s*;"
    r"|\busing\s+([A-Z]\w*)\s*=\s*(?:typename\s+)?([A-Za-z_][\w:]*)"
)
_CLASS_DECL = re.compile(r"\b(?:class|struct)\s+(?:[A-Z_]+\s+)?([A-Za-z_]\w*)\s*[:{<;]")
# a data member `PType *Type = nullptr;` (the declared type, then the name, at a line start)
_FIELD_DECL = re.compile(
    r"(?m)^[ \t]*(?:(?:static|mutable|const|constexpr|volatile|inline)[ \t]+)*([A-Za-z_][\w:]*(?:<[^;{}()]*>)?)[ \t*&]+"
    r"([A-Z]\w*)[ \t]*(?:=[^;{}]*|\{[^;{}]*\})?;"
)
_NOT_A_TYPE = frozenset({"return", "typedef", "using", "delete", "goto", "case", "else", "throw", "break", "continue"})
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def class_alias_names(texts: Any) -> frozenset[str]:
    """#6266: the names that alias a class the texts declare (`Base` of `typedef Private<P> Base;`), over C++ sources."""
    return class_alias_tables(("", t) for t in texts)[0]


def class_alias_tables(sources: Any) -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    """#6266: over `(path, text)` C++ sources, the names that alias a class the sources declare (`Base` of
    `typedef Private<P> Base;`), and per path the names it aliases to a type no source declares (`using Base =
    std::vector<T>;` of doomsday's `List`).
    A name some class also declares as a data member (gzdoom's `PType *Type;` beside rapidjson's `typedef T1 Type;`) is
    a member more than an alias: its init-list entry `Type(ty)` must stay no base. A name aliased to a foreign type is
    no base call either, whatever class of that name another header declares: `List : std::vector` calls the standard
    library's constructor."""
    declared: set[str] = set()
    aliases: set[tuple[str, str]] = set()
    by_path: dict[str, set[tuple[str, str]]] = {}
    fields: set[str] = set()
    for path, text in sources:
        clean = _COMMENT.sub(" ", text)
        declared.update(_CLASS_DECL.findall(clean))
        for m in _ALIAS_DECL.finditer(clean):
            pair = (m.group(2) or m.group(3), (m.group(1) or m.group(4)).rsplit("::", 1)[-1])
            aliases.add(pair)
            by_path.setdefault(path, set()).add(pair)
        fields.update(
            m.group(2) for m in _FIELD_DECL.finditer(_ALIAS_DECL.sub(" ", clean)) if m.group(1) not in _NOT_A_TYPE
        )
    names = frozenset(name for name, target in aliases if target in declared and name not in fields)
    foreign = {
        path: frozenset(name for name, target in pairs if target not in declared and name not in fields)
        for path, pairs in by_path.items()
    }
    return names, {path: names_ for path, names_ in foreign.items() if names_}


def _init_entry_not_a_base(
    bucket: "_Bucket",
    callee: str,
    lang: str,
    src_path: str,
    caller_dir: str,
    imports: dict[str, set[str]],
    closures: dict[str, set[str]],
    step: str,
    class_aliases: frozenset[str] = frozenset(),
) -> bool:
    """#6266: a ctor-init entry names a base only when a class of that name is visible from the file (its own, its
    directory's, or its include closure's). A tie among several classes of that name (a nested `Node`, another
    platform's copy of a base) pins the one in the caller's own directory, else the one the include closure reaches
    (doomsday's `de::DialogWidget` beside `de::term::DialogWidget`); a class and its own constructor
    function tying is no ambiguity; failing both, the class fewest include hops away (`term::Widget`, not the `de::Widget`
    its header includes). A file with no includes at all reaches its bases some other way (doom3-bfg
    headers get `idException` from a precompiled header): visibility says nothing there, so its entries stay bases.
    An entry naming a class alias (`Base` of DE_PIMPL's `typedef Private<P> Base`, declared in a header the file need
    not include itself) is a base call whatever class of that name is in view."""
    if callee in class_aliases:
        return False
    visible = [
        d
        for d in bucket.defs
        if (d.kind == "class" or d.owner_key == _key(callee, lang))
        and (
            d.path == src_path
            or _dirname(d.path) == caller_dir
            or d.path in _include_closure(imports, src_path, closures)
        )
    ]
    if step == "tie" and sum(d.kind == "class" for d in bucket.defs) > 1:
        seen = [d for d in visible if d.kind == "class"]
        near = [d for d in seen if d.path == src_path or _dirname(d.path) == caller_dir]
        if not near and len(seen) > 1:  # none beside the caller: the one its includes reach first
            hops = _include_depths(imports, src_path)
            nearest = min(hops[d.path] for d in seen)
            seen = [d for d in seen if hops[d.path] == nearest]
        return len(near or seen) != 1
    return not visible and bool(imports.get(src_path))


def _imports_by_file(dependency_edges: list[dict[str, Any]] | None) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for e in dependency_edges or []:
        if e.get("edge_kind", "import") == "import":
            out.setdefault(e.get("src", ""), set()).add(e.get("dst", ""))
    return out


# Barrel files: a package's public face, which mostly re-exports what its
# modules define (`from .param_functions import Depends as Depends` in a
# package `__init__.py`, `export * from "./x"` in an `index.ts`). A caller that
# imports the barrel can see what the barrel imports.
_BARREL_BASENAMES = frozenset(
    {"__init__.py", "index.js", "index.ts", "index.tsx", "index.jsx", "index.mjs", "index.cjs", "index.mts"}
)
# Barrels import barrels (`pkg/__init__.py` -> `pkg/sub/__init__.py`); follow at most this many.
_BARREL_HOPS = 2


# #4253: `export * from` chains (zod: v4/index -> classic/index -> external -> schemas) are followed
# through any file, not just a barrel basename, this many hops (cycle-safe) and at most this many files.
_STAR_HOPS = 8
_STAR_FILES = 256


def _star_closure(start: set[str], star_exports: dict[str, set[str]] | None) -> set[str]:
    """The files reached from `start` by following `export * from` specifiers (bounded, cycle-safe)."""
    if not star_exports:
        return set()
    seen: set[str] = set()
    frontier = set(start)
    for _ in range(_STAR_HOPS):
        nxt: set[str] = set()
        for f in sorted(frontier):
            for d in sorted(star_exports.get(f, ())):
                if d not in seen and d not in start and len(seen) < _STAR_FILES:
                    seen.add(d)
                    nxt.add(d)
        frontier = nxt
        if not frontier:
            break
    return seen


def _with_reexports(
    imports: dict[str, set[str]], star_exports: dict[str, set[str]] | None = None
) -> dict[str, set[str]]:
    """#3642 follow-up: each file's imports plus what the barrels among them import.

    `from fastapi import Depends` resolves to `fastapi/__init__.py`, which only
    re-exports `Depends` from `fastapi/param_functions.py`. Without this the
    import step finds no definition in the barrel and the call falls through
    to a repository-wide name search. Only barrel files are expanded, and only
    `_BARREL_HOPS` deep, so importing an ordinary module never makes its own
    imports visible.
    """
    out: dict[str, set[str]] = {}
    for src, dsts in imports.items():
        seen = set(dsts)
        frontier = [d for d in dsts if posixpath.basename(d) in _BARREL_BASENAMES]
        for _ in range(_BARREL_HOPS):
            nxt = []
            for barrel in frontier:
                for d in imports.get(barrel, ()):
                    if d != src and d not in seen:
                        seen.add(d)
                        if posixpath.basename(d) in _BARREL_BASENAMES:
                            nxt.append(d)
            frontier = nxt
        seen |= _star_closure(seen, star_exports) - {src}
        out[src] = seen
    return out


# #8161 (J5): words in a recorded parent list that name no class (`extends X implements A, B`, `public Base`)
_PARENT_LIST_KEYWORDS = frozenset(
    {"extends", "implements", "with", "public", "protected", "private", "internal", "virtual", "sealed", "open"}
)
_PARENT_TYPE_ARGS = re.compile(r"<[^<>]*>|\[[^\[\]]*\]|\([^()]*\)")
_PARENT_NAME = re.compile(r"[A-Za-z_$][\w$]*(?:(?:\.|::)[A-Za-z_$][\w$]*)*")


def _parent_names(raw: Any) -> list[str]:
    """#8161 (J5): the class names in one recorded parent entry, leaf form. A header records its whole parent
    clause as one string (`Holder<String> implements Scaled, Serializable`, Python's `Base, Mixin, metaclass=M`,
    C#'s `Base<int>, IFoo`), which as one lineage key matched no class: type arguments and call parentheses
    go, the list splits on commas and keywords, and a `name=value` keyword argument is no parent."""
    text = str(raw)
    for _ in range(8):  # nested `<...>` / `[...]` / `(...)`, innermost first
        stripped = _PARENT_TYPE_ARGS.sub("", text)
        if stripped == text:
            break
        text = stripped
    # a header the detector cut inside the type arguments (`DoomColumnFunction<byte` of `<byte[],short[]>`) leaves
    # an unbalanced opener: the name is the identifier before it
    heads = (_PARENT_NAME.match(part) for part in re.split(r"[,\s]+", text) if part and "=" not in part)
    return [_leaf(m.group(0))[0] for m in heads if m and m.group(0) not in _PARENT_LIST_KEYWORDS]


def _ancestry(parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
    """(link group, class key) -> the names it inherits from, directly."""
    parents: dict[tuple[str, str], set[str]] = {}
    for f in parsed_files:
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        for cls in f.get("classes", []) or []:
            name = str(cls.get("name") or "")
            if not name:
                continue
            bases = {n for b in cls.get("inheritance", []) or [] for n in _parent_names(b)}
            parents.setdefault((group, _key(name, lang)), set()).update(_key(b, lang) for b in bases)
    return parents


def _expand_super_ctor(
    func: dict[str, Any],
    index: dict[tuple[str, str], "_Bucket"],
    parents: dict[tuple[str, str], set[str]],
    group: str,
    lang: str,
    local: dict[str, set[str]],
) -> None:
    """#3772: a constructor's `super(...)` becomes a call to its in-repo superclass's constructor.

    The detector keeps `super` (with its argument counts) only in a constructor; here it is
    replaced by the direct parent classes the scan knows. A parent outside the repo
    (`Exception`) leaves no call. The counts move to the parent name for overload choice.
    """
    owner = func.get("parent_class_name") or _leaf(str(func.get("name") or ""))[1]
    okey = _key(_leaf(str(owner))[0], lang) if owner else ""
    # a nested class name repeats across files (`HiColor`): the declaration in the caller's own file wins
    direct = sorted(local.get(okey) or parents.get((group, okey)) or set()) if owner else []
    # an `extends Base<T>` is recorded with its type arguments: `Base` names the class
    # (a header broken after `extends A` can leave `A implements` as one recorded name)
    named = sorted({_leaf(p.split("<")[0].split()[0])[0] for p in direct if p.strip()})
    known = [p for p in named if _is_class(index, group, p, lang)]
    arities = func.setdefault("calls_out_arities", {})
    quals = func.setdefault("calls_out_qualifiers", {})
    keyword = "super"
    counts = arities.pop(keyword, None)
    quals.pop(keyword, None)
    calls = [c for c in func["calls_out_to"] if c != keyword]
    for p in known:
        if p not in calls:
            calls.append(p)
        if counts:
            arities.setdefault(p, []).extend(a for a in counts if a not in arities.get(p, []))
        quals.setdefault(p, [""])
    func["calls_out_to"] = calls


def _is_class(index: dict[tuple[str, str], "_Bucket"], group: str, name: str, lang: str) -> bool:
    bucket = index.get((group, _key(name, lang)))
    return bucket is not None and any(d.kind == "class" for d in bucket.defs)


def _lineage(owner: str | None, group: str, lang: str, parents: dict[tuple[str, str], set[str]]) -> list[str]:
    """The caller's class followed by its ancestors, nearest first (bounded)."""
    if not owner:
        return []
    out = [_key(_leaf(owner)[0], lang)]
    frontier = [out[0]]
    while frontier and len(out) < 16:
        nxt = []
        for c in frontier:
            for p in sorted(parents.get((group, c), ())):
                if p not in out:
                    out.append(p)
                    nxt.append(p)
        frontier = nxt
    return out


def _nearest_of(defs: list[_Definition], src_parts: tuple[str, ...]) -> _Definition | None:
    """The nearest of definitions in DISTINCT files, or None on an exact tie."""
    if len(defs) == 1:
        return defs[0]
    best: _Definition | None = None
    best_rank = second_rank = (1, 0)
    for d in defs:
        r = _rank(src_parts, d)
        if best is None or r < best_rank:
            best, second_rank, best_rank = d, best_rank, r
        elif r < second_rank:
            second_rank = r
    return None if second_rank == best_rank else best


def _alias_scope(
    target: str, imports: dict[str, set[str]], star_exports: dict[str, set[str]] | None = None
) -> set[str]:
    """#3788: the files a namespace alias bound to `target` can reach: the module itself, and
    what a barrel module (`index.ts`) re-exports, `_BARREL_HOPS` deep (see `_with_reexports`)."""
    seen = {target}
    frontier = [target] if posixpath.basename(target) in _BARREL_BASENAMES else []
    for _ in range(_BARREL_HOPS + 1):
        nxt = []
        for barrel in frontier:
            for d in imports.get(barrel, ()):
                if d not in seen:
                    seen.add(d)
                    if posixpath.basename(d) in _BARREL_BASENAMES:
                        nxt.append(d)
        frontier = nxt
    return seen | _star_closure(seen, star_exports)


class _File:
    """What one calling file brings to every lookup made from it."""

    __slots__ = (
        "aliases",
        "class_files",
        "depth",
        "dir",
        "imported",
        "imported_dirs",
        "imported_stems",
        "includes",
        "lang",
        "parts",
        "path",
        "pkg",
        "rust",
    )

    def __init__(
        self,
        path: str,
        lang: str,
        imported: set[str],
        aliases: dict[str, set[str]] | None = None,
        depth: dict[str, int] | None = None,
        includes: set[str] | None = None,
    ) -> None:
        self.path = path
        # #8161 (X4): C/C++ -- how many include hops away each visible file is (a header's paired source counts
        # one past its header), and the files the caller's translation unit actually includes (its closure)
        self.depth = depth
        self.includes = includes
        # #8161 (R4): the crate's module tree, for a Rust caller
        self.rust: _RustTree | None = None
        # #8161 (X3): class name key -> the files defining a class of that name (shared, repo-wide)
        self.class_files: dict[str, set[str]] = {}
        # #3788: a namespace alias (`import * as ns from "x"`) -> the files `ns.f()` may reach
        self.aliases = aliases or {}
        self.lang = lang
        self.dir = _dirname(path)
        self.parts = _parts(self.dir)
        self.pkg = _package_dir(self.dir, lang)
        self.imported = imported
        self.imported_stems = {_stem(p) for p in imported}
        self.imported_dirs = {posixpath.basename(_dirname(p)) for p in imported}


_Cache = dict[tuple[str, str, int], _Definition | None]


def _nearest(cset: _Set, caller: _File, cache: _Cache) -> _Definition | None:
    """Nearest file in the whole set; depends only on the caller's directory."""
    ck = ("dir", caller.dir, id(cset))
    if ck not in cache:
        cache[ck] = cset.nearest(caller.parts)
    return cache[ck]


def _nearest_imported(cset: _Set, caller: _File, cache: _Cache) -> _Definition | None:
    """Nearest file among those the caller imports; depends on the caller's file.
    A tie among imported files still picks one (first path): both are visible."""
    ck = ("imp", caller.path, id(cset))
    if ck not in cache:
        if len(caller.imported) < cset.n_paths:
            hits = [cset.by_path[p] for p in caller.imported if p in cset.by_path]
        else:
            hits = [d for p, d in cset.by_path.items() if p in caller.imported]
        if hits and caller.depth:
            # #8161 (X4): the nearest include hop first (a direct include over one its includes reach)
            best = min(caller.depth.get(d.path, 1 << 20) for d in hits)
            hits = [d for d in hits if caller.depth.get(d.path, 1 << 20) == best]
        cache[ck] = (_nearest_of(hits, caller.parts) or min(hits, key=lambda d: d.path)) if hits else None
    return cache[ck]


def _nearest_local(cset: _Set, caller: _File, cache: _Cache) -> _Definition | None:
    """Nearest file in the caller's own directory (a package)."""
    ck = ("loc", caller.pkg, id(cset))
    if ck not in cache:
        local = cset.by_dir.get(caller.pkg)
        cache[ck] = (_nearest_of(local, caller.parts) or min(local, key=lambda d: d.path)) if local else None
    return cache[ck]


def _visible_receiver(cset: _Set, caller: _File, cache: _Cache) -> tuple[str, _Definition | None]:
    """An untyped receiver (`x.save()`): confident only when exactly ONE visible
    class defines the method -- in the caller's own file, else among the files
    it imports, else (package-scoped languages only) in its own directory. Several classes at the first level
    that has any (cython's Nodes.py defines `generate_execution_code` on ~40
    node classes; `self.body.generate_execution_code()` could be any of them)
    is the ambiguous `receiver` step, with the nearest as its guess (#3332)."""

    def classes(paths) -> int:
        return len({(p, o) for p in paths for o in cset.owners.get(p, ())})

    own = cset.by_path.get(caller.path)
    if own is not None:
        return ("file", own) if classes([caller.path]) == 1 else ("receiver", own)
    if caller.imported:
        hit = _nearest_imported(cset, caller, cache)
        if hit is not None:
            visible = [p for p in caller.imported if p in cset.owners]
            return ("import", hit) if classes(visible) == 1 else ("receiver", hit)
    hit = _nearest_local(cset, caller, cache) if caller.lang in _PACKAGE_DIR_LANGS else None
    if hit is not None:
        local = [d.path for d in cset.by_dir.get(caller.pkg, [])]
        return ("import", hit) if classes(local) == 1 else ("receiver", hit)
    return "receiver", _nearest(cset, caller, cache)


def _other_visible_class(cset: _Set, caller: _File) -> bool:
    """Whether a file the caller sees, other than its own, defines the name on a class."""
    if any(p in cset.owners for p in caller.imported if p != caller.path):
        return True
    if caller.lang in _PACKAGE_DIR_LANGS:
        return any(d.path != caller.path for d in cset.by_dir.get(caller.pkg, []))
    return False


# #8161 (C5): languages where the nearest-path pick among several definitions is confident. In C it almost
# always means "the variant in my own platform directory" (aix.c calling `uv_mutex_lock` links unix/thread.c,
# not win/thread.c): 363 of 363 judged picks agreed with libclang over 5 repos, 0 wrong. Elsewhere it stays the
# ambiguous `nearest` guess.
_PROXIMATE_CONFIDENT_LANGS = frozenset({"c"})


def _ladder(cset: _Set, caller: _File, visible_only: bool, cache: _Cache) -> tuple[str, _Definition | None]:
    """Steps file -> import -> unique -> nearest -> tie over an already-filtered set.

    `visible_only` is the unknown-receiver case: the method's defining file must
    be one the caller can see (its own, one it imports, or its own directory --
    a Java package or a Go package is a directory), or the best a name can do
    is the `receiver` guess.
    """
    if not cset.n_paths:
        return "none", None
    if visible_only:
        return _visible_receiver(cset, caller, cache)
    own = cset.by_path.get(caller.path)
    if own is not None:
        return "file", own
    if caller.imported:
        hit = _nearest_imported(cset, caller, cache)
        if hit is not None:
            return "import", hit
    if cset.n_paths == 1:
        return "unique", cset.defs[0]
    near = _nearest(cset, caller, cache)
    if near is not None and caller.lang in _PROXIMATE_CONFIDENT_LANGS:
        return "proximate", near
    return ("nearest", near) if near is not None else ("tie", None)


# #8161 (G3): the alias-key prefix of a Go dot import (network_risk_sensor.GO_DOT_IMPORT_PREFIX)
_GO_DOT_IMPORT_PREFIX = ". "


def _go_bare(cset: _Set, caller: _File, cache: _Cache) -> tuple[str, _Definition | None]:
    """#8161 (G3): a bare Go call by Go's scoping: the caller's own file, then its own package (a directory:
    confident even when other packages define the name), then the packages it dot-imports. An ordinary import
    never puts a name in bare scope; a definition reachable no other way is the ambiguous `unseen` guess."""
    if not cset.n_paths:
        return "none", None
    own = cset.by_path.get(caller.path)
    if own is not None:
        return "file", own
    for scope in (
        cset.by_dir.get(caller.pkg, []),
        [d for d in cset.defs if d.pkg in _go_dot_dirs(caller)],
    ):
        if scope:
            paths = {d.path for d in scope}
            # several files of one package defining it: build-tag variants (`_linux.go`, `_windows.go`)
            return ("import", scope[0]) if len(paths) == 1 else ("tie", None)
    return "unseen", _nearest(cset, caller, cache) or cset.defs[0]


def _go_package_call(bucket: _Bucket, caller: _File, qualifier: str) -> tuple[str, _Definition | None] | None:
    """#8161 (G1): `pkg.F()` where `pkg` is one of the caller's import names: a function of THAT package (any file
    of its directory), never another imported package's or the caller's own; `pkg.T.M()` a method of type `T`
    there. A package outside the scan (`errors.New`, `http.Get`) reaches nothing in the repo. Several files of
    the package defining it are build-tag variants (`_linux.go`, `_windows.go`): a tie. None when `pkg` is no
    import name, or `pkg.x.M()` names no type of the package (a package-level variable: an untyped receiver)."""
    head, _, rest = qualifier.partition(".")
    if head not in caller.aliases or head.startswith(_GO_DOT_IMPORT_PREFIX):
        return None
    scope = caller.aliases[head]
    if not scope:
        return "none", None
    if rest:
        owner = _key(rest.rpartition(".")[2], caller.lang)
        defs = [d for d in bucket.by_owner.get(owner, []) if d.path in scope]
        if not defs:
            return None
    else:
        defs = [d for d in bucket.free.defs if d.path in scope]
    paths = {d.path for d in defs}
    if len(paths) == 1:
        return "import", defs[0]
    return ("tie", None) if paths else ("none", None)


def _go_package_files(parsed_files: list[dict[str, Any]]) -> dict[str, set[str]]:
    """#8161 (G1): each Go package directory -> its non-test files (what an importer of the package sees)."""
    out: dict[str, set[str]] = {}
    for f in parsed_files:
        path = str(f.get("path", ""))
        if str(f.get("lang_id", "")).lower() == "go" and path and not path.endswith("_test.go"):
            out.setdefault(_dirname(path), set()).add(path)
    return out


def _go_dot_dirs(caller: _File) -> set[str]:
    return {_dirname(p) for a, files in caller.aliases.items() if a.startswith(_GO_DOT_IMPORT_PREFIX) for p in files}


def _rust_parent_module_files(path: str) -> frozenset[str]:
    """#8161 (R3): the files that can hold the parent module of the Rust file at `path` (`super::`)."""
    d, base = _dirname(path), posixpath.basename(path)
    if base in ("mod.rs", "lib.rs", "main.rs"):
        d = _dirname(d)
    up = _dirname(d)
    files = {posixpath.join(d, f) if d else f for f in ("mod.rs", "lib.rs", "main.rs")}
    if d:
        files.add(posixpath.join(up, posixpath.basename(d) + ".rs") if up else posixpath.basename(d) + ".rs")
    return frozenset(files)


class _RustTree:
    """#8161 (R4): a Rust crate's module tree as the scan's file paths show it (`mod m;` is `m.rs` or `m/mod.rs`
    beside the declaring module's own directory), for resolving a call's module path to the module's FILE."""

    def __init__(self, paths: set[str], imports: dict[str, set[str]]) -> None:
        self.paths = paths
        self.imports = imports
        # a workspace crate's name (its directory, `-` read as `_`) -> its `src/` directory
        self.crates = {
            posixpath.basename(_dirname(_dirname(p))).replace("-", "_"): _dirname(p)
            for p in sorted(paths)
            if posixpath.basename(p) == "lib.rs" and posixpath.basename(_dirname(p)) == "src"
        }

    @staticmethod
    def module_dir(path: str) -> str:
        """The directory a file module's child modules live in (`src/a.rs` -> `src/a`; `src/a/mod.rs` -> `src/a`)."""
        d, base = _dirname(path), posixpath.basename(path)
        if base in ("mod.rs", "lib.rs", "main.rs"):
            return d
        stem = base[: -len(".rs")] if base.endswith(".rs") else base
        return posixpath.join(d, stem) if d else stem

    def crate_root(self, path: str) -> str | None:
        """The `src/`-style directory of the crate `path` belongs to: the nearest ancestor holding lib.rs/main.rs."""
        d = _dirname(path)
        while True:
            if any((posixpath.join(d, f) if d else f) in self.paths for f in ("lib.rs", "main.rs")):
                return d
            if not d:
                return None
            d = _dirname(d)

    def child(self, base: str, seg: str) -> str | None:
        for f in (f"{seg}.rs", f"{seg}/mod.rs"):
            p = posixpath.join(base, f) if base else f
            if p in self.paths:
                return p
        return None

    def module_file(self, caller_path: str, segs: list[str], up: int) -> str | None:
        """The file of the module `segs` names from `caller_path` (`up` leading `super`s), or None when a segment
        is no file module (an inline `mod`, an external crate, a type)."""
        if not segs:
            return None
        head = segs[0]
        if head == "crate":
            root = self.crate_root(caller_path)
            bases = [root] if root is not None else []
            segs = segs[1:]
        elif head == "self":
            bases, segs = [self.module_dir(caller_path)], segs[1:]
        elif up:
            base = self.module_dir(caller_path)
            for _ in range(up):
                base = _dirname(base)
            bases = [base]
        elif head in self.crates and self.child(self.module_dir(caller_path), head) is None:
            bases, segs = [self.crates[head]], segs[1:]
            if not segs:
                return posixpath.join(bases[0], "lib.rs")
        else:
            root = self.crate_root(caller_path)
            bases = [self.module_dir(caller_path)] + ([root] if root is not None else [])
        for base in dict.fromkeys(bases):
            found: str | None = None
            cur = base
            for seg in segs:
                found = self.child(cur, seg)
                if found is None:
                    break
                cur = self.module_dir(found)
            if found is not None:
                return found
        return None


def _rust_module_call(bucket: _Bucket, caller: _File, segs: list[str], up: int) -> _Definition | None:
    """#8161 (R4): `m::f()` / `crate::m::f()` / `super::m::f()` / `cratename::f()`: the free function `f` in the
    module's file, else in the one file the module imports it from (a `pub use` re-export)."""
    tree = caller.rust
    if tree is None:
        return None
    target = tree.module_file(caller.path, segs, up)
    if target is None:
        return None
    d = bucket.free.by_path.get(target)
    if d is not None:
        return d
    hits = [bucket.free.by_path[p] for p in sorted(tree.imports.get(target, ())) if p in bucket.free.by_path]
    return hits[0] if len(hits) == 1 else None


def _rust_path(bucket: _Bucket, caller: _File, path: str, owned: Any, cache: _Cache) -> tuple[str, _Definition | None]:
    """#8161 (R1, R3): a Rust call through a path (`a::B::f()`, `crate::m::f()`, `super::f()`; `path` is the
    qualifier without its `::` mark, segments joined by `.`).

    A path whose last segment is a type (CamelCase, as Rust names them) reaches that type's method (`qualified`)
    or nothing in the repo. `super::f()` names the parent MODULE: the caller's own file first (an inline `mod
    tests`' parent), then the files that can hold it (`mod.rs`, `lib.rs` / `main.rs`, `<dir>.rs`), a sibling
    module's `f` not reached; `super::m::f()` reads as `m::f()`. Any other module path reaches a free function
    of a module the caller imports by that name; else no edge (`std::mem::swap` is not a repo `swap`)."""
    segs = [s for s in path.split(".") if s]
    last = segs[-1] if segs else ""
    if last[:1].isupper() and last != "Self":
        d = owned(_key(last, caller.lang))
        return ("qualified", d) if d is not None else ("none", None)
    up = 0
    if segs and segs[0] == "super":
        while segs and segs[0] == "super":
            segs.pop(0)
            up += 1
        if not segs:
            own = bucket.free.by_path.get(caller.path)
            if own is not None:
                return "file", own
            parents = _rust_parent_module_files(caller.path)
            hits = [d for p, d in bucket.free.by_path.items() if p in parents]
            if len(hits) == 1:
                return "import", hits[0]
            step, d = _ladder(bucket.free, caller, False, cache)
            return ("unseen", d) if step == "unique" else (step, d)
    if segs == ["self"]:
        own = bucket.free.by_path.get(caller.path)
        return ("file", own) if own is not None else ("none", None)
    if segs == ["crate"]:
        root = caller.rust.crate_root(caller.path) if caller.rust is not None else None
        hits = [
            bucket.free.by_path[p]
            for p in (posixpath.join(root, f) if root else f for f in ("lib.rs", "main.rs"))
            if root is not None and p in bucket.free.by_path
        ]
        return ("import", hits[0]) if len(hits) == 1 else ("none", None)
    d = _rust_module_call(bucket, caller, segs, up)
    if d is not None:
        return ("file" if d.path == caller.path else "import"), d
    head, last = (segs[0], segs[-1]) if segs else ("", "")
    if head in caller.imported_stems or last in caller.imported_stems or last in caller.imported_dirs:
        via = [
            d
            for p, d in bucket.free.by_path.items()
            if p in caller.imported and (d.stem in (head, last) or posixpath.basename(d.dir) == last)
        ]
        if via:
            return "import", (_nearest_of(via, caller.parts) or min(via, key=lambda d: d.path))
    return "none", None


# #8161 (X3): languages whose typed receiver must name a class the caller can see: in its own file or one it imports
# (C/C++: its include closure). `new FormData()` in a JS test is the platform's FormData, not another test file's
# class of that name. Go's typing is scoped by package instead (`owned`, `typed_scope`); a Rust type name is always
# in scope where it is written (a `use`, a glob, a path), which the import graph does not fully see (-1.3 pp recall
# on serde-json when checked, no precision gained).
_TYPED_SEEN_LANGS = frozenset({"cpp", "typescript", "javascript"})


def _class_in_view(d: _Definition, owner_key: str, caller: _File) -> bool:
    """Whether method `d` of class `owner_key`, or a class definition of that name, is in a file the caller sees."""
    if d.path == caller.path or d.path in caller.imported:
        return True
    return any(p == caller.path or p in caller.imported for p in caller.class_files.get(owner_key, ()))


def _resolve_one(
    bucket: _Bucket | None,
    caller: _File,
    lineage: list[str],
    qualifier: str | None,
    cache: _Cache,
    typed: dict[str, list[str]] | None = None,
    typed_scope: dict[str, set[str]] | None = None,
) -> tuple[str, _Definition | None]:
    """One (caller, callee, qualifier) lookup. `qualifier` None = not captured. `typed_scope` (#8161, Go) names the
    only files a typed receiver's class may be defined in (`x *pkg.T`: the package `pkg` binds)."""
    if bucket is None:
        return "none", None
    by_owner = bucket.by_owner

    def owned(owner_key: str) -> _Definition | None:
        """The caller's own file's definition on that class, else the nearest one."""
        defs = by_owner.get(owner_key)
        if defs and caller.lang == "go":
            # #8161 (G1): a Go type's methods are in its own package; another package's type of the same name is
            # reached only through that package's import name (`_go_package_call`)
            defs = [d for d in defs if d.pkg == caller.pkg]
        if not defs:
            return None
        for d in defs:
            if d.path == caller.path:
                return d
        return _nearest_of(defs, caller.parts) or min(defs, key=lambda d: d.path)

    def walk(owners: list[str]) -> tuple[str, _Definition | None] | None:
        """The caller's lineage, nearest class first: the first class with a body
        for the name wins (`class`). #3836: a class that only DECLARES it -- an
        `abstract` method, an interface's -- ends the walk: the call dispatches to
        an override, which the scan cannot pick, so it is the ambiguous `receiver`
        step (an implementation as the guess), never a confident link. The
        caller's own class is checked in its own file, where it is defined."""
        for i, owner_key in enumerate(owners):
            d = owned(owner_key)
            if d is not None and (i or d.path == caller.path):
                return "class", d
            if any(s.owner_key == owner_key and (i or s.path == caller.path) for s in bucket.signatures):
                return "receiver", _ladder(bucket.methods, caller, True, cache)[1]
            if d is not None:
                return "class", d
        return None

    ns = False
    if qualifier is not None and qualifier.startswith("::") and caller.lang in _NAMESPACE_QUALIFIED_LANGS:
        ns, qualifier = True, qualifier[2:]
        if not qualifier:
            step, d = _ladder(bucket.free, caller, True, cache)  # a global `::f()`: a visible free function only
            return (step, d) if step in ("file", "import") else ("none", None)

    if caller.lang == "objective-c":
        # #5639: a send's receiver is recorded as its qualifier, but objc methods carry no owner here, so
        # the receiver (`self`, an ivar) cannot narrow a lookup; resolved by selector name, as before.
        qualifier = None

    if qualifier is not None and qualifier.startswith("!"):
        return "none", None  # #5634: a macro invocation `name!(..)` is never a call of a function `name`

    if (
        qualifier == ""
        and bucket.defs
        and _leaf(bucket.defs[0].name)[0] in _BARE_BUILTINS.get(caller.lang, ())
        # #8161: Go lets a package-level function shadow a predeclared one, in its own package only
        and not (caller.lang == "go" and any(d.pkg == caller.pkg for d in bucket.free.defs))
    ):
        return "none", None  # the built-in (#3401), external like any library call
    if caller.lang == "php" and qualifier == "static":
        qualifier = "self"  # #8161 (PR 5): `static::m()` is the class's own (late-bound) method, as `self::m()`
    if qualifier is None or qualifier == "":
        # #8161 (PR 5): a bare PHP call never reaches a method (that takes `$this->` / `self::`): `count()`,
        # `unlink()` in a class with its own `count` / `unlink` method are the builtins
        hit = None if qualifier == "" and caller.lang == "php" else walk(lineage)
        if hit is not None:
            return hit
        # A bare call cannot reach another class's method: only a free
        # function, a class (a constructor), or the caller's own lineage,
        # handled above. #8161: a Go method has no owner but is `member`-shaped,
        # which `free` leaves out, so Go bare calls reach free functions only too.
        cset = bucket.free if qualifier == "" else bucket.all
        if qualifier == "" and caller.lang == "go":
            return _go_bare(cset, caller, cache)
        step, d = _ladder(cset, caller, False, cache)
        if (
            step == "unique"
            and qualifier == ""
            and caller.lang in _PACKAGE_SCOPED_LANGS
            and not (caller.lang in _PACKAGE_DIR_LANGS and d is not None and d.pkg == caller.pkg)
        ):
            return "unseen", d  # #3443: the only definition, but not one this caller can see
        return step, d

    if caller.lang in _PATH_QUALIFIED_LANGS and qualifier is not None and qualifier.startswith("::"):
        # #8161 (R1): a Rust path. `Self::f()` is the caller's own type, like `self.f()`; `Type::f()` is a
        # method of an in-repo type (an `impl` block's) or nothing in the repo (`Vec::new`, `String::from`);
        # `m::f()` / `self::f()` / `super::f()` name a MODULE, so only a free function answers them
        path = qualifier[2:]
        if path == "Self":
            qualifier = "self"
        else:
            return _rust_path(bucket, caller, path, owned, cache)
    if caller.lang == "go" and qualifier and caller.aliases:
        pkg_hit = _go_package_call(bucket, caller, qualifier)
        if pkg_hit is not None:
            return pkg_hit
    if qualifier in _SELF_RECEIVERS and not ns:
        hit = walk(lineage)
        if hit is not None:
            return hit
        return _ladder(bucket.methods, caller, True, cache)
    if qualifier in _SUPER_RECEIVERS:
        for owner_key in lineage[1:]:
            d = owned(owner_key)
            if d is not None:
                return "class", d
        return "none", None
    if typed and qualifier in typed and not ns:
        # The receiver's class is known from this function (`app = FastAPI()`):
        # the method on that class, or on the nearest ancestor that has it.
        scope = (typed_scope or {}).get(qualifier)
        for owner_key in typed[qualifier]:
            if scope is not None:
                in_pkg = [d for d in by_owner.get(owner_key, ()) if d.path in scope]
                d = (_nearest_of(in_pkg, caller.parts) or min(in_pkg, key=lambda d: d.path)) if in_pkg else None
            else:
                d = owned(owner_key)
                if d is not None and caller.lang in _TYPED_SEEN_LANGS and not _class_in_view(d, owner_key, caller):
                    d = None
            if d is not None:
                return "typed", d
    head = qualifier.split(".", 1)[0]
    last = qualifier.rsplit(".", 1)[-1]
    d = owned(_key(last, caller.lang))
    if d is not None:
        return "qualified", d
    if caller.aliases and qualifier in caller.aliases:
        # #3788: `import * as processors from "./json-schema-processors.js"`: the alias names that
        # module, whatever the file is called. Only the module itself (and, for a barrel, what it
        # re-exports) can hold `processors.f`.
        via = [d for d in bucket.all.defs if d.path in caller.aliases[qualifier] and d.owner_key is None]
        # #8161 (T3a): an object-literal / prototype member there (zod's `set(...)` in a descriptor,
        # `toJSONSchema(params)` in a class-less object) is no module export in TypeScript. JavaScript keeps one when
        # nothing else is there: a CommonJS module's exports ARE members (`exports.f = function`).
        exported = [d for d in via if d.shape != "member"]
        firsts: dict[str, _Definition] = {}
        for d in exported if (exported or caller.lang == "typescript") else via:
            firsts.setdefault(d.path, d)
        via = list(firsts.values())
        if via:
            return "import", (_nearest_of(via, caller.parts) or min(via, key=lambda d: d.path))
    # #4991: `util.propertyKeyTypes.has(k)`: the receiver is a PROPERTY of the imported module (a
    # Set), not the module, so a built-in method name is the built-in, not `util.has`.
    member_builtin = (
        head != last
        and last not in caller.imported_stems
        and last not in caller.imported_dirs
        and bool(bucket.defs)
        and _leaf(bucket.defs[0].name)[0] in _BUILTIN_INSTANCE_METHODS.get(caller.lang, ())
    )
    if not member_builtin and (
        head in caller.imported_stems or last in caller.imported_stems or last in caller.imported_dirs
    ):
        via = [
            d
            for p, d in bucket.all.by_path.items()
            if p in caller.imported
            and (d.stem in (head, last) or posixpath.basename(d.dir) == last)
            and not (d.owner_key is not None and ns)
        ]
        if via:
            return "import", (_nearest_of(via, caller.parts) or min(via, key=lambda d: d.path))
    # A receiver the engine cannot type: a variable, a call result, an external
    # module. Only a method can answer it (a free function is not reachable
    # through a receiver), and only a visible one confidently.
    if qualifier in _BUILTIN_NAMESPACES.get(caller.lang, ()) and bucket.defs:
        return "none", None  # #3756: `Number.isFinite`, `JSON.parse`: the global, not a repo method
    if ns:
        # only a free function the caller can see: `std::move(x)` must not reach a repo `move` elsewhere
        step, d = _ladder(bucket.free, caller, True, cache)
        if step in ("file", "import"):
            return step, d
    cset = bucket.methods
    step, d = _ladder(cset, caller, True, cache)
    if (
        step in ("file", "import")
        and bucket.defs
        and _leaf(bucket.defs[0].name)[0] in _BUILTIN_INSTANCE_METHODS.get(caller.lang, ())
    ):
        # #3756: `input.data.trim()`, `seen.has(x)` on a receiver the scan cannot type.
        return "receiver", d
    if step == "file" and d is not None and d.owner_key in lineage and _other_visible_class(cset, caller):
        # #3837: `members.entrySet()` inside JsonObject, which has its own
        # entrySet. An explicit receiver other than `this` is usually ANOTHER
        # object: the caller's own class is only one candidate, so with another
        # visible class defining the name the call is ambiguous, not `file`.
        return "receiver", d
    if (
        d is not None
        and RESOLUTION_OF_STEP.get(step) in CONFIDENT_RESOLUTIONS
        and any(x.shape == EXTENSION_SHAPE for x in cset.defs)
        and len({(x.path, x.owner_key) for x in cset.defs}) > 1
    ):
        # #8161 (PR 5): a Kotlin extension answers a receiver it cannot type only as the one definition of the
        # name: `x.asTypeName()` near `fun ParameterizedType.asTypeName()` is as likely `Type.asTypeName()`
        return "receiver", d
    return step, d


# #3759: languages where one file holds several bindings of a name only in
# different scopes -- a `const Node = ...` in each test callback, a helper nested
# in two functions. A second binding in ONE scope is an error there (an overload
# signature is not a binding, #3757), so the binding a bare call sees is the
# nearest one written before it, its own scope's or an enclosing one's, or, when
# none precedes, the last (a function declaration is hoisted). Python is not
# listed: a module-level redefinition is legal and the last one wins at runtime.
_BLOCK_SCOPED_LANGS = frozenset({"typescript", "javascript"})


def _in_scope_same_file(bucket: "_Bucket", path: str, caller_line: int) -> _Definition | None:
    """Among several same-file bindings a bare call can reach (`bucket.free`), the
    one a call at `caller_line` sees; None with fewer than two."""
    same = [d for d in bucket.free.defs if d.path == path and d.kind == "function"]
    if len(same) < 2:
        return None
    before = [d for d in same if d.line <= caller_line]
    return max(before or same, key=lambda d: d.line)


# #3835: languages with overloading -- several methods of one name on one class,
# told apart by their parameters. The resolver picks among them by the argument
# counts the caller used (the detector's `calls_out_arities`); when a count still
# matches several overloads, or none, the call is ambiguous (`overload`), a row
# but never an edge. #3784: C++ joins (libclang on fmt judged 220 links the wrong overload).
# Measured on gson vs scip-java: 1,653 of 1,923 wrong confident
# links were an arbitrary pick among overloads.
# #8161 (PR 5): C# and Kotlin join, with overload_types.py's argument types (577 of C#'s 623 and 88 of Kotlin's
# 98 wrong confident links on the LAWS survey repos were another overload).
OVERLOAD_LANGS = frozenset({"java", "cpp", "csharp", "kotlin"})


def _overloads(index: dict[tuple[str, str], "_Bucket"], dst: _Definition, group: str, lang: str) -> list[_Definition]:
    """Every definition of `dst`'s name on `dst`'s class in `dst`'s file (itself included)."""
    bucket = index.get((group, _key(_leaf(dst.name)[0], lang)))
    if bucket is None:
        return [dst]
    return [d for d in bucket.defs if d.kind == "function" and d.path == dst.path and d.owner_key == dst.owner_key]


def _choose_overloads(
    overloads: list[_Definition],
    arities: list[int],
    arg_types: list[list[str]] | None = None,
    subtype: Callable[[str, str], bool | None] | None = None,
    lang: str = "java",
) -> tuple[list[_Definition], bool]:
    """(the overloads the call's argument counts pick, whether any count stays ambiguous).

    Each count picks the one overload declaring that many parameters; a count that
    matches several, or none (a variadic method, an arity the detector miscounted),
    is ambiguous. No recorded count at all is ambiguous too. #8161 (J1): a count that
    matches several is decided by argument type: each call site of that count whose
    types pick one overload (java_arg_types.choose) picks it, and a site they do not
    decide leaves the count ambiguous as well.
    """
    picked: list[_Definition] = []
    ambiguous = not arities
    typed = lang in overload_types.LANGS
    for n in arities:
        # #8161 (PR 5): C# and Kotlin choose among every overload the count fits (a default or a `params` /
        # `vararg` makes it fit); their types decide, never a tier of counts
        match = [d for d in overloads if d.fits(n)] if typed else _arity_matches(overloads, n)
        if len(match) == 1:
            if match[0] not in picked:
                picked.append(match[0])
            continue
        sites = [t for t in arg_types or () if len(t) == n]
        if typed:
            chosen = [
                overload_types.choose(
                    [None if d.params is None else (d.params, d.max_arity is None) for d in match],
                    t,
                    lang,
                    subtype,
                    [d.min_arity if d.min_arity is not None else len(d.params or ()) for d in match],
                )
                for t in sites
            ]
        else:
            chosen = [java_choose([d.params for d in match], t, subtype) for t in sites] if match else []
        if not sites or any(k is None for k in chosen):
            ambiguous = True  # a site no type decides: the count keeps its `overload` row
        for k in chosen:
            if k is not None and match[k] not in picked:
                picked.append(match[k])  # each decided site is certain on its own
    return picked, ambiguous


# #8161 (Y2): decorators that make a method an attribute whose read runs it (`@x.getter` is the same getter)
_PROPERTY_DECORATORS = frozenset({"property", "cached_property", "getter", "cached_property_with_ttl"})


def _property_getter(
    index: dict[tuple[str, str], "_Bucket"], dst: _Definition, group: str, lang: str
) -> _Definition | None:
    """#8161 (Y2): the `@property` getter named like `dst` on `dst`'s class in `dst`'s file (a setter or deleter
    shares the name), or None when the attribute is no property."""
    if dst.prop:
        return dst
    for d in _overloads(index, dst, group, lang):
        if d.prop:
            return d
    return None


def _arity_matches(overloads: list[_Definition], n: int) -> list[_Definition]:
    """#8161 (P5): the overloads a call with `n` arguments may reach, best tier first.

    A parameter count equal to `n` wins (#3835; a variadic's pack or ellipsis then takes one argument); else an
    overload that takes `n` through its default arguments; else a variadic that takes `n` (an ellipsis or a pack
    ranks last in C++ overload resolution). Several in the winning tier stay ambiguous."""
    exact = [d for d in overloads if d.arity == n]
    by_default = [
        d for d in overloads if d.max_arity is not None and d.min_arity is not None and d.min_arity <= n < d.max_arity
    ]
    variadic = [d for d in overloads if d.max_arity is None and d.min_arity is not None and d.min_arity <= n]
    return exact or by_default or variadic


def _apply_declared_arities(index: dict[tuple[str, str], "_Bucket"], parsed_files: list[dict[str, Any]]) -> None:
    """#8161 (P5): a C++ member declared with a default or a variadic (`void emit(int a, int b = 0);`, in the
    class's header) widens its definition's range: the out-of-line `Printer::emit(int a, int b)` repeats no
    default. A definition takes a declared range of its class when the parameter counts agree."""
    for f in parsed_files:
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        for cls in f.get("classes", []) or []:
            declared = cls.get("method_arities") or {}
            if not declared or not cls.get("name"):
                continue
            owner = _key(_leaf(str(cls["name"]))[0], lang)
            for method, ranges in declared.items():
                bucket = index.get((group, _key(method, lang)))
                if bucket is None:
                    continue
                for d in bucket.defs:
                    if d.kind != "function" or d.owner_key != owner:
                        continue
                    for fewest, most, count in ranges:
                        if d.arity == count:
                            d.min_arity = min(int(fewest), d.min_arity if d.min_arity is not None else int(fewest))
                            if most is None:
                                d.max_arity = None


def _java_subtype(
    index: dict[tuple[str, str], "_Bucket"], parents: dict[tuple[str, str], set[str]], group: str, lang: str
) -> Callable[[str, str], bool | None]:
    """#8161 (J1): is class `sub` a subtype of `sup`? Certain only when both name exactly one repo class:
    then `sub`'s in-repo lineage decides (a library class cannot extend a repo class). None otherwise."""

    def one_class(name: str) -> bool:
        bucket = index.get((group, _key(name, lang)))
        return bucket is not None and sum(1 for d in bucket.defs if d.kind == "class") == 1

    def subtype(sub: str, sup: str) -> bool | None:
        if not (one_class(sub) and one_class(sup)):
            return None
        lineage = _lineage(sub, group, lang, parents)
        if _key(sup, lang) in lineage:
            return True
        return None if len(lineage) >= 16 else False

    return subtype


# #8161 (X4): C and C++ see what the translation unit includes, transitively, and a header's own source file
_INCLUDE_VISIBILITY_LANGS = frozenset({"c", "cpp"})
_C_SOURCE_EXTS = (".c", ".cc", ".cpp", ".cxx", ".c++", ".cp")
_C_HEADER_EXTS = (".h", ".hh", ".hpp", ".hxx", ".h++", ".inl", ".ipp", ".tcc")


def _c_sources_by_stem(parsed_files: list[dict[str, Any]]) -> dict[str, list[str]]:
    """#8161 (X4): C/C++ source files (not headers) by file stem, for pairing a header with its body file."""
    out: dict[str, list[str]] = {}
    for f in parsed_files:
        path = str(f.get("path", ""))
        if str(f.get("lang_id", "")).lower() in _INCLUDE_VISIBILITY_LANGS and path.lower().endswith(_C_SOURCE_EXTS):
            out.setdefault(_stem(path), []).append(path)
    return out


def _c_visibility(
    imports: dict[str, set[str]],
    path: str,
    lang: str,
    sources: dict[str, list[str]],
    closures: dict[str, set[str]],
) -> tuple[set[str], dict[str, int], set[str]]:
    """#8161 (X4): (visible files, include depth of each, the include closure) for a C/C++ caller at `path`.

    The closure is every file the translation unit includes, transitively (`_include_closure`): a static inline
    helper in `alloc.h` reached through `hiredis.h` is in view. A header declares what its paired source file
    defines (`foo.h` -> `foo.c` / `foo.cc` beside it; in C++ also the repo's only source of that stem, as
    `include/fmt/format.h` -> `src/format.cc`), so that source is visible too, one hop past its header: a call
    through `foo.h` reaches the body in `foo.cc`. C pairs only beside the header: libuv's `include/uv/aix.h`
    declares no `src/unix/aix.c` functions to a Windows caller."""
    closure = _include_closure(imports, path, closures)
    depth = _include_depths(imports, path)
    visible = set(closure)
    for header in sorted(closure):
        if not header.lower().endswith(_C_HEADER_EXTS):
            continue
        same_stem = sources.get(_stem(header), [])
        paired = [p for p in same_stem if _dirname(p) == _dirname(header)] or (
            same_stem if lang == "cpp" and len(same_stem) == 1 else []
        )
        for p in paired:
            if p != path and p not in visible:
                visible.add(p)
                depth[p] = depth.get(header, 1) + 1
    return visible, depth, closure


def _visible_statics(
    bucket: "_Bucket | None", caller: _File, memo: dict[tuple[int, str], "_Bucket"]
) -> "_Bucket | None":
    """#8161 (X4): `bucket` without the C/C++ `static` free functions the caller's translation unit cannot see
    (another file's statics, unless the caller #includes that file). Memoised per (bucket, caller file); the
    filtered buckets live as long as the memo, so the `id()`-keyed lookup cache never sees a reused id."""
    if bucket is None or caller.includes is None:
        return bucket
    hidden = [
        d
        for d in bucket.defs
        if d.shape == C_STATIC_SHAPE and d.owner_key is None and d.path != caller.path and d.path not in caller.includes
    ]
    if not hidden:
        return bucket
    key = (id(bucket), caller.path)
    out = memo.get(key)
    if out is None:
        out = _Bucket()
        gone = {id(d) for d in hidden}
        for d in bucket.defs:
            if id(d) not in gone:
                out.add(d)
        out.signatures = list(bucket.signatures)
        memo[key] = out
    return out


# #8161 (C1, owner decision): languages whose tie across several definitions records every candidate as a
# `variant` edge (`fcall_candidates`): in C one external symbol defined once per platform or build option is one
# symbol, only one copy of which a given build links (libuv `uv__io_poll` in linux.c, kqueue.c, sunos.c, ...)
VARIANT_LANGS = frozenset({"c"})
# a path segment (directory, or a file name's `-`/`_`/`.` parts) that names the platform its code is built for
_PLATFORM_TOKENS = {
    **dict.fromkeys(("win", "win32", "win64", "windows", "mingw", "msvc"), "windows"),
    **dict.fromkeys(("darwin", "macos", "osx", "apple", "mac"), "darwin"),
    **dict.fromkeys(("kqueue", "bsd"), "bsd"),
    **dict.fromkeys(("sunos", "solaris", "illumos"), "sunos"),
    **dict.fromkeys(("os390", "zos", "mvs"), "zos"),
    **{
        t: t
        for t in (
            "unix",
            "posix",
            "linux",
            "android",
            "freebsd",
            "openbsd",
            "netbsd",
            "dragonfly",
            "aix",
            "ibmi",
            "qnx",
            "haiku",
            "cygwin",
            "hurd",
        )
    },
}
_PATH_TOKEN_SPLIT = re.compile(r"[-_.]")


def platform_of(path: str) -> str | None:
    """#8161: the platform a C file's path says its code is for (`src/unix/linux.c` -> `linux`, `src/win/fs.c` ->
    `windows`, `sockcompat_win32.c` -> `windows`), the file name first, then its directories nearest first; None
    when the path names none."""
    parts = path.replace("\\", "/").lower().split("/")
    for i, part in enumerate(reversed(parts)):
        tokens = _PATH_TOKEN_SPLIT.split(part.rsplit(".", 1)[0] if i == 0 else part)
        for t in tokens:
            if t in _PLATFORM_TOKENS:
                return _PLATFORM_TOKENS[t]
    return None


def _variants(cset: "_Set") -> list[dict[str, Any]]:
    """#8161: every function definition of a tied name, one per file, as `variant` edge targets."""
    return [
        {"dst_path": d.path, "dst_name": d.name, "dst_line": d.line, "platform": platform_of(d.path)}
        for d in sorted(cset.by_path.values(), key=lambda d: d.path)
        if d.kind == "function"
    ]


def resolve_calls(
    parsed_files: list[dict[str, Any]],
    dependency_edges: list[dict[str, Any]] | None = None,
    namespace_aliases: dict[str, dict[str, str]] | None = None,
    star_exports: dict[str, set[str]] | None = None,
    class_aliases: frozenset[str] = frozenset(),
    foreign_aliases: dict[str, frozenset[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve every (caller function, callee name) pair in the repository.

    `namespace_aliases` (#3788) maps a JS/TS file to the modules its namespace imports
    name (`{file: {alias: module path}}`), so `ns.f()` reaches the module `ns` is bound to.
    `class_aliases` (#6266) are the repo's class-typedef names (`class_alias_names`): a C++ ctor-init entry naming one is a base call.
    `foreign_aliases` (#6266) maps a file to the names it aliases to a type outside the repo (`class_alias_tables`): its
    ctor-init entries naming one call that type, not a repo class.

    Returns `(sites, stats)`:
      - `sites`: one row per distinct callee name per caller (calls_out_to is
        already deduplicated, contract decision 3), resolved or not. A resolved
        row names its definition by `(dst_path, dst_name, dst_line, dst_kind)`;
        `kind` is 'call', or 'transfer' for a COBOL GO TO target (#3362:
        resolved the same way, never counted in the call-resolution rates).
        `qualifier` is the receiver chain the winning lookup used (#3329), None
        where the language captures none. A callee reached through several
        receivers keeps the most confident of their resolutions. Self-resolution
        (a call that lands on the caller itself) is dropped, as the contract
        drops recursion.
      - `stats`: counts by step and by resolution, repo-wide and per language
        -- the numbers #3331 reports.
    """
    index = _index(parsed_files)
    _apply_declared_arities(index, parsed_files)
    parents = _ancestry(parsed_files)
    # proximity depends only on the caller's directory, so the nearest pick for
    # a candidate set is shared by every caller in that directory
    cache: _Cache = {}
    imports = _with_reexports(_imports_by_file(dependency_edges), star_exports)
    closures: dict[str, set[str]] = {}
    sites: list[dict[str, Any]] = []
    by_step: Counter[str] = Counter()
    by_lang: dict[str, Counter[str]] = {}
    transfers: Counter[str] = Counter()
    decorators: Counter[str] = Counter()
    references: Counter[str] = Counter()
    ctors: Counter[str] = Counter()

    go_packages = _go_package_files(parsed_files)
    rust_paths = {str(f.get("path", "")) for f in parsed_files if str(f.get("lang_id", "")).lower() == "rust"}
    rust_tree = _RustTree(rust_paths, imports) if rust_paths else None
    c_sources = _c_sources_by_stem(parsed_files)
    class_files: dict[str, set[str]] = {}
    for (_g, key), b in index.items():
        for d in b.defs:
            if d.kind == "class":
                class_files.setdefault(key, set()).add(d.path)
    static_memo: dict[tuple[int, str], _Bucket] = {}

    for f in parsed_files:
        src_path = f.get("path", "")
        lang = str(f.get("lang_id", "")).lower()
        group = _group(lang)
        file_aliases = (namespace_aliases or {}).get(src_path, {})
        if lang in _INCLUDE_VISIBILITY_LANGS:
            visible, depth, closure = _c_visibility(imports, src_path, lang, c_sources, closures)
            caller = _File(
                src_path,
                lang,
                visible,
                {a: _alias_scope(t, imports, star_exports) for a, t in file_aliases.items()},
                depth=depth,
                includes=closure,
            )
        elif lang == "go":
            # #8161 (G1): a Go package is its directory: an import (and an import name) sees every non-test file of
            # the package, not only the representative file the import edge names; `""` is a package outside the scan
            caller = _File(
                src_path,
                lang,
                {p for t in imports.get(src_path, set()) for p in go_packages.get(_dirname(t), {t})},
                {a: set(go_packages.get(_dirname(t), {t})) if t else set() for a, t in file_aliases.items()},
            )
        else:
            caller = _File(
                src_path,
                lang,
                imports.get(src_path, set()),
                {a: _alias_scope(t, imports, star_exports) for a, t in file_aliases.items()},
            )
        if lang == "rust":
            caller.rust = rust_tree
        caller.class_files = class_files
        lang_counts = by_lang.setdefault(lang, Counter())
        file_parents: dict[str, set[str]] = {}
        for cls in f.get("classes", []) or []:
            if cls.get("name"):
                bases = {n for b in cls.get("inheritance", []) or [] for n in _parent_names(b)}
                file_parents.setdefault(_key(str(cls["name"]), lang), set()).update(_key(b, lang) for b in bases)
        # A module's own receiver types (`app = FastAPI()` at top level) hold in
        # every function of the file that does not bind that name itself.
        module_types: dict[str, str] = {}
        for unit in f.get("functions", []) or []:
            if unit.get("calls_only"):
                module_types.update(unit.get("calls_out_receiver_types") or {})
        for func in f.get("functions", []) or []:
            # #3362: calls, then unconditional transfers (COBOL GO TO). A transfer
            # resolves by the same ladder (it names a unit the same way) but is
            # its own `kind`: it never counts toward the call-resolution rates.
            if lang in OVERLOAD_LANGS and "super" in (func.get("calls_out_to") or []):
                _expand_super_ctor(func, index, parents, group, lang, file_parents)
            callees = [(c, "call") for c in func.get("calls_out_to") or []]
            callees += [(t, "transfer") for t in func.get("transfers_to") or []]
            # Decorators: the decorated function -> each decorator applied to it
            # (its wrapper runs around every call). Same ladder, own `kind`, and
            # like a transfer never counted in the call-resolution rates.
            callees += [(d, "decorator") for d in func.get("decorated_by") or []]
            # References: a function name used as a value (a callback, `Depends(f)`).
            # Most candidates are variables, so only a confident, scoped link to a
            # function becomes a row (see _REFERENCE_STEPS below).
            callees += [(r, "reference") for r in func.get("references_to") or []]
            # #8161 (P3): a C++ construction the text does not write as a call (`T x;`, `make_unique<T>()`):
            # the class's constructor, as its own kind
            ctor_forms = func.get("ctor_forms") or {}
            callees += [(c, "ctor") for c in ctor_forms]
            # #8161 (Y2): `self.x` read, not called: a call to x's getter when x is a `@property`
            callees += [(p, "property") for p in func.get("property_reads") or []]
            if not callees:
                continue
            caller_name = str(func.get("name") or "")
            caller_line = int(func.get("start_line", 0) or 0)
            caller_end = caller_line + int(func.get("loc", 0) or 0) - 1
            lineage = _lineage(func.get("parent_class_name") or _leaf(caller_name)[1], group, lang, parents)
            qualifier_map = func.get("calls_out_qualifiers") or {}
            decorator_map = func.get("decorated_by_qualifiers") or {}
            reference_map = func.get("references_qualifiers") or {}
            # receiver -> its class's lineage, for receivers whose class the scan
            # knows (a factory function's name is not a class, and is ignored)
            # knows. A name the function binds itself with no known class ("")
            # hides the module's type for it rather than inheriting it.
            receiver_types = {**module_types, **(func.get("calls_out_receiver_types") or {})}
            typed = {
                q: _lineage(c, group, lang, parents)
                for q, c in receiver_types.items()
                if c and _is_class(index, group, str(c), lang)
            }
            typed_scope: dict[str, set[str]] = {}
            for q, c in receiver_types.items():
                if lang == "rust" and c == "Self" and lineage:
                    typed[q] = lineage  # #8161 (X3): `let x = Self::new()` is the caller's own type
                elif lang == "go" and c and "." in str(c):
                    # #8161 (X3): `x *pkg.T` is T in the package that import name binds, nowhere else
                    alias, _, leaf = str(c).partition(".")
                    files = caller.aliases.get(alias)
                    if files and _is_class(index, group, leaf, lang):
                        typed[q] = _lineage(leaf, group, lang, parents)
                        typed_scope[q] = files
            recursive: list[str] = []
            renames = func.get("calls_out_renames") or {}
            for callee, kind in callees:
                # #8161 (X5): `plus2()` after `import { add as plus2 }` is looked up as `add`
                looked_up = renames.get(callee, callee) if kind == "call" else callee
                bucket = _visible_statics(index.get((group, _key(str(looked_up), lang))), caller, static_memo)
                quals = {
                    "call": qualifier_map,
                    "decorator": decorator_map,
                    "reference": reference_map,
                    "ctor": {c: list(dict.fromkeys(str(q) for q, _ in forms)) for c, forms in ctor_forms.items()},
                    "property": {p: ["self"] for p in func.get("property_reads") or []},
                }.get(kind, {})
                options: list[str | None] = list(quals.get(callee) or []) or [None]
                # #6266: a C++ constructor's bare initializer-list entry is a call only to a base class
                init_only = kind == "call" and bool(options) and all(q == INIT_LIST_QUALIFIER for q in options)
                options = list(dict.fromkeys(None if q == INIT_LIST_QUALIFIER else q for q in options))
                step, dst = _resolve_one(bucket, caller, lineage, options[0], cache, typed, typed_scope)
                used = options[0]
                for q in options[1:]:
                    alt_step, alt_dst = _resolve_one(bucket, caller, lineage, q, cache, typed, typed_scope)
                    if _RANK[alt_step] < _RANK[step]:
                        step, dst, used = alt_step, alt_dst, q
                if kind == "reference" and (step not in _REFERENCE_STEPS or dst is None or dst.kind != "function"):
                    continue  # a variable, a class, or a name the scope cannot see: no row
                if kind in ("property", "reference") and dst is not None and dst.kind == "function":
                    getter = _property_getter(index, dst, group, lang) if step in ("class", "typed") else None
                    if kind == "reference" and getter is not None:
                        continue  # a property read in value position is the getter's call (below), no reference
                    if kind == "property":
                        if getter is None:
                            continue  # a data attribute (or a method read as a value: a `reference`)
                        dst, kind = getter, "call"
                elif kind == "property":
                    continue
                if (
                    kind in ("call", "reference")
                    and not used
                    and bucket is not None
                    and dst is not None
                    and dst.path == src_path
                    and caller_end > caller_line
                ):
                    # `wrapper(...)` / `return wrapper` inside a function that defines
                    # its own nested `wrapper`: that one, not the file's first.
                    nested = [
                        d
                        for d in bucket.all.defs
                        if d.path == src_path and d.kind == "function" and caller_line < d.line <= caller_end
                    ]
                    if nested and not (caller_line < dst.line <= caller_end):
                        dst = min(nested, key=lambda d: d.line)
                if (
                    kind in ("call", "reference")
                    and not used
                    and lang in _BLOCK_SCOPED_LANGS
                    and bucket is not None
                    and dst is not None
                    and dst.path == src_path
                    and dst.kind == "function"
                    and dst.owner_key is None
                    and not (caller_line < dst.line <= caller_end)
                ):
                    dst = _in_scope_same_file(bucket, src_path, caller_line) or dst
                if (
                    kind == "call"
                    and not used
                    and bucket is not None
                    and dst is not None
                    and dst.path == src_path
                    and dst.line == caller_line
                    and dst.name == caller_name
                    and bucket.free.defs
                    and lang not in overload_types.LANGS
                ):
                    # #5628: a bare `f(` in `Scope::f` found the unit itself on the class rung; the
                    # detector keeps it because a free `f` (this file or another) may be the callee.
                    # If one resolves, that is the edge; if none does it stays recursion. #8161 (PR 5): not in
                    # Kotlin or C#, where the member shadows a top-level `f` (the detector keeps the call there
                    # for a sibling overload, not for a free function)
                    free_step, free_dst = _ladder(bucket.free, caller, False, cache)
                    if free_dst is not None:
                        step, dst = free_step, free_dst
                if (
                    kind == "call"
                    and dst is None
                    and not used
                    and callee == caller_name
                    and quals.get(callee) == [""]
                    and bucket is not None
                    and any(d.path == src_path and d.line == caller_line for d in bucket.defs)
                ):
                    # #8161: a Go method `f`'s bare `f(` with no free `f` to reach (a method is `member`-shaped,
                    # so no bare call reaches the unit itself): recursion through the name, as before (#5699)
                    recursive.append(callee)
                    continue
                if init_only and str(callee) in (foreign_aliases or {}).get(src_path, ()):
                    recursive.append(callee)  # `: Base(n)` of `using Base = std::vector<T>`: the library's constructor
                    continue
                if (
                    init_only
                    and str(callee) not in class_aliases
                    and not (bucket is not None and any(d.kind == "class" for d in bucket.defs))
                    and (dst is None or (dst.kind != "class" and dst.owner_key != _key(str(callee), lang)))
                ) or (
                    init_only
                    and bucket is not None
                    and _init_entry_not_a_base(
                        bucket, str(callee), lang, src_path, caller.dir, imports, closures, step, class_aliases
                    )
                ):
                    recursive.append(callee)  # a data member `: type(t)`, not a call, whatever function shares its name
                    continue
                cls = None
                if dst is not None and dst.kind == "class":
                    # A constructor call reaches the class's constructor method.
                    ctor = _constructor_of(index, dst, lang)
                    if ctor is not None:
                        cls, dst = dst, ctor
                if kind == "ctor" and (cls is None or dst is None):
                    continue  # not a repository class with a constructor of its own: no unit runs that we know
                # #3835: a confident call to one of several overloads -> the overloads
                # its argument counts pick, each its own row; a count that cannot
                # choose leaves an ambiguous `overload` row (the first overload kept
                # as the guess), which is never an edge
                targets: list[tuple[str, _Definition | None]] = [(step, dst)]
                if (
                    kind in ("call", "ctor")
                    and lang in OVERLOAD_LANGS
                    and dst is not None
                    and dst.kind == "function"
                    and RESOLUTION_OF_STEP[step] in CONFIDENT_RESOLUTIONS
                ):
                    overloads = _overloads(index, dst, group, lang)
                    if len(overloads) > 1:
                        arities = (
                            list(dict.fromkeys(int(n) for _, n in ctor_forms.get(callee) or []))
                            if kind == "ctor"
                            else [int(a) for a in (func.get("calls_out_arities") or {}).get(callee) or []]
                        )
                        picked, ambiguous = _choose_overloads(
                            overloads,
                            arities,
                            (func.get("calls_out_arg_types") or {}).get(callee),
                            _java_subtype(index, parents, group, lang),
                            lang,
                        )
                        targets = [(step, d) for d in picked]
                        if ambiguous:
                            # #8161 (J2): the guess is an overload the call's argument count fits, when one does
                            fits = [d for d in [dst, *overloads] if d not in picked and any(map(d.fits, arities))]
                            guess = fits[0] if fits else (dst if dst not in picked else overloads[0])
                            targets.append(("overload", guess))
                for step, dst in targets:
                    if dst is not None and dst.path == src_path and dst.line == caller_line and dst.name == caller_name:
                        # recursion through a qualified name (`Foo::bar` calling `bar`); a bare call
                        # that reaches only the unit itself is not a call (#3327, #5628); only where the
                        # detector recorded the bare qualifier (a shell `md5` is a binary, not recursion);
                        # #3772: an overload language's detector keeps a bare self-name call, and a count
                        # that picks only the unit itself is its recursion
                        if (
                            kind == "call"
                            and (callee != caller_name or lang in BARE_CALL_SKIPS_METHODS or lang in OVERLOAD_LANGS)
                            and len(targets) == 1
                            and quals.get(callee) == [""]
                        ):
                            recursive.append(callee)
                        continue
                    resolution = RESOLUTION_OF_STEP[step]
                    if kind == "call":
                        by_step[step] += 1
                        lang_counts[resolution] += 1
                    elif kind == "decorator":
                        decorators[step] += 1
                    elif kind == "reference":
                        references[step] += 1
                    elif kind == "ctor":
                        ctors[step] += 1
                    else:
                        transfers[step] += 1
                    site: dict[str, Any] = {
                        "src_path": src_path,
                        "src_name": caller_name,
                        "src_line": caller_line,
                        "src_synthetic": bool(func.get("is_synthetic_slice")),
                        "callee": callee,
                        "kind": kind,
                        "qualifier": used,
                        "step": step,
                        "resolution": resolution,
                        "candidates": bucket.all.n_paths if bucket else 0,
                        "dst_path": dst.path if dst else None,
                        "dst_name": dst.name if dst else None,
                        "dst_line": dst.line if dst else None,
                        "dst_kind": dst.kind if dst else None,
                        # the class a constructor call named, when dst is its constructor
                        "dst_class_path": cls.path if cls else None,
                        "dst_class_name": cls.name if cls else None,
                    }
                    if step == "tie" and kind == "call" and lang in VARIANT_LANGS and bucket is not None:
                        # #8161: the tie stays an ambiguous row; each candidate is a `variant` edge
                        variants = _variants(bucket.free if used == "" else bucket.all)
                        if len(variants) > 1:
                            site["variants"] = variants
                    sites.append(site)
            if recursive:
                func["calls_out_to"] = [c for c in func["calls_out_to"] if c not in recursive]
                for gone in recursive:
                    qualifier_map.pop(gone, None)
                    (func.get("calls_out_arities") or {}).pop(gone, None)
                    (func.get("calls_out_arg_types") or {}).pop(gone, None)
            # the marker is for this pass only: a kept base-class entry reads as the plain call it is
            for callee_quals in qualifier_map.values():
                if INIT_LIST_QUALIFIER in callee_quals:
                    callee_quals[:] = list(dict.fromkeys("" if q == INIT_LIST_QUALIFIER else q for q in callee_quals))

    by_resolution: Counter[str] = Counter()
    for step, n in by_step.items():
        by_resolution[RESOLUTION_OF_STEP[step]] += n
    stats = {
        "by_step": dict(by_step),
        "by_resolution": dict(by_resolution),
        "by_language": {lang: dict(c) for lang, c in sorted(by_lang.items()) if c},
        "transfers_by_step": dict(transfers),
        "ctors_by_step": dict(ctors),
        "decorators_by_step": dict(decorators),
        "references_by_step": dict(references),
    }
    return sites, stats


# A reference is kept only when the name is in scope for certain: the caller's
# class, a qualified or typed receiver, its own file or a file it imports.
# `unique` is not enough -- a local variable named like the repository's one
# function of that name is still a variable.
_REFERENCE_STEPS = frozenset({"class", "qualified", "typed", "file", "import"})

RESOLUTION_CLASSES = ("scoped", "unique", "ambiguous", "external")

# Stated wherever a rate is shown (#3331): the rate is the resolver's confidence,
# not its accuracy -- #3332 measures correctness.
RATE_CAVEAT = (
    "A high scoped/unique share means the resolver made a confident choice, not that the choice "
    "was correct; resolution accuracy is measured separately (gitgalaxy#3332)."
)


def _rate_row(language: str, counts: dict[str, int]) -> dict[str, Any]:
    scoped = int(counts.get("scoped", 0))
    unique = int(counts.get("unique", 0))
    ambiguous = int(counts.get("ambiguous", 0))
    external = int(counts.get("external", 0))
    return {
        "language": language,
        "scoped": scoped,
        "unique": unique,
        "ambiguous": ambiguous,
        "external": external,
        "total": scoped + unique + ambiguous + external,
    }


def resolution_rates(stats: dict[str, Any]) -> list[dict[str, Any]]:
    """#3331: per-language rows plus a repository row (`language` '*'), each with
    the count of (caller, callee) pairs in every resolution class and their total.
    Languages with no pairs are omitted; an empty repository gives no rows."""
    rows = [_rate_row(lang, counts) for lang, counts in sorted((stats.get("by_language") or {}).items())]
    rows = [r for r in rows if r["total"]]
    if rows:
        repo = Counter[str]()
        for r in rows:
            for c in RESOLUTION_CLASSES:
                repo[c] += r[c]
        rows.insert(0, _rate_row("*", repo))
    return rows


def confident_file_pairs(sites: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    """#3333: (caller file, callee file) -> how many calling functions link to
    it confidently (scoped/unique), across files only. What the dependency
    graph adds as call edges. A constructor call that reached a class counts:
    the caller depends on the class's file either way."""
    pairs: Counter[tuple[str, str]] = Counter()
    for s in sites:
        dst = s.get("dst_path")
        # #3362: a transfer (COBOL GO TO) never joins the file graph.
        if s.get("kind", "call") != "call":
            continue
        # #8161 (J2): an `overload` row names the right FILE (every candidate overload is in it, on one class),
        # only the overload is unknown: it joins the file graph, never the function graph
        confident_file = s.get("resolution") in CONFIDENT_RESOLUTIONS or s.get("step") == "overload"
        if dst and confident_file and dst != s.get("src_path"):
            pairs[(s.get("src_path", ""), dst)] += 1
    return dict(pairs)
