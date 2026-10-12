"""System / standard-library header names the typosquat radar must never test (#4547).

A header is a file path the toolchain supplies, not a package a registry
distributes, so `strings.h` sitting one edit from `string.h` is two real
headers, not a dependency-confusion attempt. The radar (galaxyscope.py,
"AIR-GAPPED TYPOSQUATTING RADAR") asks `is_system_header()` about both sides
of a candidate pair and skips the pair when either is one.

Families: C99/C11 standard, POSIX, C++ standard library (extensionless and the
`c`-prefixed C wrappers), MSVC STL internals, Win32/DirectX, OpenGL/GLX,
compiler intrinsics, and the platform directories (`sys/`, `linux/`, ...).
"""

from __future__ import annotations

import re

_C_STD = [
    "assert",
    "complex",
    "ctype",
    "errno",
    "fenv",
    "float",
    "inttypes",
    "iso646",
    "limits",
    "locale",
    "math",
    "setjmp",
    "signal",
    "stdalign",
    "stdarg",
    "stdatomic",
    "stdbool",
    "stddef",
    "stdint",
    "stdio",
    "stdlib",
    "stdnoreturn",
    "string",
    "strings",
    "tgmath",
    "threads",
    "time",
    "uchar",
    "wchar",
    "wctype",
    "malloc",
    "alloc",
    "memory",
]

_POSIX = [
    "aio",
    "arpa/inet",
    "cpio",
    "dirent",
    "dlfcn",
    "fcntl",
    "fmtmsg",
    "fnmatch",
    "ftw",
    "glob",
    "grp",
    "iconv",
    "langinfo",
    "libgen",
    "monetary",
    "mqueue",
    "ndbm",
    "netdb",
    "nl_types",
    "poll",
    "pthread",
    "pwd",
    "regex",
    "sched",
    "search",
    "semaphore",
    "spawn",
    "strings",
    "stropts",
    "syslog",
    "tar",
    "termios",
    "trace",
    "ulimit",
    "unistd",
    "utime",
    "utmpx",
    "wordexp",
    "getopt",
    "endian",
    "byteswap",
    "alloca",
]

_WIN32 = [
    "windows",
    "windowsx",
    "winsock",
    "winsock2",
    "ws2tcpip",
    "wsipx",
    "winbase",
    "wincon",
    "wingdi",
    "winuser",
    "winnt",
    "winerror",
    "winreg",
    "winternl",
    "winsvc",
    "winioctl",
    "commctrl",
    "commdlg",
    "shellapi",
    "shlobj",
    "shlwapi",
    "objbase",
    "ole2",
    "oleauto",
    "mmsystem",
    "mmreg",
    "dsound",
    "dinput",
    "direct",
    "io",
    "process",
    "conio",
    "tchar",
    "xinput",
    "xaudio2",
    "d2d1",
    "dwrite",
    "dxgi",
    "wincrypt",
    "wininet",
    "winhttp",
    "psapi",
    "tlhelp32",
    "sddl",
    "aclapi",
    "lmcons",
    "iphlpapi",
    "mswsock",
    "mstcpip",
    "rpc",
    "rpcdce",
    "excpt",
    "crtdbg",
    "malloc",
    "sys/timeb",
    "sys/utime",
]

_CPP_STD = [
    "algorithm",
    "any",
    "array",
    "atomic",
    "barrier",
    "bit",
    "bitset",
    "charconv",
    "chrono",
    "codecvt",
    "compare",
    "complex",
    "concepts",
    "condition_variable",
    "coroutine",
    "deque",
    "exception",
    "execution",
    "expected",
    "filesystem",
    "format",
    "forward_list",
    "fstream",
    "functional",
    "future",
    "generator",
    "initializer_list",
    "iomanip",
    "ios",
    "iosfwd",
    "iostream",
    "istream",
    "iterator",
    "latch",
    "limits",
    "list",
    "locale",
    "map",
    "mdspan",
    "memory",
    "memory_resource",
    "mutex",
    "new",
    "numbers",
    "numeric",
    "optional",
    "ostream",
    "print",
    "queue",
    "random",
    "ranges",
    "ratio",
    "regex",
    "scoped_allocator",
    "semaphore",
    "set",
    "shared_mutex",
    "source_location",
    "span",
    "spanstream",
    "sstream",
    "stack",
    "stacktrace",
    "stdexcept",
    "stop_token",
    "streambuf",
    "string",
    "string_view",
    "strstream",
    "syncstream",
    "system_error",
    "thread",
    "tuple",
    "type_traits",
    "typeindex",
    "typeinfo",
    "unordered_map",
    "unordered_set",
    "utility",
    "valarray",
    "variant",
    "vector",
    "version",
]

