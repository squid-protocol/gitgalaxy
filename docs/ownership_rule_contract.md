# The `ownership` rule contract (#2882)

Phase 3 of the contract roadmap (`docs/contract_roadmap.md`, epic #2812): the sheet row
`ownership` goes from `draft` to `stated`. The precedents are `docs/api_rule_contract.md`
(#2730), `docs/args_rule_contract.md` (#2773), `docs/state_mutation_rule_contract.md` (#2765),
`docs/branch_rule_contract.md` (#2822), `docs/io_rule_contract.md` (#2841),
`docs/globals_rule_contract.md` (#2858), `docs/safety_rule_contract.md` (#2869),
`docs/import_rule_contract.md` (#2875) and `docs/high_risk_execution_rule_contract.md` (#2878).

The sheet's draft sentence was "Authorship metadata. Includes: @author, Created by:". Forty-six
rules read it forty-six ways: solidity counted the SPDX license identifier on every file, c,
cpp and yacc counted the MIT license's own prose (`The above copyright notice`, `AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE`), shell counted every copyright notice, typescript and javascript
counted the phrase `created by` wherever a sentence used it, go counted `owner as the given
ReplicaSet`, objective-c's rule was literally a person's name (`Tim Berners-Lee`, copied into
abap, apex and scala), kotlin counted `@since`, haskell could not see the GHC module header's
`Maintainer  :` field, and five doc rules still counted the author tag a second time. Every one
of those is a different answer to "what is one hit".

This is the first contract stated for a **comment-stream rule**. The detector runs the six
comment-stream rules (`dead_code`, `doc`, `ownership`, `planned_debt`, `fragile_debt`,
`spec_exposure`) over the code stream in `coding_analysis` AND over the comment stream in
`comment_analysis`, so a rule's incidence is the sum of both -- `tests/tools/rule_probe.py`
measured only the code stream until this issue and read c's 51 crucible hits as 0. It now takes
`--stream auto|code|comment|both` (auto = both for those six rules) and reports the split.

## The contract

> **One hit is a tag naming who is responsible for the unit -- an author, creator, maintainer,
> owner, developer or contact -- with its value, in the form the language's tooling or header
> convention reads as metadata: a doc-comment tag, a keyed header line, or the language's own
> metadata field.**

Kind `annotation`, unit `annotations` (the module's `KINDS` table): a marker attached to a
comment or declaration. The score layer no longer reads it: #2908 D4 removed the
`ownership_weight` 0.5 documentation-defense term (*who* maintains a file is a different
question from whether its units are documented, and it is carried by the silo/authorship
views); `detector._decode_comment_stream` still reads the rule's **last capture group** from
the comment stream as the file's dominant author (`Architect` in the audit,
`Unknown Architect` when nothing matches), and `signal_processor` names ghost clusters after it.

## Corollaries

**C1 -- the tag, not the word.** The forms are `@author X` (javadoc, jsdoc, phpdoc, apexdoc,
kdoc, scaladoc, groovydoc, natspec, LDoc, YARD, doxygen, css/sqlite `/** @author */`),
`\author X` (doxygen), `<author>X</author>` (C# XML docs), `Author: X` / `Created by: X` /
`Maintainer: X` / `Owner: X` / `Developer: X` / `Contact: X` as a keyed header line (any case
after the language's comment marker; on an unprefixed block-comment continuation line the tag
must be capitalised -- `Author:` or `AUTHOR:` -- and its value must not end the way a field or
literal line does), `=head1 AUTHOR(S)` (POD, the value on the next paragraph), `.AUTHOR X`
(powershell help), `- Author: X` (swift markdown callouts), `AUTHOR. X.` (cobol's paragraph),
`MOD BY - X` (agc's modification credit), `__author__ = "X"`, `.. moduleauthor:: X` and
`:author: X` (python's module variable, Sphinx directive and docinfo field), `MAINTAINER X` /
`LABEL maintainer=` / `LABEL org.opencontainers.image.authors=` (dockerfile), `author:` and
`contact:` (yaml -- action.yml and OpenAPI), `<meta name="author">` / `<link rev="made">`
(html), and Xcode's dated template `//  Created by X on <date>` (swift, objective-c, c, cpp)
-- the one colon-less keyed form kept, because the date is its separator. The keyed form is
anchored to the start of a comment line and needs its separator, and the separator is not
`::` or `:=` (`Author::Author()` is a C++ scope, `AUTHOR := x` a make variable). Prose carrying
the words is not a hit: typescript's `* created by the extension.` (11 of vscode's hits),
javascript's `created by the renderer`, csharp's `being created by compiling all of the code`,
go's `owner as the given ReplicaSet`; a substring is not a tag (python's unanchored `Author:`
matched inside `.. moduleauthor::`, which now counts by its own form); a field or annotation
named for the concept is not one (`owner: UserDB`, `owner: *Package.Module,`, `author:
CommentAuthorInformation;`, react's `owner: task.debugOwner,`); a person's name is not a rule.

**C2 -- rights are not responsibility.** A license identifier (`SPDX-License-Identifier`,
`License:`, `=head1 LICENSE`) and a copyright notice (`Copyright (c) 2014 X`, `Copyright 2017
The Kubernetes Authors`, `SPDX-FileCopyrightText`, `AC_COPYRIGHT`, `=head1 COPYRIGHT`, the keyed
`Copyright:` that twenty rules carried and no real notice writes) say who holds rights and on
what terms -- repo-wide boilerplate, identical on every file, that says nothing about who to ask
about this one. Neither counts, in any form. Four languages counted the notice (c, cpp, yacc,
objective-c), shell counted every one (131 of 256 crucible files), c/cpp/yacc counted the
license text itself, and forty-one languages counted none of it; the contract sides with the
forty-one. The visible consequence in the golden master: `Architect` for doom's c files was
`(C) 1993-1996 by id Software, Inc` and is now `Unknown Architect`, which is the truth -- no one
signed those files. A version tag (`@since`) is not ownership either.

**C3 -- one tag is one hit, and the value is the name.** A file with `@author` and
`Maintainer:` reads 2; two `@author` lines read 2; a block under one tag (yaml's `contact:`,
perl's `=head1 AUTHORS` paragraph, a wrapped continuation) reads 1. Every alternative captures
its value with the closing comment marker stripped (`/* Author: X */` yields `X`), because the
detector reads `m.group(m.lastindex)` -- solidity's SPDX alternative had no group, so every
solidity file's architect was the string `// SPDX-License-Identifier:`; m4's `AC_COPYRIGHT` and
yaml's whole rule had none either.

**C4 -- one owner: the author tag is ownership's.** `doc` counts the documentation block, never
the author tag inside it -- the rule #2659 and #2672 applied to eighteen languages, finished:
assembly (`@author`), cobol (`*> @author`), css (`/* @author`), dockerfile (`LABEL maintainer=`,
`LABEL org.opencontainers.image.authors=`, `# Author:`, `# Maintainer:`), haskell (`-- @author`,
whose ownership rule was pinned *not* to match it) and solidity's bare `@author` release it.
html's `<meta name="author">` was already ownership's alone (#2659); the corpus ledger's
`batch5-tier2-morphology-shapes` still called it a dual and loses the clause.

**C5 -- absence.** markdown has no comment surface (the prose bypass routes the whole file to
the doc stream) and no metadata field; its rule stays `None` and the cell is n/a. Every other
corpus language has a comment surface or a metadata key, so no fallback family is manufactured.

## The open cell

`solidity` read 4 against a row of 1s: the SPDX line on every file (C2), through the
group-less alternative (C3). The rule now counts natspec `/// @author` and the keyed line;
`main.sol` plants `// Author: keyword-rosetta generator` (the `///` form was rejected because
the doc rule counts every `///` line and doc would read 2) and `a`/`b`/`c` re-bless 1 -> 0.
The SPDX lines stay in the files as furniture and count nothing.

## Measured with no red cell

The crucible (language-crucible v1.2.0, `rule_probe.py --stream auto`, raw hits over both
Prism streams) before -> after, with the reason:

- **c 51 -> 0, cpp 62 -> 1, yacc 6 -> 0**: the notice form and the MIT/BSD license prose (C2).
  cpp's survivor is `// Owner: Builtin (local) administrator` -- a keyed line in a comment.
- **shell 131 -> 5**: every `# Copyright ...` notice (C2); the five are `# Author:` and
  `# Created by:` lines in the linux kernel's scripts.
- **typescript 11 -> 0, javascript 4 -> 0, csharp 1 -> 0, go 1 -> 0**: `created by` and `owner`
  in sentences (C1). react's `owner: task.debugOwner,` fields were caught by a first draft of
  the bare form and are excluded by its terminator guard.
- **m4 2 -> 0**: `AC_COPYRIGHT` (C2; it stays `doc`'s). **perl 2 -> 1**: `=head1 COPYRIGHT`
  out, `=head1 AUTHORS` stays and now captures the paragraph. **php 17 -> 16**: `@copyright`.
- **haskell 0 -> 7**: pandoc's GHC-style header `Maintainer  : John MacFarlane` -- spaces
  before the colon, on an unprefixed line inside `{- |` (C1's bare form).
- **cobol 61 -> 79**: `* Author     : ALDV` comment lines join the `AUTHOR.` paragraph.
- **python 2 -> 5**: `:contact:` and two twisted `Maintainer:` docstring lines join;
  `.. moduleauthor::` and `:author:` count by their own forms.
- **sqlite 0 -> 8**: yii migrations' `* @author Qiang Xue` blocks. **matlab 3 -> 5**:
  `% Authors:`. **fortran 1 -> 3**: `!  Author:Balwinder.Singh@pnl.gov` (no space after the
  colon). **scheme 0 -> 2**: `;;; Authors: R. Kent Dybvig, ...`. **powershell 0 -> 1**:
  `Maintainer: PowerShell Team` in a help block. **dockerfile 0 -> 1**: `# Maintainer:
  @jhowardmsft` (released by doc, C4).
- **objective-c 1 -> 0**: `//	TBL		Tim Berners-Lee CERN/CN` (a name is not a tag).

`doc` on the crucible moved in one language: dockerfile 7 -> 6 (`LABEL maintainer=`, C4). The
other five doc releases had no crucible hits.

## The corpus (keyword-rosetta PR)

| language | was | now | why |
|---|---|---|---|
| solidity `a/b/c.sol` | ownership 1 (SPDX) | 0 | C2 |
| solidity `main.sol` | SPDX line | `// Author: keyword-rosetta generator` added | C1 |
| csharp `main.cs`, objective-c `main.mm` | `// Created by keyword-rosetta generator` | `// Created by: keyword-rosetta generator` | C1 (the separator) |

Each screened as a replacement pair (every rule of the language over both Prism streams, HEAD
vs branch): only `ownership` moves. Ledger: `ownership-contract-2882` added;
`batch5-tier2-morphology-shapes` loses `ownership`, solidity and html (their only itemised
shapes). Every other language's plant already carried the keyed or doc-tag form and reads 1
unchanged, with the generator's name as the captured value in all 45.

## The 46-language audit

Raw rule hits on both corpora before -> after (`rule_probe.py --compare`); a single number
did not move. The keyword-rosetta column is the corpus cell (1 planted in `main`; markdown n/a).

| language | crucible | keyword-rosetta |
|---|---|---|
| `abap` | 0 | 1 |
| `ada` | -- | 1 |
| `agc_assembly` | 16 | 1 |
| `apex` | 0 | 1 |
| `assembly` | 0 | 1 |
| `c` | 51 -> 0 | 1 |
| `cobol` | 61 -> 79 | 1 |
| `cpp` | 62 -> 1 | 1 |
| `csharp` | 1 -> 0 | 1 |
| `css` | 0 | 1 |
| `dart` | 0 | 1 |
| `dockerfile` | 0 -> 1 | 1 |
| `embedded_python` | 0 | 1 |
| `fortran` | 1 -> 3 | 1 |
| `go` | 1 -> 0 | 1 |
| `groovy` | 14 | 1 |
| `haskell` | 0 -> 7 | 1 |
| `html` | 1 | 1 |
| `java` | 42 | 1 |
| `javascript` | 4 -> 0 | 1 |
| `jcl` | 0 | 1 |
| `kotlin` | 0 | 1 |
| `livecode` | 0 | 1 |
| `lua` | 0 | 1 |
| `m4` | 2 -> 0 | 1 |
| `makefile` | -- | 1 |
| `markdown` | n/a | n/a |
| `matlab` | 3 -> 5 | 1 |
| `objective-c` | 1 -> 0 | 1 |
| `perl` | 2 -> 1 | 1 |
| `php` | 17 -> 16 | 1 |
| `powershell` | 0 -> 1 | 1 |
| `python` | 2 -> 5 | 1 |
| `ruby` | 0 | 1 |
| `rust` | 0 | 1 |
| `scala` | 0 | 1 |
| `scheme` | 0 -> 2 | 1 |
| `shell` | 131 -> 5 | 1 |
| `solidity` | 7 -> 0 | 4 -> 1 |
| `sqlite` | 0 -> 8 | 1 |
| `swift` | 0 | 1 |
| `tcl` | 0 | 1 |
| `typescript` | 11 -> 0 | 1 |
| `yacc` | 6 -> 0 | 1 |
| `yaml` | 0 | 1 |
| `zig` | 0 | 1 |

Every rule was rewritten to the shared shape (one replacement script, `# #2882 contract:` in
each file's comment): the language's doc-tag form(s), the keyed line on the language's own
comment markers, its metadata field(s), the bare capitalised form, every alternative capturing.
Unchanged in effect on the crucible: the twenty-four languages whose files carry no tag at all.

## Known limits

- The stream contract: a string literal carrying a form at the start of a line counts (a
  multi-line string beginning `Author: x`). Deliberate, corpus-wide.
- cobol's `AUTHOR.` paragraph counts when its value is empty (NIST's `000400 AUTHOR.` with only
  the sequence-area identifier), because the paragraph is declared; the captured "name" is
  then the sequence text. The keyed form's value is captured verbatim, so `__author__ = "x"`
  yields `"x"` with its quotes and `LABEL maintainer="x"` likewise -- the detector strips tags
  and trailing punctuation, not quotes.
- The bare capitalised form admits a capitalised field or annotation that does not end in
  `,`, `;`, `{` or `(` (a pydantic model with `Owner: str`), and a comment line `// Owner:
  Builtin (local) administrator` describing something else's owner. Measured at one hit.
- The ghost meta reads the comment stream only, so python's `__author__`, dockerfile's
  `MAINTAINER`, yaml's `author:` and html's `<meta>` count but never name the architect
  (pre-existing; `_decode_comment_stream` is the consumer to widen).
- yaml's Helm `maintainers:` list and `CODEOWNERS`-style files are not ownership forms yet
  (no cell evidence; the value sits on the next line).

## Deferred by design

Nothing filed: the audit found no residue worth an issue. The ghost-meta limit above and the
`maintainers:` list are named here for the next language that needs them.

## Bless scope

`tests/golden_master_*.json`: 489 differences, **0 topological**, all in-family -- the
`Authorship Metadata` leaf (198), `Architect` in the artifact identity (194: doom's
`(C) 1993-1996 by id Software, Inc` and haiku's `(c) 2010-2012 Haiku, Inc` become `Unknown
Architect`; moby's `windows.Dockerfile` gains `@jhowardmsft`), `Documentation Exposure` /
`documentation` (91, the 0.5-weight defense), and one dockerfile file whose `Structured
Documentation Blocks` reads 1 instead of 2 (C4's `LABEL maintainer=` release) with the
`Cognitive Load Exposure` that reads doc. By language: shell 181, c 68, cpp 59, cobol 49,
solidity 16, haskell 14, sqlite 10. Newly parsed / newly excluded: none.
