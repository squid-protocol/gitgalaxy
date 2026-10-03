"""
#4150: the four AI/ML import-pack rules (`llm_orchestrator`, `llm_vector_store`,
`ml_traditional`, `dl_frameworks`) are anchored on the library's top-level package,
the way #4137 / PR #4149 anchored `llm_api`.

The old shared shape `\\b(?:import|require|from)\\b.*?(?:names)\\b` fired whenever a
package name appeared ANYWHERE on an import line: `from .langchain import chain`,
`from airflow.providers.pinecone.hooks import PineconeHook`,
`from myproj.models.torch import Net`, `import { load } from './keras/loader'`.
Every language that carries one of these rules (python, javascript, typescript) is
covered, and every previously-detected real import still fires.

Ownership decisions recorded here (see _shared_patterns.py):
* python `langchain_*` distributions (`langchain_core`, `langchain_community`,
  `langchain_openai`, ...) are `llm_orchestrator`, mirroring js/ts where the
  `@langchain/*` scope always counted. `langchain_openai`/`langchain_anthropic`
  ALSO count as `llm_api` (#4149), exactly as `@langchain/openai` does in js/ts.
* js/ts scoped packages: `@langchain/*`, `@llamaindex/*` (+ `llamaindex`) ->
  orchestrator; `@pinecone-database/*` -> vector store; `@tensorflow/*`,
  `@tensorflow-models/*` (+ bare `tensorflow`/`torch`/`keras`) -> dl_frameworks.
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

_RULES = ("llm_orchestrator", "llm_vector_store", "ml_traditional", "dl_frameworks")
_LANGS = ("python", "javascript", "typescript")


def _rule(lang: str, key: str):
    return LANGUAGE_DEFINITIONS[lang]["rules"][key]


# ----------------------------------------------------------------------------- wiring


@pytest.mark.parametrize("key", _RULES)
def test_only_python_js_ts_carry_the_rule_and_js_ts_share_one_pattern(key):
    langs = sorted(k for k, d in LANGUAGE_DEFINITIONS.items() if d.get("rules", {}).get(key) is not None)
    assert langs == sorted(_LANGS)
    assert _rule("javascript", key) is _rule("typescript", key)
    assert _rule("python", key) is not _rule("javascript", key)


# ----------------------------------------------------------------------------- python

_PY_FIRES = [
    ("llm_orchestrator", "import langchain"),
    ("llm_orchestrator", "from langchain.chains import LLMChain"),
    ("llm_orchestrator", "from langchain_core.prompts import ChatPromptTemplate"),
    ("llm_orchestrator", "from langchain_community.vectorstores import FAISS"),
    ("llm_orchestrator", "from langchain_openai import ChatOpenAI"),
    ("llm_orchestrator", "from llama_index.core import VectorStoreIndex"),
    ("llm_orchestrator", "import llama_index"),
    ("llm_vector_store", "import chromadb"),
    ("llm_vector_store", "from chromadb.config import Settings"),
    ("llm_vector_store", "from pinecone import Pinecone"),
    ("llm_vector_store", "import os, pinecone"),
    ("ml_traditional", "from sklearn.model_selection import train_test_split"),
    ("ml_traditional", "import sklearn"),
    ("ml_traditional", "import numpy as np, sklearn.linear_model as lm"),
    ("dl_frameworks", "import torch"),
    ("dl_frameworks", "import torch.nn as nn"),
    ("dl_frameworks", "from torch import nn"),
    ("dl_frameworks", "from torch.utils.data import (\n    DataLoader,\n)"),
    ("dl_frameworks", "import tensorflow as tf"),
    ("dl_frameworks", "import tensorflow.compat.v1 as tf"),
    ("dl_frameworks", "from keras.layers import Dense"),
    ("dl_frameworks", "    import torch  # lazy import inside a function"),
    ("dl_frameworks", "x = 1; import keras"),
]

_PY_SILENT = [
    # the #4150 report
    ("llm_orchestrator", "from .langchain import chain"),
    ("llm_vector_store", "from airflow.providers.pinecone.hooks import PineconeHook"),
    ("llm_vector_store", "from airflow.providers.chromadb import x"),
    ("dl_frameworks", "from myproj.models.torch import Net"),
    # internal / relative modules named after a library
    ("llm_orchestrator", "from airflow.providers import langchain"),
    ("llm_orchestrator", "from . import llama_index"),
    ("llm_vector_store", "import airflow.providers.pinecone.hooks.pinecone as hook"),
    ("ml_traditional", "from ..sklearn import compat"),
    ("ml_traditional", "from mlflow.sklearn import log_model"),
    ("ml_traditional", "import mlflow.sklearn"),
    ("dl_frameworks", "from transformers.models.bert import modeling_tf_bert as tensorflow"),
    ("dl_frameworks", "from ray.train.torch import TorchTrainer"),
    ("dl_frameworks", "import mlflow.pytorch, mlflow.keras"),
    # a package name that is only a prefix of another package
    ("dl_frameworks", "import torchvision"),
    ("dl_frameworks", "from torchaudio import load"),
    ("dl_frameworks", "import tensorflow_hub as hub"),
    ("llm_vector_store", "import pinecone_text"),
    ("ml_traditional", "import sklearn_crfsuite"),
    ("llm_orchestrator", "import langchainhub"),
    # non-import mentions
    ("dl_frameworks", "model = torch.nn.Linear(3, 4)"),
    ("dl_frameworks", "important = torch"),
    ("llm_orchestrator", "backend = 'langchain'"),
]


@pytest.mark.parametrize("key,line", _PY_FIRES)
def test_python_package_import_fires(key, line):
    assert _rule("python", key).search(line), line


@pytest.mark.parametrize("key,line", _PY_SILENT)
def test_python_library_named_path_does_not_fire(key, line):
    assert not _rule("python", key).search(line), line


# ----------------------------------------------------------------------------- js / ts

_JS_FIRES = [
    ("llm_orchestrator", "import { LLMChain } from 'langchain/chains';"),
    ("llm_orchestrator", "const { OpenAI } = require('langchain/llms/openai');"),
    ("llm_orchestrator", "import { ChatPromptTemplate } from '@langchain/core/prompts';"),
    ("llm_orchestrator", "import { ChatOpenAI } from '@langchain/openai';"),
    ("llm_orchestrator", 'import { VectorStoreIndex } from "llamaindex";'),
    ("llm_orchestrator", "import { OpenAI } from '@llamaindex/openai';"),
    ("llm_vector_store", "import { ChromaClient } from 'chromadb';"),
    ("llm_vector_store", "import { Pinecone } from '@pinecone-database/pinecone';"),
    ("llm_vector_store", "const { Pinecone } = require('@pinecone-database/pinecone');"),
    ("dl_frameworks", "import * as tf from '@tensorflow/tfjs';"),
    ("dl_frameworks", "import '@tensorflow/tfjs-backend-webgl';"),
    ("dl_frameworks", "const tf = require('@tensorflow/tfjs-node');"),
    ("dl_frameworks", "import * as cocoSsd from '@tensorflow-models/coco-ssd';"),
    ("dl_frameworks", "const tf = await import('@tensorflow/tfjs');"),
]

_JS_SILENT = [
    # the #4150 report
    ("ml_traditional", "const x = require('../sklearn')"),
    ("dl_frameworks", "import { load } from './keras/loader'"),
    # local / relative / aliased paths named after a library
    ("llm_orchestrator", "import { chain } from './langchain/chain';"),
    ("llm_orchestrator", "import { x } from '@/langchain';"),
    ("llm_vector_store", "import { db } from '../pinecone';"),
    ("llm_vector_store", "import { db } from '~/chromadb/client';"),
    ("llm_vector_store", "import { db } from 'src/services/pinecone';"),
    ("dl_frameworks", "import { Net } from './models/torch';"),
    ("dl_frameworks", "const m = await import('./tensorflow.js');"),
    # packages that only share a prefix/suffix with a library name
    ("llm_vector_store", "import x from 'chromadb-default-embed';"),
    ("llm_orchestrator", "import x from 'langchain-community-helpers';"),
    ("dl_frameworks", "import x from 'keras-js';"),
    ("dl_frameworks", "import { y } from '@acme/tensorflow-utils';"),
    # non-import mentions
    ("dl_frameworks", "const backend = 'tensorflow';"),
    ("llm_orchestrator", "import axios from 'axios';"),
]


@pytest.mark.parametrize("key,line", _JS_FIRES)
@pytest.mark.parametrize("lang", ["javascript", "typescript"])
def test_js_ts_package_import_fires(lang, key, line):
    assert _rule(lang, key).search(line), line


@pytest.mark.parametrize("key,line", _JS_SILENT)
@pytest.mark.parametrize("lang", ["javascript", "typescript"])
def test_js_ts_library_named_path_does_not_fire(lang, key, line):
    assert not _rule(lang, key).search(line), line


# ----------------------------------------------------------------------------- splice path


def _count(lang: str, key: str, code: str) -> int:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["equations"][key]


def test_python_counts_one_per_real_import_through_splice():
    code = (
        "import torch\n"
        "from torch import nn\n"
        "from myproj.models.torch import Net\n"
        "from ray.train.torch import TorchTrainer\n\n\n"
        "def f():\n"
        "    return nn.Linear(2, 3), Net(), TorchTrainer\n"
    )
    assert _count("python", "dl_frameworks", code) == 2


def test_airflow_pinecone_hook_counts_zero_through_splice():
    code = (
        "from airflow.models import BaseOperator\n"
        "from airflow.providers.pinecone.hooks.pinecone import PineconeHook\n\n\n"
        "class PineconeIngestOperator(BaseOperator):\n"
        "    def execute(self, context):\n"
        "        return PineconeHook(conn_id=self.conn_id).upsert(self.input_vectors)\n"
    )
    assert _count("python", "llm_vector_store", code) == 0


@pytest.mark.parametrize("lang", ["javascript", "typescript"])
def test_js_ts_counts_only_package_specifiers_through_splice(lang):
    code = (
        "import * as tf from '@tensorflow/tfjs';\n"
        "const keras = require('./keras/loader');\n"
        "import { Net } from '../models/torch';\n"
        "function h() { return tf.tensor([1]); }\n"
    )
    assert _count(lang, "dl_frameworks", code) == 1


# ----------------------------------------------------------------------------- redos


@pytest.mark.parametrize(
    "lang,payload",
    [
        ("python", "import " + "a, " * 5000 + "b"),
        ("python", "import " + "a as b , " * 3000 + "x"),
        ("python", "from torch" + "." * 10000 + " x"),
        ("python", "from langchain_" + "a" * 10000 + "!"),
        ("python", "import" + " " * 10000 + "x"),
        ("javascript", "from" + " " * 10000 + "("),
        ("javascript", "import '@" + "a" * 10000 + "x"),
        ("javascript", "require('@tensorflow/" + "a" * 10000 + "!"),
        ("javascript", "import '@langchain/" + "a" * 10000 + "!"),
    ],
)
@pytest.mark.parametrize("key", _RULES)
def test_ai_ml_import_patterns_are_redos_immune(lang, key, payload):
    assert_redos_immune(_rule(lang, key), payload)
