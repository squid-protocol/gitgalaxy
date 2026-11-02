# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 6: per-signal probe of Embedded Credentials & Keys (`hardcoded_secrets`).

Planted forms the rule used to miss (compound names, JSON-quoted keys, punctuation in the value, newer vendor
token prefixes) and near-miss controls that must stay at zero. Fake values are assembled from parts so this file
is not itself a credential.
"""

import pytest

from gitgalaxy.security.security_lens import SecurityLens

A = "abcdefghijklmnopqrstuvwxyz0123456789"

FIRES = {
    "compound_name": 'DB_PASSWORD = "' + A[:20] + '"\n',
    "aws_secret_access_key": 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCY"\n',
    "json_quoted_key": '{"password": "' + A[:20] + '"}\n',
    "punctuation_value": 'password = "P@ssw0rd!Secret#2024"\n',
    "jwt": 'x = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27"\n',
    "github_fine_grained": 'x = "github_pat_' + "11ABCDEFG0" + A + '"\n',
    "github_oauth": 'x = "gho_' + A + '"\n',
    "gitlab": 'x = "glpat-' + A[:20] + '"\n',
    "npm": 'x = "npm_' + A + '"\n',
    "anthropic": 'x = "sk-ant-api03-' + A + '"\n',
    "openai_project": 'x = "sk-proj-' + A + '"\n',
    "huggingface": 'x = "hf_' + A + '"\n',
    "slack_webhook": 'u = "https://hooks.slack.com/services/T0000000/B0000000/' + A[:24] + '"\n',
    "encrypted_pem": "-----BEGIN ENCRYPTED PRIVATE KEY-----\n",
}
QUIET = {
    "secret_name_suffix": 'secret_name = "my-prod-database-secret-name"\n',
    "token_url_suffix": 'token_url = "https://example.com/oauth/token/x"\n',
    "plural_name": 'max_tokens = "' + A[:20] + '"\n',
    "short_value": 'password = "hunter2"\n',
    "half_jwt": 'x = "eyJhbGci.notajwt"\n',
    "short_prefix": 'x = "gho_short"\n',
    "non_credential_name": 'username = "' + A[:20] + '"\n',
}


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


@pytest.mark.parametrize("name", FIRES)
def test_missed_form_now_fires(lens, name):
    assert lens.scan_content(FIRES[name])["counts"].get("hardcoded_secrets", 0) >= 1


@pytest.mark.parametrize("name", QUIET)
def test_near_miss_stays_quiet(lens, name):
    assert lens.scan_content(QUIET[name])["counts"].get("hardcoded_secrets", 0) == 0


def test_long_compound_name_is_not_a_redos_shape(lens):
    import time

    start = time.perf_counter()
    lens.scan_content("a_" * 400 + 'x = "' + A + '"\n' + ("password" + "_a" * 300) + "\n")
    assert time.perf_counter() - start < 2
