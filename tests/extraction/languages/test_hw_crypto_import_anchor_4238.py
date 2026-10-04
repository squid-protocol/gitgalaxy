"""
#4238: `hardware_bridge` and `cryptography`, the last import-anchored rules, are anchored
on the library's top-level package (builders from #4150 / PR #4231) instead of matching a
library name ANYWHERE on an import line. Only python and javascript carry them.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore

_RULES = ("hardware_bridge", "cryptography")


def _rule(lang: str, key: str):
    return LANGUAGE_DEFINITIONS[lang]["rules"][key]


@pytest.mark.parametrize("key", _RULES)
def test_only_python_and_javascript_carry_the_rule(key):
    langs = sorted(k for k, d in LANGUAGE_DEFINITIONS.items() if d.get("rules", {}).get(key) is not None)
    assert langs == ["javascript", "python"]


_PY_FIRES = [
    ("hardware_bridge", "import usb.core"),
    ("hardware_bridge", "from usb import util"),
    ("hardware_bridge", "import bluetooth"),
    ("hardware_bridge", "import os, websocket"),
    ("hardware_bridge", "from websocket import create_connection"),
    ("cryptography", "import hashlib"),
    ("cryptography", "import hmac, hashlib"),
    ("cryptography", "from cryptography import x509"),
    ("cryptography", "from cryptography.hazmat.primitives import hashes"),
    ("cryptography", "from OpenSSL import crypto"),
    ("cryptography", "from OpenSSL.crypto import X509"),
    ("cryptography", "import ssl"),
    ("cryptography", "import bcrypt"),
    ("cryptography", "    import hashlib  # lazy"),
]
_PY_SILENT = [
    ("hardware_bridge", "from airflow.providers.usb.hooks import UsbHook"),
    ("hardware_bridge", "from app.printer import render"),
    ("hardware_bridge", "from . import ir_websocket"),
    ("hardware_bridge", "from scapy.layers.bluetooth import HCI"),
    ("hardware_bridge", "usb = 1"),
    ("cryptography", "from myproj.crypto.utils import hash_it"),
    ("cryptography", "from django.utils.crypto import get_random_string"),
    ("cryptography", "from scapy.layers.tls.record import TLS"),
    ("cryptography", "from .ssl_helpers import ctx"),
    ("cryptography", "import os, mypkg.tls_config"),
    ("cryptography", "from . import crypto"),
]


@pytest.mark.parametrize("key,line", _PY_FIRES)
def test_python_package_import_fires(key, line):
    assert _rule("python", key).search(line), line


@pytest.mark.parametrize("key,line", _PY_SILENT)
def test_python_library_named_path_does_not_fire(key, line):
    assert not _rule("python", key).search(line), line


_JS_FIRES = [
    ("hardware_bridge", "import { SerialPort } from 'serialport';"),
    ("hardware_bridge", "const usb = require('usb');"),
    ("hardware_bridge", "import { io } from 'socket.io-client';"),
    ("hardware_bridge", 'import "@serialport/bindings-cpp"'),
    ("hardware_bridge", "const ws = await import('websocket');"),
    ("cryptography", "import crypto from 'crypto';"),
    ("cryptography", "import { createHash } from 'node:crypto';"),
    ("cryptography", "const tls = require('node:tls');"),
    ("cryptography", "import CryptoJS from 'crypto-js';"),
    ("cryptography", "import bcrypt from 'bcrypt';"),
    ("cryptography", 'const jwt = require("jsonwebtoken");'),
    ("cryptography", "import * as x509 from '@peculiar/x509';"),
    ("cryptography", "import crypto = require('crypto')"),
]
_JS_SILENT = [
    ("hardware_bridge", "import { Foo } from './usb/driver';"),
    ("hardware_bridge", "import { P } from './printer/queue';"),
    ("hardware_bridge", "import { W } from '@bus/../tests/mock_websocket';"),
    ("hardware_bridge", "const x = require('../common/websocket');"),
    ("cryptography", "const c = require('../crypto/helpers');"),
    ("cryptography", "import x from '@/lib/ssl-utils';"),
    ("cryptography", "require('internal/crypto/util');"),
    ("cryptography", "import { m } from './crypto';"),
    ("cryptography", "import { gcTick, tls } from './common'"),
]


@pytest.mark.parametrize("key,line", _JS_FIRES)
def test_js_package_import_fires(key, line):
    assert _rule("javascript", key).search(line), line


@pytest.mark.parametrize("key,line", _JS_SILENT)
def test_js_library_named_path_does_not_fire(key, line):
    assert not _rule("javascript", key).search(line), line


def _count(lang: str, key: str, code: str) -> int:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["equations"][key]


def test_python_counts_only_real_imports_through_splice():
    code = "import hashlib\nfrom myproj.crypto.utils import h\nfrom OpenSSL import crypto\n\n\ndef f():\n    return h\n"
    assert _count("python", "cryptography", code) == 2


def test_js_counts_only_real_imports_through_splice():
    code = "import crypto from 'crypto';\nimport h from './crypto/helpers';\nconst t = require('node:tls');\n"
    assert _count("javascript", "cryptography", code) == 2


@pytest.mark.parametrize(
    "lang,payload",
    [
        ("python", "import " + "a, " * 5000 + "b"),
        ("python", "import " + "a as b , " * 3000 + "x"),
        ("python", "from usb" + "." * 10000 + " x"),
        ("python", "from cryptography" + "a" * 10000 + "!"),
        ("python", "import" + " " * 10000 + "x"),
        ("javascript", "from" + " " * 10000 + "("),
        ("javascript", "import '@" + "a" * 10000 + "x"),
        ("javascript", "require('@serialport/" + "a" * 10000 + "!"),
        ("javascript", "import 'crypto-" + "a" * 10000 + "!"),
        ("javascript", "import 'node:" + "a" * 10000),
    ],
)
@pytest.mark.parametrize("key", _RULES)
def test_hw_crypto_import_patterns_are_redos_immune(lang, key, payload):
    assert_redos_immune(_rule(lang, key), payload)
