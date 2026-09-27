# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The multilingual credential lexicon behind the hardcoded-secrets signature.

A credential is named in the language its programmers speak. The signature used
to know only English (`password`, `secret`, `token`...), so `String senha = "..."`
in a Brazilian service and `05 WS-PASSWORT PIC X(16) VALUE '...'` in a German
COBOL estate were invisible to it (#3832).

Each entry is a regex FRAGMENT, matched case-insensitively and bounded by `\\b`
by the caller. Accented letters are spelled as `(?:n|ñ)`-style alternatives
because source is often written without them (`contrasena`) and decoded code
pages sometimes lose them. Only words that name a credential and little else
are listed: a word that is also an everyday noun would turn the signature into
a word counter.

This module is a leaf (it imports only `re`), so any lens can use it without an
import cycle.
"""

import re

# Credential names as they appear in modern code: identifiers and config keys.
# The English core is the pre-#3832 list, unchanged.
CODE_CREDENTIAL_NAMES: dict[str, tuple[str, ...]] = {
    "en": (
        "password",
        "secret",
        "token",
        r"api[_-]?key",
        r"client[_-]?secret",
        "credentials",
        r"private[_-]?key",
        r"auth[_-]?token",
    ),
    "de": ("passwort", "kennwort"),
    "pt": ("senha",),
    "es": (r"contrase(?:n|ñ)a", "clave"),
    "fr": (r"mot[_-]?de[_-]?passe",),
    "nl": ("wachtwoord",),
    "sv": (r"l(?:o|ö)senord",),
    "no": ("passord",),
    "da": ("adgangskode",),
    "fi": ("salasana",),
    "pl": ("haslo", "hasło"),
}

# Credential stems as they open a COBOL data name (`WS-PASSWORT-1`). COBOL
# words are hyphenated, so the French name is `MOT-DE-PASSE`. The English core
# is the pre-#3832 list, unchanged.
COBOL_CREDENTIAL_STEMS: dict[str, tuple[str, ...]] = {
    "en": ("PASSWORD", "SECRET", "TOKEN", "KEY", "CREDENTIALS"),
    "de": ("PASSWORT", "KENNWORT"),
    "pt": ("SENHA",),
    "es": (r"CONTRASE(?:N|Ñ)A", "CLAVE"),
    "fr": ("MOT-DE-PASSE",),
    "nl": ("WACHTWOORD",),
    "sv": (r"L(?:O|Ö)SENORD",),
    "no": ("PASSORD",),
    "da": ("ADGANGSKODE",),
    "fi": ("SALASANA",),
    "pl": ("HASLO", "HASŁO"),
}


def _alternation(lexicon: dict[str, tuple[str, ...]]) -> str:
    return "|".join(word for words in lexicon.values() for word in words)


CODE_CREDENTIAL_ALTERNATION = _alternation(CODE_CREDENTIAL_NAMES)
COBOL_CREDENTIAL_ALTERNATION = _alternation(COBOL_CREDENTIAL_STEMS)

# Fail at import, not at scan time, if a fragment is not a valid regex.
re.compile(CODE_CREDENTIAL_ALTERNATION)
re.compile(COBOL_CREDENTIAL_ALTERNATION)
