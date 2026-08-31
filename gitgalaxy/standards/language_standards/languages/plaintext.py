# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Universal Plaintext & ASCII Secrets",
        "last_updated": "2026-04-01",
        "blueprint_version": "1.1",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard text, log outputs, and UNIX man pages.
    # FIX: Removed JCL/BMS (executable) and p12/pfx/jks/kdbx (lethal binary blobs).
    "extensions": [
        ".txt",
        ".text",
        ".log",
        ".out",
        ".err",
        ".nfo",
        ".golden",
        ".properties",
        ".1",
        ".2",
        ".3",
        ".4",
        ".5",
        ".6",
        ".7",
        ".8",
        ".9",
    ],
    # ABSOLUTE IDENTITY: The universally recognized, extensionless plaintext anchors.
    # FIX: Added ubiquitous community files. Removed binary keystore exact matches.
    "exact_matches": [
        "AUTHORS",
        "NOTICE",
        "COPYING",
        "INSTALL",
        "acknowledgements",
        "CHANGELOG",
        "CONTRIBUTING",
        "CODE_OF_CONDUCT",
        "SECURITY",
        "MAINTAINERS",
    ],
    # ECOSYSTEM ANCHORS: Universal fallback discriminators.
    "discriminators": [".txt", ".md", "README", "LICENSE"],
    # EXECUTION SIGNATURES: Plaintext is unexecuted raw string data.
    "shebangs": [],
    # THE FIX: Plaintext is mathematically inert. It has no lexical family.
    "lexical_family": "non_lexical",
    "rules": {},
}
