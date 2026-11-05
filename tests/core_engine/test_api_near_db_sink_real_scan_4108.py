# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 17: Public API Declared Near Raw DB Sink (`threat_api_near_db_sink`) probed through a real scan.

The funnel needs a public route (`api`, detector side) and a raw DB sink (`sec_db_hooks`, security lens) in the same
function, within a few lines. This plants one route-plus-query file per language and reads `threat_api_near_db_sink`
from the scan DB. Near misses (a sink with no route, a route with no sink) stay 0. Shapes the rules do not read
are strict xfails (sibling gaps).
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="three real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

_PAD = {"py": "#", "rb": "#"}

# name -> (extension, body)
FIRE = {
    "py_flask": (
        "py",
        "@app.route('/u')\ndef get_user(request):\n    uid = request.args['id']\n"
        "    cur.execute(\"SELECT * FROM users WHERE id=\" + uid)\n    return cur.fetchall()\n",
    ),
    "js_express": (
        "js",
        "app.get('/u', (req, res) => {\n  db.query('SELECT * FROM users WHERE id=' + req.query.id);\n"
        "  res.send('ok');\n});\n",
    ),
    "ts_express": (
        "ts",
        "router.get('/u', async (req: Request, res: Response) => {\n"
        "  await pool.query(`SELECT * FROM users WHERE id=${req.query.id}`);\n  res.send('ok');\n});\n",
    ),
    "java_spring": (
        "java",
        '@GetMapping("/u")\npublic String get(@RequestParam String id) {\n'
        '    stmt.executeQuery("SELECT * FROM users WHERE id=" + id);\n    return "ok";\n}\n',
    ),
    "go_http": (
        "go",
        "func handler(w http.ResponseWriter, r *http.Request) {\n"
        '\tdb.Query("SELECT * FROM users WHERE id=" + r.URL.Query().Get("id"))\n}\n'
        'func main() { http.HandleFunc("/u", handler) }\n',
    ),
    "rb_sinatra": (
        "rb",
        "get '/u' do\n  ActiveRecord::Base.connection.execute(\"SELECT * FROM users WHERE id=#{params[:id]}\")\nend\n",
    ),
}
QUIET = {
    # python reads any non-underscore `def` as public surface (implicit public default), so a private name is the miss
    "py_private_helper_sink": (
        "py",
        "def _helper(uid):\n    cur.execute(\"SELECT * FROM users WHERE id=\" + uid)\n    return cur.fetchall()\n",
    ),
    "py_route_no_sink": ("py", "@app.route('/u')\ndef get_user(request):\n    return 'ok'\n"),
    "js_route_no_sink": ("js", "app.get('/u', (req, res) => {\n  res.send('ok');\n});\n"),
    "java_route_no_sink": ("java", '@GetMapping("/u")\npublic String get() {\n    return "ok";\n}\n'),
}
# Shapes the rules do not read: sibling gaps, each a different mechanism.
GAPS = {
    "php_route_closure": (
        "php",
        "<?php\nRoute::get('/u', function () {\n"
        "    mysqli_query($conn, \"SELECT * FROM users WHERE id=\" . $_GET['id']);\n});\n",
    ),
    "cs_sqlcommand": (
        "cs",
        '[HttpGet("u")]\npublic IActionResult Get(string id) {\n'
        '    var c = new SqlCommand("SELECT * FROM users WHERE id=" + id, conn);\n    return Ok();\n}\n',
    ),
}


def _scan(tmp_path, table) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, (ext, body) in table.items():
        pad = _PAD.get(ext, "//")
        (src / f"{name}.{ext}").write_text(body + "".join(f"{pad} filler {i}\n" for i in range(30)), "utf-8")
    out = tmp_path / "out"
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out)],
        env=env,
        check=True,
        capture_output=True,
        timeout=180,
    )
    (db,) = out.glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    try:
        return {p: n for p, n in con.execute("select file_path, threat_api_near_db_sink from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    return tuple(_scan(tmp_path_factory.mktemp(k), t) for k, t in (("fire", FIRE), ("quiet", QUIET), ("gaps", GAPS)))


@pytest.mark.parametrize("name", sorted(FIRE))
def test_route_near_sink_is_flagged_through_a_real_scan(scans, name):
    assert scans[0][f"{name}.{FIRE[name][0]}"] >= 1


@pytest.mark.parametrize("name", sorted(QUIET))
def test_near_miss_is_not_flagged(scans, name):
    assert scans[1][f"{name}.{QUIET[name][0]}"] == 0


@pytest.mark.xfail(strict=True, reason="sibling gap: the route or the sink shape is not read in this language")
@pytest.mark.parametrize("name", sorted(GAPS))
def test_unread_shape_is_flagged(scans, name):
    assert scans[2][f"{name}.{GAPS[name][0]}"] >= 1
