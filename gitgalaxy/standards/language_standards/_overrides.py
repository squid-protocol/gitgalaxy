# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re

PROJECT_OVERRIDES = {
    "freebsd-src": {
        "objective-c": {"extensions": [".mm", ".h"]},
        "c": {
            "extensions": [
                ".c",
                ".h",
                ".cl",
                ".inc",
                ".y",
                ".idc",
                ".cats",
                ".m",
                ".dts",
                ".dtsi",
            ]
        },
    },
    "wrf-fortran": {
        "_shield_": {"unban_directories": ["var", "external", "test"]},
        "fortran": {
            "concurrency": re.compile(
                r"\b(COARRAY|SYNC\s+ALL|CRITICAL|MPI_[A-Za-z_]+|wrf_dm[A-Za-z0-9_]*|RSL[A-Za-z0-9_]*)\b|!\$(?:OMP|ACC)\b",
                re.I,
            )
        },
    },
    "Apollo-11": {
        "agc_assembly": {
            "_meta_purpose_block": re.compile(r"^[ \t]*(?:FUNCTIONAL|PROGRAM)\s+DESCRIPTION\b", re.I),
            "_meta_purpose_line": re.compile(r"^[ \t]*Purpose[\s:\-]*(.*)", re.I),
            "_meta_boundary": re.compile(
                r"^[ \t]*(?:Assembler|Filename|Pages|Website|Mod history|Copyright|Reference|PROGRAM NAME)[\s:\-]+",
                re.I,
            ),
        }
    },
    "cpython": {
        "_shield_": {
            "exclude_paths": ["Lib/pydoc_data/topics.py", "configure"],
            "exclude_dirs": ["Modules/clinic"],
        }
    },
    "AppFlowy": {
        "_shield_": {
            "exclude_dirs": ["scripts", "integration_test"],
            "exclude_paths": ["install.sh"],
        }
    },
    "ansible": {"_shield_": {"exclude_dirs": [".azure-pipelines", ".github"]}},
    "bugzilla": {
        "html": {
            "extensions": [
                ".html",
                ".htm",
                ".xhtml",
                ".cshtml",
                ".vue",
                ".svelte",
                ".astro",
                ".ejs",
                ".hbs",
                ".twig",
                ".erb",
                ".tmpl",
            ]
        }
    },
    "bun": {"_shield_": {"exclude_dirs": ["scripts"]}},
    "curl": {
        "plaintext": {
            "extensions": [
                ".txt",
                ".text",
                ".log",
                ".out",
                ".err",
                ".nfo",
                ".1",
                ".3",
                ".d",
            ]
        }
    },
    "discourse": {
        "_shield_": {"exclude_paths": ["config/unicorn_launcher", "pnpm-lock.yaml", "yarn.lock"]},
        "javascript": {"extensions": [".js", ".jsx", ".mjs", ".cjs", ".gjs"]},
    },
    "elasticsearch": {"plaintext": {"extensions": [".txt", ".text", ".log", ".json", ".yaml", ".yml"]}},
    "exiftool": {"plaintext": {"extensions": [".txt", ".text", ".out", ".args", ".fmt", ".xmp"]}},
    "express": {"html": {"extensions": [".html", ".htm", ".ejs", ".tmpl"]}},
    "fieldtrip": {"_shield_": {"exclude_dirs": ["external"]}},
    "jenkins": {"_shield_": {"exclude_paths": ["translation-tool.pl", "core/report-l10n.rb"]}},
    "redis": {"_shield_": {"exclude_dirs": ["deps/lua", "deps/jemalloc", "deps/hiredis"]}},
}
