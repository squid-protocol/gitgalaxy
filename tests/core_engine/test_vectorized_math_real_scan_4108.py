# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 19: Vectorized Math & Tensor Operations (`vectorized_math`) probed through a real scan.

`test_vectorized_math_probe_4108.py` calls the extractor directly; this plants one file per shape in python,
javascript and typescript, scans them end to end and reads `file_data.vectorized_math`. Ordinary names, comments
and string text stay 0. Shapes the rules do not read are strict xfails (sibling gaps).
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="three real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

# name -> (extension, body)
FIRE = {
    "py_matmul_operator": ("py", "y = a @ b\n"),
    "py_np_dot": ("py", "y = np.dot(a, b)\n"),
    "py_einsum": ("py", "y = np.einsum('ij,jk', a, b)\n"),
    "py_torch_bmm": ("py", "y = torch.bmm(a, b)\n"),
    "py_torch_mm_method": ("py", "y = a.mm(b)\n"),
    "py_np_outer": ("py", "y = np.outer(a, b)\n"),
    "js_tf_matmul": ("js", "const y = tf.matMul(a, b);\n"),
    "js_tf_einsum": ("js", "const y = tf.einsum('ij,jk', a, b);\n"),
    "ts_tf_matmul": ("ts", "const y: tf.Tensor = tf.matMul(a, b);\n"),
}
QUIET = {
    "py_decorator": ("py", "@app.route('/x')\ndef f():\n    return 1\n"),
    "py_email_string": ("py", "e = 'a@example.com'\n"),
    "py_commented": ("py", "# y = a.mm(b)\n"),
    "py_bare_names": ("py", "mm = 25.4\nouter = inner = 0\n"),
    "py_sh_mv": ("py", "sh.mv('a', 'b')\n"),
    "js_mul": ("js", "const y = tf.mul(a, b);\n"),
    "js_plain_name": ("js", "const matMulResult = 1;\n"),
    "ts_plain_name": ("ts", "const einsumCount: number = 1;\n"),
}
# False positives: the js/ts rule is `\\b(dot|cross|multiply)\\s*\\(` with no tensor context, so scalar arithmetic reads as
# a tensor product. Strict xfail (sibling gap): tightening it needs a receiver or import contract and moves the golden.
FALSE_POS = {
    "js_scalar_multiply": ("js", "const total = multiply(price, qty);\n"),
    "ts_cart_cross": ("ts", "const r = cart.cross(item);\n"),
}
# Shapes the rules do not read: sibling gaps, each a different mechanism.
GAPS = {
    "py_np_cross": ("py", "y = np.cross(a, b)\n"),
    "py_torch_linalg_solve": ("py", "y = torch.linalg.solve(a, b)\n"),
}


def _scan(tmp_path, table) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, (ext, body) in table.items():
        pad = "#" if ext == "py" else "//"
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
        return {p: n for p, n in con.execute("select file_path, vectorized_math from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    return tuple(_scan(tmp_path_factory.mktemp(k), t) for k, t in (("fire", FIRE), ("quiet", QUIET), ("gaps", GAPS), ("fp", FALSE_POS)))


@pytest.mark.parametrize("name", sorted(FIRE))
def test_tensor_product_fires_through_a_real_scan(scans, name):
    assert scans[0][f"{name}.{FIRE[name][0]}"] >= 1


@pytest.mark.parametrize("name", sorted(QUIET))
def test_near_miss_stays_zero(scans, name):
    assert scans[1][f"{name}.{QUIET[name][0]}"] == 0


@pytest.mark.xfail(strict=True, reason="sibling gap: the product or solver form is not named in the rule")
@pytest.mark.parametrize("name", sorted(GAPS))
def test_unread_shape_fires(scans, name):
    assert scans[2][f"{name}.{GAPS[name][0]}"] >= 1


@pytest.mark.xfail(strict=True, reason="sibling gap: js/ts `dot(` / `cross(` / `multiply(` need no tensor context")
@pytest.mark.parametrize("name", sorted(FALSE_POS))
def test_scalar_call_stays_zero(scans, name):
    assert scans[3][f"{name}.{FALSE_POS[name][0]}"] == 0
