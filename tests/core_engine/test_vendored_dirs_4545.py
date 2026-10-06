"""#4545: vendored copies of other projects are excluded under every common spelling.

`third_party/` always was. The other spellings are excluded by name; `*.framework` by suffix;
`libraries/`-style containers and versioned directories (`SDL2-2.32.10/`) only on evidence of a
separate project (a license of their own that differs from the scan root's). Shapes are taken from
the Doom source-port study (woof, gzdoom, doomretro, linuxdoom).
"""

import pytest

from gitgalaxy.core.aperture import ApertureFilter, VendorDirectoryDetector
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

GPL = "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n"
ZLIB = "This software is provided 'as-is', without any express or implied warranty.\n"
MIT = "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
CODE = "int f(void) { return 0; }\n"


def _write(path, text=CODE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _admitted(root, rel):
    f = _write(root / rel) if not (root / rel).exists() else root / rel
    return ApertureFilter(root, LANGUAGE_DEFINITIONS, APERTURE_CONFIG).evaluate_path_integrity(f)[0]


@pytest.fixture
def repo(tmp_path):
    _write(tmp_path / "LICENSE", GPL)
    _write(tmp_path / "src/main.c")
    return tmp_path


# --- by name ------------------------------------------------------------------
@pytest.mark.parametrize("name", ["third_party", "third-party", "thirdparty", "3rdparty", "3rd_party", "vendored"])
def test_third_party_spellings_are_excluded(repo, name):
    assert not _admitted(repo, f"{name}/miniz/miniz.c")
    assert not _admitted(repo, f"src/common/{name}/md5.cpp")


def test_framework_bundle_is_excluded(repo):
    assert not _admitted(repo, "xcode/SDL2.framework/Headers/SDL.h")


def test_first_party_lookalike_names_stay_scanned(repo):
    for rel in ("src/party/third.c", "src/thirdperson.c", "src/framework/app.c", "src/vendors/list.c"):
        assert _admitted(repo, rel), rel


# --- versioned directories -----------------------------------------------------
def test_versioned_library_with_its_own_license_is_excluded(repo):
    _write(repo / "SDL2-2.32.10/LICENSE.txt", ZLIB)
    _write(repo / "SDL2_mixer-2.8.2/LICENSE.txt", ZLIB)
    assert not _admitted(repo, "SDL2-2.32.10/include/SDL_opengl_glext.h")
    assert not _admitted(repo, "SDL2_mixer-2.8.2/include/SDL_mixer.h")


def test_versioned_first_party_tree_without_a_license_stays_scanned(repo):
    # id Software's DOOM repo: linuxdoom-1.10/ is the game; LICENSE.TXT sits at the root
    assert _admitted(repo, "linuxdoom-1.10/am_map.c")


def test_versioned_tree_carrying_the_roots_license_stays_scanned(repo):
    _write(repo / "mygame-2.1/LICENSE", GPL)
    assert _admitted(repo, "mygame-2.1/main.c")


def test_no_root_license_means_no_evidence(tmp_path):
    # the only license in the repo may be the repo's own, kept in a versioned subdir
    _write(tmp_path / "proj-1.2.3/LICENSE", MIT)
    assert _admitted(tmp_path, "proj-1.2.3/main.c")


# --- generic containers --------------------------------------------------------
def test_libraries_holding_separate_projects_is_excluded(repo):
    _write(repo / "libraries/bzip2/LICENSE", "bzip2 license\n")
    _write(repo / "libraries/ZVulkan/LICENSE.md", MIT)
    _write(repo / "libraries/ZMusic/licenses/gpl.txt", GPL)
    _write(repo / "libraries/miniz/miniz.c")  # unlicensed member of a vendor container
    assert not _admitted(repo, "libraries/bzip2/bzlib.c")
    assert not _admitted(repo, "libraries/miniz/miniz.c")
    assert not _admitted(repo, "libraries/ZMusic/source/zmusic.cpp")


@pytest.mark.parametrize("name", ["libs", "deps", "extern", "external"])
def test_other_container_names_follow_the_same_rule(repo, name):
    _write(repo / f"{name}/fmt/LICENSE", MIT)
    assert not _admitted(repo, f"{name}/fmt/src/format.cc")


def test_first_party_libs_stay_scanned(repo):
    # Nx-style workspace: libs/ holds the repo's own packages (no license, or the root's)
    _write(repo / "libs/core/src/core.c")
    _write(repo / "libs/ui/LICENSE", GPL)
    _write(repo / "libs/net/net.c")
    assert _admitted(repo, "libs/core/src/core.c")
    assert _admitted(repo, "libs/ui/widget.c")


def test_one_vendored_lib_does_not_take_a_mostly_first_party_container(repo):
    _write(repo / "libs/a/a.c")
    _write(repo / "libs/b/b.c")
    _write(repo / "libs/c/c.c")
    _write(repo / "libs/zlib/LICENSE", ZLIB)
    assert _admitted(repo, "libs/a/a.c")


def test_container_without_subprojects_stays_scanned(repo):
    # doom64ex extern/: build glue and one patched header, no subproject
    _write(repo / "extern/CMakeLists.txt", "add_library(x)\n")
    assert _admitted(repo, "extern/patched-config_win32.h")


def test_scan_root_is_never_a_candidate(tmp_path):
    root = tmp_path / "SDL2-2.32.10"
    _write(root / "LICENSE.txt", ZLIB)
    _write(root / "third/LICENSE", MIT)
    assert _admitted(root, "src/SDL.c")
    assert not VendorDirectoryDetector(root).is_vendored("")
