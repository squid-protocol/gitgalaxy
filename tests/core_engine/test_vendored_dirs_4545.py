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
    # an extern/ of build glue and one patched header, no subproject
    _write(repo / "extern/CMakeLists.txt", "add_library(x)\n")
    assert _admitted(repo, "extern/patched-config_win32.h")


def test_scan_root_is_never_a_candidate(tmp_path):
    root = tmp_path / "SDL2-2.32.10"
    _write(root / "LICENSE.txt", ZLIB)
    _write(root / "third/LICENSE", MIT)
    assert _admitted(root, "src/SDL.c")
    assert not VendorDirectoryDetector(root).is_vendored("")


# --- #5464: vendored trees under any name --------------------------------------
@pytest.mark.parametrize(
    "name", ["third_party_libs", "third-party-libs", "thirdparty_src", "3rdparty-code", "3rd_party_lib"]
)
def test_third_party_prefix_spellings_are_excluded_without_a_license(repo, name):
    # a third_party_libs/libsdl/sdl2 tree (367k lines)
    assert not _admitted(repo, f"{name}/libsdl/sdl2/src/SDL.c")


def test_third_party_lookalikes_stay_scanned(repo):
    for rel in ("src/third_person/cam.c", "src/thirdparty.c", "src/party_hall/a.c", "src/third_partyish/a.c"):
        assert _admitted(repo, rel), rel


def test_libs_suffix_container_follows_the_container_rule(repo):
    _write(repo / "ext_libs/png/LICENSE", ZLIB)
    _write(repo / "ext_libs/zlib/zlib.c")
    assert not _admitted(repo, "ext_libs/png/png.c")
    assert not _admitted(repo, "ext_libs/zlib/zlib.c")
    # no license evidence: a first-party `*_libs` stays scanned
    _write(repo / "game_libs/net/net.c")
    assert _admitted(repo, "game_libs/net/net.c")


@pytest.mark.parametrize(
    "rel", ["libpng/png.c", "src/yyjson/yyjson.c", "game-music-emu/gme.cpp", "src/deep/miniz/miniz.c"]
)
def test_any_directory_with_a_foreign_license_is_excluded(repo, rel):
    top = rel.rsplit("/", 1)[0]
    _write(repo / top / "LICENSE", MIT)
    assert not _admitted(repo, rel)


def test_directory_with_the_roots_license_or_none_stays_scanned(repo):
    # srb2 `src/sdl/`, odamex `client/sdl/`: first-party backends
    _write(repo / "src/sdl/i_video.c")
    _write(repo / "client/sdl/mixer.cpp")
    _write(repo / "src/own/LICENSE", GPL)
    assert _admitted(repo, "src/sdl/i_video.c")
    assert _admitted(repo, "client/sdl/mixer.cpp")
    assert _admitted(repo, "src/own/a.c")


def test_foreign_license_is_no_evidence_without_a_root_license(tmp_path):
    _write(tmp_path / "somelib/LICENSE", ZLIB)
    assert _admitted(tmp_path, "somelib/a.c")


def test_detector_flags_the_directory_not_its_siblings(repo):
    _write(repo / "lzma/LICENSE", MIT)
    assert VendorDirectoryDetector(repo).is_vendored("lzma")
    assert not VendorDirectoryDetector(repo).is_vendored("src")


def test_same_license_with_another_copyright_or_address_is_not_foreign(repo):
    # fastdoom: FASTDOOM/LICENSE is the root's GPL-2 with a different FSF address and copyright line
    _write(repo / "game/LICENSE", GPL + "Copyright (C) 1989 Someone\n675 Mass Ave, Cambridge, MA 02139, USA\n")
    assert _admitted(repo, "game/main.c")


# --- #5464 (c): well-known library names with no license file ---------------------
@pytest.mark.parametrize(
    "rel",
    ["zlib/inflate.c", "neo/renderer/jpeg-6/jdapimin.c", "lzma/LzmaDec.c", "gdtoa/dtoa.c", "source/nlohmann/json.hpp"],
)
def test_known_library_names_are_excluded_without_a_license(repo, rel):
    assert not _admitted(repo, rel)


def test_known_library_name_needs_the_exact_name(repo):
    for rel in ("src/zlib_wrapper/a.c", "src/jpeg_export/a.c", "src/lzmaish/a.c", "src/zlibs/a.c"):
        assert _admitted(repo, rel), rel


def test_known_library_name_with_the_roots_own_license_stays_scanned(repo):
    _write(repo / "zlib/LICENSE", GPL)
    assert _admitted(repo, "zlib/own.c")


def test_versioned_known_library_name_is_excluded(repo):
    assert not _admitted(repo, "zlib-1.2.11/adler32.c")


# --- #5525: a title line above the same license text is not a different license ---
APACHE = "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/\n\nTERMS AND CONDITIONS\n"
TITLES = ["Google Gson\n\n", "My Module\n=========\n\n", "Project Foo\nSub-module bar\n\n", "# Core\n"]


@pytest.mark.parametrize("title", TITLES)
@pytest.mark.parametrize("base", [APACHE, GPL, MIT])
def test_titled_module_license_is_not_foreign(tmp_path, base, title):
    _write(tmp_path / "LICENSE", base)
    _write(tmp_path / "gson/LICENSE", title + base)
    _write(tmp_path / "gson/a.c")
    assert not VendorDirectoryDetector(tmp_path).is_vendored("gson")
    assert _admitted(tmp_path, "gson/a.c")


@pytest.mark.parametrize("title", TITLES)
def test_titled_root_license_with_bare_module_copy_is_not_foreign(tmp_path, title):
    _write(tmp_path / "LICENSE", title + APACHE)
    _write(tmp_path / "mod/LICENSE", APACHE)
    assert not VendorDirectoryDetector(tmp_path).is_vendored("mod")


def test_titled_copy_with_copyright_and_address_changes_is_not_foreign(tmp_path):
    _write(tmp_path / "LICENSE", GPL)
    _write(tmp_path / "m/LICENSE", "Game Title\nCopyright (C) 1989 Someone\n" + GPL + "675 Mass Ave\n")
    assert not VendorDirectoryDetector(tmp_path).is_vendored("m")


def test_titled_different_license_is_still_foreign(tmp_path):
    _write(tmp_path / "LICENSE", APACHE)
    _write(tmp_path / "libfoo/LICENSE", "libfoo\n\n" + MIT)
    assert VendorDirectoryDetector(tmp_path).is_vendored("libfoo")


def test_licenses_dir_and_empty_license_are_still_foreign(tmp_path):
    _write(tmp_path / "LICENSE", APACHE)
    _write(tmp_path / "a/licenses/x.txt", MIT)
    _write(tmp_path / "b/LICENSE", "")
    detector = VendorDirectoryDetector(tmp_path)
    assert detector.is_vendored("a")
    assert detector.is_vendored("b")


def test_container_of_titled_root_license_modules_stays_scanned(tmp_path):
    _write(tmp_path / "LICENSE", APACHE)
    for m in ("one", "two"):
        _write(tmp_path / "libs" / m / "LICENSE", f"Module {m}\n\n" + APACHE)
        _write(tmp_path / "libs" / m / "a.c")
    assert not VendorDirectoryDetector(tmp_path).is_vendored("libs")


def test_known_library_name_with_titled_root_license_stays_scanned(tmp_path):
    _write(tmp_path / "LICENSE", APACHE)
    _write(tmp_path / "zlib/LICENSE", "Zlib wrapper\n" + APACHE)
    assert not VendorDirectoryDetector(tmp_path).is_vendored("zlib")
