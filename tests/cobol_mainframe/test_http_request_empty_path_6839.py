"""#6839 (row K): a scenario's http_request may state an empty path (a request for no path); every other piece keeps its check."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_web as web  # noqa: E402


def _req(**kw):
    req = {"scheme": "HTTP", "host": "h.example.com", "port": 8080, "method": "GET", "version": "HTTP/1.1", "path": "/a",
           "query": "", "headers": [], "mediatype": None, "body": None}  # fmt: skip
    return {**req, **kw}


def _get(req):
    return web.http_request({}, {"name": "s", "http_request": req})


def test_an_empty_path_is_accepted_and_written_as_a_blank_token():
    req = _get(_req(path=""))
    assert req["path"] == ""
    assert (
        web.http_request_cfg(req, "latin-1").splitlines()[0]
        == "R HTTP " + "h.example.com".encode().hex().upper() + " 8080 GET - -"
    )


@pytest.mark.parametrize("field", ["host", "version"])
def test_the_other_pieces_still_refuse_empty(field):
    with pytest.raises(ec.Unsupported):
        _get(_req(**{field: ""}))


@pytest.mark.parametrize("path", ["/a b", " ", "/a\t"])
def test_a_path_with_whitespace_is_still_refused(path):
    with pytest.raises(ec.Unsupported):
        _get(_req(path=path))
