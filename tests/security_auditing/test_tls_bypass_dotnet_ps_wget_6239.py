"""#6239: .NET accept-any certificate callbacks, PowerShell -SkipCertificateCheck and wget --no-check-certificate count as safety bypasses; near-misses stay silent."""

import time

import pytest

from gitgalaxy.security.security_lens import SecurityLens

_LENS = SecurityLens()


def _count(text: str) -> int:
    return _LENS.scan_content(text)["counts"].get("safety_bypasses", 0)


_FIRES = [
    "ServicePointManager.ServerCertificateValidationCallback = (s, c, ch, e) => true;",
    "ServicePointManager.ServerCertificateValidationCallback += (sender, cert, chain, errors) => { return true; };",
    "ServicePointManager.ServerCertificateValidationCallback = delegate { return true; };",
    "ServicePointManager.ServerCertificateValidationCallback = delegate (object s, X509Certificate c, X509Chain ch, SslPolicyErrors e)\n{\n    return true;\n};",
    "handler.ServerCertificateCustomValidationCallback = (m, c, ch, e) => true;",
    "handler.ServerCertificateCustomValidationCallback = HttpClientHandler.DangerousAcceptAnyServerCertificateValidator;",
    "Invoke-WebRequest https://host/x -SkipCertificateCheck",
    "Invoke-RestMethod -Uri $u -SkipCertificateCheck -Method Post",
    "wget --no-check-certificate https://host/x.tgz",
    "wget -q -O - --no-check-certificate https://host/install.sh | sh",
    "check_certificate = off",
    "[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }",
    "[Net.ServicePointManager]::ServerCertificateValidationCallback = { return $true }",
    "[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy",
    "[System.Net.ServicePointManager]::CertificatePolicy = [TrustAllCertsPolicy]::new()",
    "public bool CheckValidationResult(ServicePoint sp, X509Certificate c, WebRequest r, int p) {\n    return true;\n}",
]

_SILENT = [
    "ServicePointManager.ServerCertificateValidationCallback = (s, c, ch, e) => e == SslPolicyErrors.None;",
    "ServicePointManager.ServerCertificateValidationCallback = delegate { return Validate(); };",
    "ServicePointManager.ServerCertificateValidationCallback = null;",
    "var ok = ServicePointManager.ServerCertificateValidationCallback == null;",
    "handler.ServerCertificateCustomValidationCallback = (m, c, ch, e) => pinned.Equals(c.Thumbprint);",
    "Invoke-WebRequest https://host/x -SkipCertificateCheck:$false",
    "Invoke-WebRequest https://host/x -SkipCertificateCheckX",
    "Invoke-WebRequest https://host/x -NoSkipCertificateCheck",
    "wget https://host/x.tgz",
    "wget --check-certificate=on https://host/x.tgz",
    "echo wget is great\n# --no-check-certificate is unsafe",
    "check_certificate = on",
    "[Net.ServicePointManager]::ServerCertificateValidationCallback = { param($s, $c) $c.Thumbprint -eq $pin }",
    "[Net.ServicePointManager]::ServerCertificateValidationCallback = $null",
    "[Net.ServicePointManager]::CertificatePolicy = $null",
    "[Net.ServicePointManager]::CertificatePolicy = New-Object PinnedCertsPolicy",
    "public bool CheckValidationResult(ServicePoint sp, X509Certificate c, WebRequest r, int p) {\n    return false;\n}",
]


@pytest.mark.parametrize("text", _FIRES)
def test_tls_bypass_fires(text):
    assert _count(text) >= 1


@pytest.mark.parametrize("text", _SILENT)
def test_tls_bypass_near_miss_is_silent(text):
    assert _count(text) == 0


@pytest.mark.parametrize(
    "text",
    [
        "ServerCertificateValidationCallback = " + "(" * 5000,
        "ServerCertificateValidationCallback = delegate " + "(a) " * 3000,
        "wget " + "-q " * 5000,
        "-SkipCertificateCheck" * 3000,
        "ServerCertificateValidationCallback = { " * 3000,
        "CertificatePolicy = " * 3000,
        "CheckValidationResult(" + "a" * 5000,
    ],
    ids=["callback", "delegate", "wget", "skip", "psblock", "policy", "cvr"],
)
def test_tls_bypass_patterns_are_not_redos(text):
    start = time.perf_counter()
    _count(text)
    assert time.perf_counter() - start < 2
