"""#8161: a C/C++ include naming a system header (`<errno.h>`, `<sys/time.h>`) resolves only on the repo's
include path -- the repo root, an `include/` or `inc/` directory, or a directory a multi-segment include of
the repo resolves through -- never to a same-named repo file by bare name. libuv's `include/uv/errno.h` is
reached as `"uv/errno.h"`; its 61 `#include <errno.h>` sites are the C library's header."""

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_C = LANGUAGE_DEFINITIONS["c"]

REPO = {
    "include/uv.h": '#include "uv/errno.h"\n#include "uv/unix.h"\n',
    "include/uv/errno.h": "#define UV_EOF (-4095)\n",
    "include/uv/unix.h": "#include <sys/time.h>\n",
    "include/sys2/time.h": "struct t;\n",
    "src/unix/core.c": '#include <errno.h>\n#include <poll.h>\n#include "uv.h"\n#include <mach/task.h>\n',
    "adapters/poll.h": "int x;\n",
    "test/task.h": "int y;\n",
    "compat/time.h": "int z;\n",
    "compat/use.c": "#include <time.h>\n",  # beside the includer: the compiler's `-I.` would pick it
    "include/stdbool.h": "#define bool int\n",
    "lib/b.c": "#include <stdbool.h>\n",  # `include/` is on the include path
}

EXPECTED = {
    ("include/uv.h", "include/uv/errno.h"),
    ("include/uv.h", "include/uv/unix.h"),
    ("src/unix/core.c", "include/uv.h"),
    ("compat/use.c", "compat/time.h"),
    ("lib/b.c", "include/stdbool.h"),
}


def _edges(files):
    rule = _C["rules"]["_dependency_capture"]
    parsed = [
        {
            "path": rel,
            "lang_id": "c",
            "raw_imports": sorted(extract_raw_imports(rule, text, _C)),
            "functions": [],
            "classes": [],
        }
        for rel, text in files.items()
    ]
    return set(NetworkRiskSensor().resolve_import_edges(parsed))


def test_system_headers_resolve_only_on_the_include_path():
    assert _edges(REPO) == EXPECTED


# #7827: the whole class -- every C-family importer, every system-directory prefix -- never reaches a repo file
# that only shares the basename (curl's `ares/` -> `include/curl/types.h`).
_PREFIXED = ["sys/types.h", "sys/time.h", "machine/types.h", "os/types.h", "netinet6/types.h", "net80211/types.h"]
_IMPORTERS = [("c", "c"), ("cpp", "cpp"), ("objective-c", "m")]


def _edges_from(lang, ext, files):
    d = LANGUAGE_DEFINITIONS[lang]
    rule = d["rules"]["_dependency_capture"]
    parsed = [
        {
            "path": rel,
            "lang_id": lang if rel.endswith("." + ext) else "c",
            "raw_imports": sorted(extract_raw_imports(rule, text, d)) if rel.endswith("." + ext) else [],
            "functions": [],
            "classes": [],
        }
        for rel, text in files.items()
    ]
    return set(NetworkRiskSensor().resolve_import_edges(parsed))


def test_a_prefixed_system_include_never_names_a_same_basename_repo_file():
    for lang, ext in _IMPORTERS:
        for token in _PREFIXED:
            base = token.rsplit("/", 1)[1]
            files = {
                f"include/curl/{base}": "int a;\n",
                f"include/internal/{base}": "int b;\n",
                f"ares/a.{ext}": f"#include <{token}>\n",
            }
            assert _edges_from(lang, ext, files) == set(), (lang, token)


def test_a_repo_that_owns_the_prefixed_path_keeps_its_edge():
    for lang, ext in _IMPORTERS:
        files = {
            "include/sys/types.h": "int a;\n",
            "include/curl/types.h": "int b;\n",
            f"ares/a.{ext}": "#include <sys/types.h>\n",
        }
        assert _edges_from(lang, ext, files) == {(f"ares/a.{ext}", "include/sys/types.h")}, lang


def test_a_bare_quoted_name_keeps_its_basename_fallback():
    for lang, ext in _IMPORTERS:
        files = {"include/curl/types.h": "int a;\n", f"ares/a.{ext}": '#include "types.h"\n'}
        assert _edges_from(lang, ext, files) == {(f"ares/a.{ext}", "include/curl/types.h")}, lang
