# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The shipped library table for `gitgalaxy libsurface`: the libraries whose API names discovery cannot supply.

Discovery (libsurface.py) finds every external library from the imports and includes a scan already stores. What it cannot find is a
library reached through a wrapper header: files call `SSL_new` without including `openssl/ssl.h`. A library listed here adds glob patterns
for the names it exports. On 19 (repository, library) pairs in C and C++ the names carry real signal: includes alone beat a size ranking by
+0.253 recall@20 but lose to includes plus names by -0.136 (temporal-crucible, docs/sensor-overhaul/sensors/library_surface.md).

`include` globs match an include or import string (`openssl/*`, `zlib.h`); `calls` globs match a called external name (`SSL_*`). Globs, not
regexes: a pattern a user writes cannot hang the matcher. Keep `calls` strict: a loose pattern (`g_*`) attaches calls to the wrong library.
A user adds to or replaces any entry by name in a TOML file (see libsurface.py).
"""

from __future__ import annotations

_C_FAMILY = ["c", "cpp"]


def _lib(name: str, include: list[str], calls: list[str]) -> dict:
    return {"name": name, "languages": list(_C_FAMILY), "include": include, "calls": calls}


DEFAULT_LIBRARIES: list[dict] = [
    _lib(
        "openssl",
        ["openssl/*"],
        ["SSL_*", "EVP_*", "X509_*", "BIO_*", "ERR_*", "PEM_*", "RSA_*", "EC_KEY_*", "BN_*", "OPENSSL_*"],
    ),
    _lib("zlib", ["zlib.h"], ["inflate*", "deflate*"]),
    _lib("libssh2", ["libssh2*"], ["libssh2_*"]),
    _lib("nghttp2", ["nghttp2/*"], ["nghttp2_*"]),
    _lib("c-ares", ["ares.h"], ["ares_*"]),
    _lib("wolfssl", ["wolfssl/*"], ["wolfSSL_*"]),
    _lib("mbedtls", ["mbedtls/*"], ["mbedtls_*"]),
    _lib("gnutls", ["gnutls/*"], ["gnutls_*"]),
    _lib("libidn2", ["idn2.h"], ["idn2_*"]),
    _lib("bzip2", ["bzlib.h"], ["BZ2_*"]),
    _lib("xz", ["lzma.h"], ["lzma_*"]),
    _lib("zstd", ["zstd.h"], ["ZSTD_*"]),
    _lib("lz4", ["lz4*"], ["LZ4*_*"]),
    _lib("libpcap", ["pcap*"], ["pcap_*"]),
    _lib("freetype", ["ft2build.h", "freetype/*"], ["FT_*"]),
    _lib("icu", ["unicode/*"], ["u_*", "ubrk_*", "uscript_*", "unorm_*", "unorm2_*"]),
    _lib("coretext", ["CoreText*"], ["CT*"]),
    _lib("uniscribe", ["usp10.h"], ["Script*"]),
    _lib("graphite", ["graphite2/*"], ["gr_*"]),
    _lib("glib", ["glib*"], ["g_*"]),
]
