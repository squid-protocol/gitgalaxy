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
        "target_version": "Standard XML 1.0 / UI Layouts",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard data, schemas, stylesheets, vector graphics, Apple UI, and config files.
    "extensions": [
        ".xml",
        ".xsd",
        ".xsl",
        ".xslt",
        ".svg",
        ".storyboard",
        ".xib",
        ".plist",
        ".wsdl",
        ".config",
        ".jelly",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Universally recognized XML architectural and build manifests.
    "exact_matches": ["pom.xml", "build.xml", "AndroidManifest.xml", "phpunit.xml"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions to anchor standard data serialization and frameworks.
    "discriminators": [".xml", ".xsd", ".xsl", "pom.xml", "build.xml"],
    # EXECUTION SIGNATURES: XML is declarative data/markup; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 8 (Singular/Unique)
    # Rationale: (CORRECTION) Consolidated 'xml_angle' into 'singular'. Like HTML, XML
    # exclusively uses SGML-style block delimiters () for its Commented / Non-Executable Text.
    "lexical_family": "block_exclusive",
    "rules": {},
}
