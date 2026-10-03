"""
#4137: `llm_api` ("Cloud LLM API Integrations") is anchored on the provider SDK's
top-level package, not on any import-path segment named after a provider.

The old shared shape `\\b(?:import|require|from)\\b.*?(?:openai|anthropic)\\b` fired on
`from airflow.providers.openai.hooks.openai import OpenAIHook` (airflow's OpenAI
operator, which never imports the SDK itself) and on JS/TS relative paths such as
`from './openai/client'`. Every language that carries an `llm_api` rule (python,
javascript, typescript) is covered here, and every previously-documented true positive
still fires.

The per-file count is asserted through `StructuralExtractor.splice()`, the path a scan
takes, in addition to the raw pattern.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import JS_LLM_API, PY_LLM_API

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore

_LLM_LANGS = ("python", "javascript", "typescript")


def _rule(lang: str):
    return LANGUAGE_DEFINITIONS[lang]["rules"]["llm_api"]


# ----------------------------------------------------------------------------- wiring


def test_every_llm_api_language_uses_an_anchored_pattern():
    langs = sorted(k for k, d in LANGUAGE_DEFINITIONS.items() if d.get("rules", {}).get("llm_api") is not None)
    assert langs == sorted(_LLM_LANGS)
    assert _rule("python") is PY_LLM_API
    assert _rule("javascript") is JS_LLM_API
    assert _rule("typescript") is JS_LLM_API


# ----------------------------------------------------------------------------- python

_PY_SDK_IMPORTS = [
    "import openai",
    "import anthropic",
    "import openai as oa",
    "import openai.types",
    "import os, openai",
    "import numpy as np, anthropic",
    "from openai import OpenAI",
    "from openai import (\n    OpenAI,\n    AsyncOpenAI,\n)",
    "from openai.types.chat import ChatCompletion",
    "from anthropic import Anthropic, AsyncAnthropic",
    "from anthropic.types import Message",
    "    import openai  # lazy import inside a function",
    "x = 1; import anthropic",
    "from langchain_openai import ChatOpenAI",
    "from langchain_anthropic import ChatAnthropic",
]

_PY_NOT_SDK = [
    # the #4137 report: airflow's own provider package, not the SDK
    "from airflow.providers.openai.hooks.openai import OpenAIHook",
    "from airflow.providers.openai.operators.openai import OpenAIEmbeddingOperator",
    "import airflow.providers.openai",
    "import airflow.providers.anthropic.hooks.anthropic as hook",
    "from airflow.providers import openai",
    "from llama_index.llms.openai import OpenAI",
    # relative / local modules named after a provider
    "from . import openai",
    "from .openai import client",
    "from ..anthropic import helpers",
    "from myapp.openai_utils import wrap",
    # a provider name that is only a prefix/suffix of another module
    "import openai_compat",
    "from openaix import thing",
    "import my_anthropic",
    # non-import mentions
    "client = openai.OpenAI()",
    "provider = 'openai'",
    "important = openai",
]


@pytest.mark.parametrize("line", _PY_SDK_IMPORTS)
def test_python_sdk_import_fires(line):
    assert PY_LLM_API.search(line), line


@pytest.mark.parametrize("line", _PY_NOT_SDK)
def test_python_provider_named_path_does_not_fire(line):
    assert not PY_LLM_API.search(line), line


# ----------------------------------------------------------------------------- js / ts

_JS_SDK_IMPORTS = [
    "import OpenAI from 'openai';",
    'import OpenAI, { toFile } from "openai";',
    "import type { ChatCompletion } from 'openai/resources/chat';",
    "import 'openai/shims/node';",
    "const OpenAI = require('openai');",
    'const { OpenAI } = require ( "openai" );',
    "const mod = await import('openai');",
    "export * from 'openai';",
    "import Anthropic from '@anthropic-ai/sdk';",
    "const Anthropic = require('@anthropic-ai/sdk');",
    "import { AnthropicBedrock } from '@anthropic-ai/bedrock-sdk';",
    "import { Messages } from '@anthropic-ai/sdk/resources/messages';",
    "import { Agent } from '@openai/agents';",
    "import { openai } from '@ai-sdk/openai';",
    "import { anthropic } from '@ai-sdk/anthropic';",
    "import { AzureOpenAI } from '@azure/openai';",
    "import { ChatOpenAI } from '@langchain/openai';",
    "import x = require('openai');",
    "import Anthropic from `anthropic`;",
]

_JS_NOT_SDK = [
    # local / relative / aliased paths named after a provider
    "import { client } from './openai/client';",
    "import openai from './openai';",
    "import { wrap } from '../anthropic/wrap';",
    "const helper = require('./providers/openai');",
    "import { x } from '@/openai/x';",
    "import { x } from '~/anthropic';",
    "import { x } from 'src/providers/openai';",
    "const m = await import('./openai.js');",
    # packages that only share a prefix/suffix with a provider name
    "import tiktoken from 'openai-tiktoken-counter';",
    "import x from 'my-openai';",
    "import { y } from '@acme/openai-utils';",
    # non-import mentions
    "const provider = 'openai';",
    "client.chat.completions.create({ model: 'gpt-4o' });",
    "import axios from 'axios';",
]


@pytest.mark.parametrize("line", _JS_SDK_IMPORTS)
def test_js_ts_sdk_import_fires(line):
    assert JS_LLM_API.search(line), line


@pytest.mark.parametrize("line", _JS_NOT_SDK)
def test_js_ts_provider_named_path_does_not_fire(line):
    assert not JS_LLM_API.search(line), line


# ----------------------------------------------------------------------------- splice path


def _llm_api(lang: str, code: str) -> int:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["equations"]["llm_api"]


def test_airflow_openai_operator_counts_zero_through_splice():
    code = (
        "from __future__ import annotations\n"
        "from airflow.models import BaseOperator\n"
        "from airflow.providers.openai.hooks.openai import OpenAIHook\n\n\n"
        "class OpenAIEmbeddingOperator(BaseOperator):\n"
        "    def execute(self, context):\n"
        "        return OpenAIHook(conn_id=self.conn_id).create_embeddings(self.input_text)\n"
    )
    assert _llm_api("python", code) == 0


def test_python_sdk_counts_one_per_import_through_splice():
    code = "from openai import OpenAI\nimport anthropic\n\n\ndef f():\n    return OpenAI(), anthropic.Anthropic()\n"
    assert _llm_api("python", code) == 2


@pytest.mark.parametrize("lang", ["javascript", "typescript"])
def test_js_ts_counts_only_package_specifiers_through_splice(lang):
    code = (
        "import OpenAI from 'openai';\n"
        "const Anthropic = require('@anthropic-ai/sdk');\n"
        "import { x } from './openai/client';\n"
        "function h() { return new OpenAI(); }\n"
    )
    assert _llm_api(lang, code) == 2


# ----------------------------------------------------------------------------- redos


@pytest.mark.parametrize(
    "pattern,payload",
    [
        (PY_LLM_API, "import " + "a, " * 5000 + "b"),
        (PY_LLM_API, "import " + "a as b , " * 3000 + "x"),
        (PY_LLM_API, "from openai" + "." * 10000 + " x"),
        (PY_LLM_API, "import" + " " * 10000 + "x"),
        (JS_LLM_API, "from" + " " * 10000 + "("),
        (JS_LLM_API, "import '@" + "a" * 10000 + "x"),
        (JS_LLM_API, "require('@anthropic-ai/" + "a" * 10000 + "!"),
    ],
)
def test_llm_api_patterns_are_redos_immune(pattern, payload):
    assert_redos_immune(pattern, payload)
