# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 7: per-signal probe of Global Environment Mutation (`state_mutation`, "Prototype Pollution &
Global State Flux").

Planted forms the rule used to miss (a property write through `__proto__`, a descriptor / merge call aimed at
`Object.prototype`, loader and runtime variables written through the environment) and near-miss controls that
must stay at zero (ordinary configuration, reads, `Foo.prototype` mixins, comparisons).
"""

import time

import pytest

from gitgalaxy.security.security_lens import SecurityLens

FIRES = {
    "proto_dot_write": "o.__proto__.admin = 1\n",
    "proto_bracket_write": 'o["__proto__"]["admin"] = true\n',
    "define_on_object_prototype": "Object.defineProperty(Object.prototype, 'x', {value: 1})\n",
    "assign_into_object_prototype": "Object.assign(Object.prototype, payload)\n",
    "set_proto_of_object_prototype": "Object.setPrototypeOf(Object.prototype, evil)\n",
    "window_xhr": "window.XMLHttpRequest = Fake\n",
    "global_buffer": "globalThis.Buffer = B\n",
    "py_environ_ld_preload": "os.environ['LD_PRELOAD'] = '/tmp/x.so'\n",
    "py_environ_pythonpath": 'os.environ["PYTHONPATH"] = "/tmp/evil"\n',
    "py_putenv": "os.putenv('LD_LIBRARY_PATH', '/tmp')\n",
    "node_env_options": "process.env.NODE_OPTIONS = '--require /tmp/x.js'\n",
    "go_setenv": 'os.Setenv("LD_PRELOAD", "/tmp/x.so")\n',
    "php_putenv": "putenv('DYLD_INSERT_LIBRARIES=/tmp/x.dylib');\n",
}
QUIET = {
    "mixin_on_class_prototype": "Object.assign(Foo.prototype, mixin)\n",
    "define_on_class_prototype": "Object.defineProperty(Foo.prototype, 'x', {value: 1})\n",
    "proto_read": "var p = o.__proto__.admin\n",
    "proto_comparison": "if (o.__proto__.admin == 1) {}\n",
    "environ_read": "p = os.environ['PYTHONPATH']\n",
    "environ_other_var": "os.environ['HOME'] = '/tmp'\n",
    "environ_comparison": "if os.environ['PYTHONPATH'] == 'x': pass\n",
    "putenv_other_var": "os.putenv('TZ', 'UTC')\n",
    "node_env_other_var": "process.env.NODE_ENV = 'test'\n",
    "node_env_read": "x = process.env.NODE_OPTIONS\n",
    "window_other_property": "window.title = 'x'\n",
}


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


@pytest.mark.parametrize("name", FIRES)
def test_missed_form_now_fires(lens, name):
    assert lens.scan_content(FIRES[name])["counts"].get("state_mutation", 0) >= 1


@pytest.mark.parametrize("name", QUIET)
def test_near_miss_stays_quiet(lens, name):
    assert lens.scan_content(QUIET[name])["counts"].get("state_mutation", 0) == 0


def test_long_lines_are_not_a_redos_shape(lens):
    start = time.perf_counter()
    lens.scan_content("o" + ".__proto__" * 400 + "\n" + 'x["__proto__"]' * 300 + "\n" + "environ[" * 500 + "\n")
    assert time.perf_counter() - start < 2
