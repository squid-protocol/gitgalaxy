"""#6239: Java trust-all HostnameVerifier / TrustManager forms count as safety bypasses; near-misses stay silent."""

import time

import pytest

from gitgalaxy.security.security_lens import SecurityLens

_LENS = SecurityLens()


def _count(text: str) -> int:
    return _LENS.scan_content(text)["counts"].get("safety_bypasses", 0)


_FIRES = [
    "HttpsURLConnection.setDefaultHostnameVerifier((h, s) -> true);",
    "conn.setHostnameVerifier((hostname, session) -> true);",
    "HostnameVerifier hv = (h, s) -> true;",
    "builder.hostnameVerifier(NoopHostnameVerifier.INSTANCE);",
    "SSLConnectionSocketFactory.ALLOW_ALL_HOSTNAME_VERIFIER",
    "SslContextBuilder.forClient().trustManager(InsecureTrustManagerFactory.INSTANCE)",
    ".loadTrustMaterial(null, TrustAllStrategy.INSTANCE)",
    "public boolean verify(String host, SSLSession s) { return true; }",
    "public boolean verify(String host, SSLSession s)\n    {\n        return true;\n    }",
    "public void checkServerTrusted(X509Certificate[] c, String a) {}",
    "public void checkServerTrusted(X509Certificate[] c, String a)\n  throws CertificateException {\n  }",
]

_SILENT = [
    "list.sort((a, b) -> true);",
    "BiPredicate<String, String> p = (a, b) -> true;",
    "HostnameVerifier hv = HttpsURLConnection.getDefaultHostnameVerifier();",
    "conn.setHostnameVerifier((h, s) -> h.endsWith(\".example.test\"));",
    "public boolean verify(String host, SSLSession s) { return host.equals(expected); }",
    "public boolean verify(String a, String b) { return true; }",
    "public void checkServerTrusted(X509Certificate[] c, String a) { delegate.checkServerTrusted(c, a); }",
    "public void checkServerTrusted(X509Certificate[] c, String a) throws CertificateException {\n  validate(c);\n}",
    "trustManager.checkServerTrusted(chain, authType);",
]


@pytest.mark.parametrize("text", _FIRES)
def test_java_trust_all_fires(text):
    assert _count(text) >= 1


@pytest.mark.parametrize("text", _SILENT)
def test_java_trust_all_near_miss_is_silent(text):
    assert _count(text) == 0


@pytest.mark.parametrize(
    "text",
    [
        "checkServerTrusted(" + "(" * 5000,
        "boolean verify(" + "SSLSession " * 3000,
        "setHostnameVerifier" + " (a, b) ->" * 3000,
        "checkServerTrusted(a) throws " + "A, " * 3000,
    ],
    ids=["trusted", "verify", "lambda", "throws"],
)
def test_java_trust_all_patterns_are_not_redos(text):
    start = time.perf_counter()
    _count(text)
    assert time.perf_counter() - start < 2
