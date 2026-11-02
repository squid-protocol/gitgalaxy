# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 10: per-signal probe of Vectorized Math & Tensor Operations (`vectorized_math`).

Tensor product forms that used to read 0 (torch methods, module-qualified numpy/torch products, tf.js camelCase),
with near-miss controls (ordinary names that share a spelling) that must stay at zero, and a ReDoS control.
"""

import time

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FIRES = {
    "torch_mm_method": ("python", "y = a.mm(b)\n"),
    "torch_addmm": ("python", "y = torch.addmm(c, a, b)\n"),
    "torch_baddbmm": ("python", "y = x.baddbmm(c, a, b)\n"),
    "torch_mv": ("python", "y = torch.mv(a, b)\n"),
    "np_inner": ("python", "y = np.inner(a, b)\n"),
    "np_outer": ("python", "y = np.outer(a, b)\n"),
    "jnp_kron": ("python", "y = jnp.kron(a, b)\n"),
    "scipy_sparse_kron": ("python", "y = scipy.sparse.kron(a, b)\n"),
    "tf_linalg_matvec": ("python", "y = tf.linalg.matvec(a, b)\n"),
    "tfjs_matmul_js": ("javascript", "const y = tf.matMul(a, b);\n"),
    "tfjs_batch_matmul_js": ("javascript", "const y = tf.batchMatMul(a, b);\n"),
    "tfjs_einsum_js": ("javascript", "const y = tf.einsum('ij,jk', a, b);\n"),
    "tfjs_outer_js": ("javascript", "const y = tf.outerProduct(a, b);\n"),
    "tfjs_matmul_ts": ("typescript", "const y: tf.Tensor = tf.matMul(a, b);\n"),
    "tfjs_einsum_ts": ("typescript", "const y = tf.einsum('ij,jk', a, b);\n"),
}
QUIET = {
    "py_bare_mm_name": ("python", "mm = 25.4\nmv = 1\n"),
    "py_inner_outer_names": ("python", "outer = inner = 0\nx = self.outer\n"),
    "py_sh_mv": ("python", 'sh.mv("a", "b")\n'),
    "py_unqualified_inner_call": ("python", "y = self.inner(a)\n"),
    "py_commented": ("python", "# y = a.mm(b)\n"),
    "py_in_string": ("python", 's = "np.outer(a, b)"\n'),
    "js_mul": ("javascript", "const y = tf.mul(a, b);\n"),
    "js_plain_name": ("javascript", "const matMulResult = 1;\n"),
}


def _count(lang, text):
    counts, *_ = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).coding_analysis([(lang, text, 0)])
    return counts["vectorized_math"]


@pytest.mark.parametrize("lang,text", list(FIRES.values()), ids=list(FIRES))
def test_missed_product_forms_fire(lang, text):
    assert _count(lang, text) == 1, text


@pytest.mark.parametrize("lang,text", list(QUIET.values()), ids=list(QUIET))
def test_near_misses_stay_quiet(lang, text):
    assert _count(lang, text) == 0, text


def test_redos_immune():
    text = "a" + ".mm" * 4000 + " " * 5000 + "\nnp." + "linalg." * 3000 + "\n"
    for lang in ("python", "javascript"):
        t = time.perf_counter()
        _count(lang, text)
        assert time.perf_counter() - t < 5
