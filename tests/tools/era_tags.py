#!/usr/bin/env python3
"""#5117: the era tagger now ships in the package (#4726): gitgalaxy/tools/readiness/era_tags.py. This keeps the
tools' import path and CLI.

    python tests/tools/era_tags.py PROGRAM.cbl [...]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gitgalaxy.tools.readiness.era_tags import (  # noqa: F401
    CITE,
    ERAS,
    PERIOD_BOUND,
    TELLS,
    asm_members,
    clean,
    main,
    mark_skipped,
    summarise,
    tag_program,
)

if __name__ == "__main__":
    sys.exit(main())
