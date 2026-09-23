"""Suite-wide pytest hooks.

Long string parameters get short test IDs. pytest puts every test's node ID in the
PYTEST_CURRENT_TEST environment variable, and Windows caps one environment
variable at 32,767 characters. A ReDoS test that parametrizes on its own
pathological payload (e.g. `"COMMAREA " * 5000`) therefore fails on Windows during
setup with "the environment variable is longer than 32767 characters", before the
test body runs, while Linux and macOS pass. That surfaced first on the labelled
full-suite Windows jobs for #3404, from test_commarea_contract.py (#3369).

A string longer than _MAX_ID_CHARS becomes its first characters plus a length and
a short content hash. The ID stays readable, stays stable across runs, and stays
distinct for payloads that share a prefix.
"""

import hashlib

_MAX_ID_CHARS = 64


def pytest_make_parametrize_id(val):
    if isinstance(val, str) and len(val) > _MAX_ID_CHARS:
        digest = hashlib.sha256(val.encode("utf-8", "surrogatepass")).hexdigest()[:8]
        return f"{val[:40]!r}...len{len(val)}-{digest}"
    return None