# MSVC STL internals (`#include <xstring>`) -- never written by the user.
_MSVC_STL = [
    "xstring",
    "xmemory",
    "xutility",
    "xtree",
    "xlocale",
    "xlocinfo",
    "xlocnum",
    "xiosbase",
    "xfacet",
    "xtr1common",
    "xcall_once",
]

_X = {f"{n}.h" for n in _C_STD + _POSIX + _WIN32}
_X |= {f"c{n}" for n in _C_STD if n not in ("alloc", "memory", "strings", "malloc", "threads")}
_NAMES = frozenset(_X) | frozenset(_CPP_STD) | frozenset(_MSVC_STL) | {"xmmintrin.h", "emmintrin.h"}
_NAMES_LOWER = frozenset(n.lower() for n in _NAMES)

# Directories whose every member is the platform's own header.
_SYSTEM_DIRS = frozenset(
    {
        "sys",
        "linux",
        "asm",
        "asm-generic",
        "bits",
        "arpa",
        "netinet",
        "net",
        "netpacket",
        "rpc",
        "scsi",
        "mach",
        "gl",
        "glx",
        "egl",
        "gles",
        "gles2",
        "gles3",
        "vulkan",
        "x11",
        "cuda",
    }
)

# *mmintrin.h (MMX/SSE), *intrin.h (x86intrin, immintrin, arm_neon via arm_*.h), d3d*/dxgi*.h, gl*.h.
_FAMILY = re.compile(
    r"^(?:[a-z0-9]*mmintrin|[a-z0-9]*intrin|arm_[a-z0-9_]+|d3d[0-9a-z_]*|dxgi[0-9a-z_]*|gl[0-9a-z_]*|glu|glut|glx)\.h$",
    re.IGNORECASE,
)


# Importer extensions whose bare (extensionless) `#include <string>` names a C++ standard header; in any
# other language `string` / `format` / `version` is a module or package name and stays eligible.
C_FAMILY_EXTENSIONS = frozenset(
    [
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".cxx",
        ".c++",
        ".hpp",
        ".hh",
        ".hxx",
        ".h++",
        ".inl",
        ".ipp",
        ".tpp",
        ".ixx",
        ".cppm",
        ".m",
        ".mm",
        ".cu",
        ".cuh",
        ".ino",
        ".pde",
    ]
)

HEADER_EXTENSIONS = (".h", ".hh", ".hpp", ".hxx", ".h++")


def is_system_header(token: str, importer_ext: str = "") -> bool:
    """True when `token` names a platform / standard-library header (case-insensitive).

    `importer_ext` is the importing file's extension: the extensionless C++ names only count from a C-family
    importer. A token spelled with a header extension is a file path in every language, never a package name.
    """
    t = token.strip().strip("<>\"'").replace("\\", "/").lower()
    if not t:
        return False
    cfam = importer_ext.lower() in C_FAMILY_EXTENSIONS
    if t in _NAMES_LOWER and (cfam or t.endswith(".h")):
        return True
    parts = t.split("/")
    base = parts[-1]
    if len(parts) > 1 and parts[0] in _SYSTEM_DIRS and (base.endswith(".h") or "." not in base):
        return True
    if len(parts) > 1 and f"{parts[-2]}/{base}" in _NAMES_LOWER and base.endswith(".h"):
        return True
    return bool(_FAMILY.match(base)) and (len(parts) == 1 or parts[0] in _SYSTEM_DIRS)
