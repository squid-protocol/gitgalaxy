# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `ownership` contract (#2882, docs/ownership_rule_contract.md), held across
every corpus language in one place.

    One hit is a tag naming who is responsible for the unit -- an author,
    creator, maintainer, owner, developer or contact -- with its value, in the
    form the language's tooling or header convention reads as metadata: a
    doc-comment tag, a keyed header line, or the language's own metadata field.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
audit found the old rules disagreeing on:

  C1 the tag, not the word: `@author X`, `Author: X`, `__author__ = X`,
     `MAINTAINER X`, `author: X`, `<meta name="author">`. The keyed form is
     anchored to the start of a comment line and needs its separator; prose
     carrying the words (`created by the renderer`, `owner as the given
     ReplicaSet`) is not a hit, nor is a field or annotation named `owner:`,
     nor a person's name as a rule (`Tim Berners-Lee`). The one colon-less
     keyed form kept is Xcode's dated template (`//  Created by X on <date>`).
  C2 rights are not responsibility: a license identifier
     (`SPDX-License-Identifier`, `License:`, `=head1 LICENSE`) and a copyright
     notice (`Copyright (c) 2014 X`, `SPDX-FileCopyrightText`, `AC_COPYRIGHT`,
     the keyed `Copyright:`) count in no form. A version tag (`@since`) is
     not ownership either.
  C3 one tag is one hit, and the value is the name: every alternative
     captures, because the detector's ghost meta reads the last group as the
     file's dominant author (an alternative with no group made the tag text
     itself the author).
  C4 one owner: the author tag is ownership's; `doc` counts the block, never
     the tag (assembly, cobol `*> @author`, css, dockerfile `LABEL maintainer=`
     and `# Author:`, haskell `-- @author`, solidity's bare `@author` released).
  C5 absence: markdown has no comment surface and no metadata field; the rule
     stays unset (n/a), no fallback family is manufactured.

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `CAPTURES` pins C3's value, `COUNTS`
one-tag-one-hit, `DUALS` the C2/C4 tokens that belong to another signal or to
none.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="ownership"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


LICENSE_PROSE = [
    " * The above copyright notice and this permission notice shall be included in",
    " * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER",
]

# lang -> (positives, negatives)
CASES = {
    # --- C2: rights are not responsibility ------------------------------------------
    "solidity": (
        ["/// @author Jane Doe", "// Author: Jane Doe", "// Maintainer: Jane Doe"],
        ["// SPDX-License-Identifier: MIT", "// SPDX-FileCopyrightText: 2024 Acme", "pragma solidity ^0.8.0;"],
    ),
    "c": (
        [
            "// @author Jane",
            " * \\author Jane Doe",
            "/* Author: Jane */",
            "   Author: John Doe",
            " * Contact: jane@x.org",
        ],
        [" * Copyright (c) 2013 Damien P. George", "// Copyright (C) 1993-1996 by id Software, Inc.", *LICENSE_PROSE],
    ),
    "cpp": (
        ["// @author Jane", "/* Author: Jane */", "// Owner: Jane Doe"],
        [
            "/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */",
            "Author::Author() {}",
            *LICENSE_PROSE,
        ],
    ),
    "yacc": (["/* @author Jane */", "// Author: Jane"], [" * Copyright (c) 1988, 1993", *LICENSE_PROSE]),
    "shell": (
        [
            "# Author: Will Deacon <will.deacon@arm.com>",
            "# Created by:\tNicolas Pitre, August 2017",
            "# Maintainer: Jane",
        ],
        [
            "# Copyright 2017 The Kubernetes Authors.",
            "# Copyright (C) Daniel Stenberg, <daniel@haxx.se>, et al.",
            "#\tCopyright (c) 1984 AT&T",
        ],
    ),
    "m4": (
        ["dnl Author: Jane Doe", "# Maintainer: Jane Doe"],
        ["AC_COPYRIGHT([Copyright (C) 2026 Jane Doe])", "dnl License: GPL"],
    ),
    "haskell": (
        [
            "-- Author: Jane Doe",
            "-- Maintainer  :  libraries@haskell.org",
            "Maintainer  : John MacFarlane <jgm@berkeley.edu>",
            "-- @author Jane",
        ],
        ["-- License: BSD3", "-- Copyright: (c) 2010 Jane", "-- Authorized by"],
    ),
    "lua": (["-- Author: Jane Doe", "---@author Jane Doe"], ["-- License: MIT", "-- Copyright: 2020 Jane"]),
    "perl": (["# Author: Jane Doe", "=head1 AUTHORS\n\nJane Doe <j@x>"], ["=head1 COPYRIGHT", "=head1 LICENSE"]),
    "php": (
        ["/** @author Fabien Potencier <fabien@symfony.com> */", "// Created by: Jane"],
        ["@copyright 2020 Jane", "// Copyright (c) 2020 Jane"],
    ),
    "kotlin": (["@author Jane Doe", "// Created by: Jane Doe"], ["@since 1.2", "// Copyright: 2020 Jane"]),
    # --- C1: the tag, not the word ---------------------------------------------------
    "typescript": (
        [" * @author Jane Doe", "// Maintainer: Jane", "   Author: Jane Doe"],
        [
            " * created by the extension.",
            "// The node is an IIFE class wrapper created by the ts transform.",
            "  author: CommentAuthorInformation;",
            "Author: Jane {",
        ],
    ),
    "javascript": (
        ["// @author Jane Doe", "// Author: Jane"],
        [
            "// was created by an older render.",
            " * A canvas where the renderer draws its output. This is automatically created by the renderer",
            "  owner: task.debugOwner,",
            "  owner: null | ReactComponentInfo,",
        ],
    ),
    "csharp": (
        ["/// <author>Jane Doe</author>", "// Created by: Jane Doe", "// Author: Jane"],
        [
            "/// Get a ModuleSymbol that refers to the module being created by compiling all of the code.",
            "// Created by keyword-rosetta generator",
        ],
    ),
    "go": (
        ["// Owner: Jane Doe", "// Author: Jane"],
        ["// owner as the given ReplicaSet.", "    Owner: owner,", "// Authorized by"],
    ),
    "python": (
        [
            '__author__ = "Jane Doe"',
            ".. moduleauthor:: Pierre Gerard-Marchant",
            ":author: Pierre Gerard-Marchant",
            "# Author: Jane",
            "Maintainer: Glyph Lefkowitz",
        ],
        [
            "owner: UserDB",
            "owner: Mapped[str] = mapped_column(String(500))",
            "contact: Annotated[",
            "authorized = True",
        ],
    ),
    "embedded_python": (['__author__ = "Jane Doe"', "# Author: Jane"], ["owner: User", "author_note = 1"]),
    "zig": (["// Author: Jane", "//! Maintainer: Jane"], ["    owner: *Package.Module,", "Owner: x,"]),
    "dart": (["// Author: Jane Doe", "/// @author Jane"], ["      owner: owner.renderObject.owner!.semanticsOwner!,"]),
    "objective-c": (
        ["// @author Jane Doe", "//  Created by Joe Esquibel on 9/8/26.", "// Author: Jane"],
        [
            "// TBL\t\tTim Berners-Lee CERN/CN",
            "// Reviewed by: Jane Doe",
            "// Copyright (c) 2020 Apple Inc.",
            "// Created by keyword-rosetta generator",
        ],
    ),
    "swift": (
        ["/// - Author: Jane Doe", "// Created by: Jane Doe", "//  Created by Joe on 1/2/20."],
        ["// Reviewed by: Jane Doe", "// Copyright © 2020 Apple"],
    ),
    "abap": (["* AUTHOR: Jane Doe", '" Maintainer: Jane'], ["* Tim Berners-Lee", "AUTHORITY-CHECK OBJECT 'X'"]),
    "apex": (["/** @author Joe */", "// Author: Jane"], ["the Author of this module", "// Tim Berners-Lee"]),
    "scala": (["/** @author Jane Doe */", "// Created by: Jane"], ["// Copyright: 2026 Acme", "// Tim Berners-Lee"]),
    "fortran": (
        ["!Author: Jane Doe", "   ! Author: Jane Doe", "C Author: Jane Doe", "! Developer: Jane"],
        ["! authored 2020", "      CALL AUTHOR(x)"],
    ),
    "cobol": (
        ["       AUTHOR. Jane Doe.", "      *> @author Jane", "      * Author     : ALDV"],
        ["       AUTHORIZED-USER PIC X.", "      * just a note"],
    ),
    "matlab": (
        ["% Author: Jane Doe", "% Authors: Arnaud Delorme and Scott Makeig"],
        ["% Copyright: 2020 Jane", "% authored in 2005"],
    ),
    # --- the metadata-field forms --------------------------------------------------------
    "dockerfile": (
        [
            "MAINTAINER Jane Doe",
            'LABEL maintainer="jane@x.org"',
            'LABEL org.opencontainers.image.authors="Jane"',
            "# Maintainer: @jhowardmsft",
        ],
        ["LABEL description=x", "# Usage: docker build ."],
    ),
    "yaml": (
        ["author: Jane Doe <jane@example.com>", "contact:\n  email: support@example.com\n"],
        ["name: My Job", "author_note: x", "contact_form: https://x/contact\n"],
    ),
    "html": (
        ['<meta name="author" content="Jane Doe">', "<!-- Author: Jane -->", '<link rev="made" href="mailto:j@x">'],
        ['<meta name="viewport" content="x">', "<p>Created by the team</p>"],
    ),
    "agc_assembly": (
        ["# MOD BY - GAUNTT", "# Contact:\tRon Burkey <info@sandroid.org>.", "# AUTHOR: J S MILLER"],
        ["# THIS IS THE RESUME ROUTINE", "\tTC\tAUTHOR"],
    ),
    "powershell": (
        ["# Author: Jane Doe", ".AUTHOR Jane Doe", "Maintainer: PowerShell Team <x@y>"],
        ["# Reviewed by: Jane Doe", "$author = 'x'"],
    ),
    "css": (
        ["/* Author: keyword-rosetta corpus */", "/* @author Jane Doe */"],
        ["/** @param --color The theme color */", "/* just a note */"],
    ),
    "sqlite": (
        ["-- Author: Jane Doe", " * @author Qiang Xue <qiang.xue@gmail.com>"],
        ["-- Copyright: 2020 Jane", "SELECT author FROM books;"],
    ),
    "scheme": (
        [";;; Authors: R. Kent Dybvig, Oscar Waddell", ";; Author: Jane"],
        [";; Copyright: 2020 Jane", "(define author 1)"],
    ),
    "java": (["/** @author Phillip Webb */", "// Maintainer: Jane"], ["// Written by Jane Doe", "String author = x;"]),
    "groovy": (["/** @author Peter Niederwieser */", "// Author: Jane"], ["def author = 'x'"]),
    "rust": (["// Author: Jane", "//! Maintainer: Jane"], ["// Copyright: 2020 Jane", "let owner = x;"]),
    "ruby": (["# Author: Jane Doe", "# @author Jane"], ["# Copyright: 2020 Jane", "author = 'x'"]),
    "tcl": (["# Author: Jane Doe"], ["# Copyright: 2020 Jane", "set author x"]),
    "jcl": (["//* Author: Jane Doe"], ["//* Copyright: 2020 Jane", "//STEP1 EXEC PGM=AUTHOR"]),
    "livecode": (["-- Author: Jane Doe", "# Maintainer: Jane"], ["-- Copyright: 2020 Jane", "put author into x"]),
    "makefile": (
        ["# author: keyword-rosetta generator", "# Maintainer: Jane"],
        ["# Copyright: 2020 Jane", "AUTHOR := x", "AUTHOR:=x", "OWNER = me"],
    ),
    "ada": (["-- Author: Jane Doe"], ["-- Copyright: 2020 Jane", "Author : String;"]),
    "assembly": (["; Author: Jane Doe", "; @author Jane"], ["; Copyright: 2020 Jane", "author db 0"]),
}

# (lang, text, expected value): C3 -- the last group is the name
CAPTURES = [
    ("solidity", "/// @author Jane Doe", "Jane Doe"),
    ("css", "/* Author: keyword-rosetta corpus */", "keyword-rosetta corpus"),
    ("html", "<!-- Author: Jane -->", "Jane"),
    ("html", '<link rev="made" href="mailto:j@x">', "j@x"),
    ("haskell", "-- Maintainer  :  libraries@haskell.org", "libraries@haskell.org"),
    ("objective-c", "//  Created by Joe Esquibel on 9/8/26.", "Joe Esquibel"),
    ("python", ".. moduleauthor:: Pierre Gerard-Marchant", "Pierre Gerard-Marchant"),
    ("perl", "=head1 AUTHORS\n\nJane Doe <j@x>", "Jane Doe <j@x>"),
    ("agc_assembly", "# MOD BY - GAUNTT", "GAUNTT"),
    ("yaml", "contact:\n  email: support@example.com\n", "support@example.com"),
    ("m4", "dnl Author: Jane Doe", "Jane Doe"),
    ("makefile", "# author: keyword-rosetta generator", "keyword-rosetta generator"),
    ("cobol", "      * Author     : ALDV", "ALDV"),
]

COUNTS = [
    ("java", "/**\n * @author Jane\n * @author Joe\n */", 2),
    ("c", "/* Author: Jane\n   Maintainer: Joe */", 2),
    ("shell", "# Author: Jane\n# Copyright 2020 Jane\n# License: MIT", 1),
    ("solidity", "// SPDX-License-Identifier: MIT\n// Author: Jane\n", 1),
    ("python", ":author: Pierre\n:contact: p@x\nowner: User\n", 2),
    ("yaml", "author: Jane\ncontact:\n  name: Support\n  email: s@x\n", 2),
]

# (lang, text, other_signal): a token that belongs to another signal alone
# (C4), or to no signal (C2) -- it must never fire ownership.
DUALS = [
    ("assembly", "; @author Jane", None),  # doc released it: ownership's alone, checked below
    ("m4", "AC_COPYRIGHT([Copyright (C) 2026 Jane Doe])", "doc"),
    ("dockerfile", 'LABEL description="x"', "doc"),
    ("kotlin", "@since 1.2", None),
    ("perl", "=head1 LICENSE", None),
    ("lua", "-- License: MIT", None),
    ("shell", "# Copyright 2017 The Kubernetes Authors.", None),
    ("solidity", "// SPDX-License-Identifier: MIT", None),
]

# C4: the author tag has one owner -- doc must not count it where it used to.
DOC_RELEASED = [
    ("assembly", "; @author Jane"),
    ("cobol", "      *> @author Joe"),
    ("css", "/* @author Jane Doe */"),
    ("dockerfile", 'LABEL maintainer="dev@example.com"'),
    ("dockerfile", "# Author: Jane"),
    ("haskell", "-- @author Jane"),
    ("html", '<meta name="author" content="Jane Doe">'),
]

PAYLOADS = [
    "Author:" + " " * 100000,
    "Author: " + "a" * 100000,
    "Author: " + "a " * 50000,
    "Author: " + "a" * 50000 + " */",
    "Author: " + "a" * 50000 + " -->",
    "Author" + " " * 50000 + ":",
    "Author:\n" * 20000,
    "Created" + " " * 50000 + "by: x",
    "Created by " + "a" * 50000 + " on ",
    "//  Created by " + "a " * 25000,
    "@author" + " " * 100000,
    "@author " + "a" * 100000,
    "=head1 AUTHORS" + "\n" * 50000,
    "=head1 AUTHORS\n" + " " * 100000,
    "__author__" + " " * 50000 + "=",
    ".. moduleauthor::" + " " * 100000,
    "contact:\n" + " \n" * 20000,
    "MOD BY " + "-" * 100000,
    '<meta name="author" content="' + "a" * 100000,
    "AUTHOR. " + " " * 100000,
    "*" * 50000 + " Author:",
    "-" * 50000 + " Author:",
    "#" * 50000 + " Author:",
    "Owner: " + "a" * 50000 + ",",
    "=head1 AUTHORS\n" + " " * 100000,
    "-- " + " " * 100000,
    "-- |" + " " * 100000,
    "/// -" + " " * 100000,
    "      *" + " " * 100000,
    "#" + " " * 100000 + "MOD BY",
    " " * 100000 + "Author:",
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_ownership_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", CAPTURES)
def test_ownership_value_is_the_name(lang, text, expected):
    """C3: the detector reads `m.group(m.lastindex)` as the file's dominant author."""
    m = _rule(lang).search(text)
    assert m and m.lastindex, f"{lang}: no capture on {text!r}"
    assert m.group(m.lastindex).strip() == expected


@pytest.mark.parametrize("lang", sorted(CASES))
def test_ownership_every_alternative_captures(lang):
    """C3: no alternative may match without a group (solidity's SPDX did)."""
    rule = _rule(lang)
    positives, _ = CASES[lang]
    for text in positives:
        m = rule.search(text)
        assert m and m.lastindex and m.group(m.lastindex).strip(), f"{lang}: {text!r} matched without a value"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_ownership_one_tag_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


@pytest.mark.parametrize("lang,text,other_signal", DUALS)
def test_ownership_never_fires_on_another_owners_token(lang, text, other_signal):
    if other_signal is None and text.startswith("; @author"):
        assert _rule(lang).search(text)  # the one positive in this list: released BY doc TO ownership
        return
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert not hits, f"{lang}: ownership fired on {text!r}: {hits!r}"
    if other_signal is not None:
        assert _rule(lang, other_signal).search(text), f"{lang}: expected {other_signal!r} to own {text!r}"


@pytest.mark.parametrize("lang,text", DOC_RELEASED)
def test_ownership_author_tag_has_one_owner(lang, text):
    """C4: doc counts the block; the author tag is ownership's alone."""
    assert not _rule(lang, "doc").search(text), f"{lang}: doc still claims {text!r}"
    assert _rule(lang).search(text), f"{lang}: ownership does not claim {text!r}"


def test_ownership_markdown_has_no_rule():
    """C5: markdown has no comment surface and no metadata field; the row is absent."""
    assert LANGUAGE_DEFINITIONS["markdown"]["rules"].get("ownership") is None


@pytest.mark.parametrize("lang", sorted(CASES))
def test_ownership_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)
