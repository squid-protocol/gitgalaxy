# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108: fixture probe of the thin AI-library import signals the crucible barely exercises.

`llm_api`, `llm_orchestrator`, `llm_vector_store`, `ml_traditional`, `dl_frameworks` fire on 2-4 crucible files each
(`tests/signal_coverage_baseline.json`, thin_coverage). Each is an import-anchored name list, so the probe plants one
import per listed family member (python and js), and near-miss controls that must stay at zero: a mention in a
comment or string, a bare variable named like the package, a sibling package sharing a prefix, a relative path.
Names outside the lists (faiss, llama_cpp, onnxruntime) are pinned at zero so adding one is a deliberate change.
"""

import pytest
from _timing import assert_cpu_below

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# (language, source, signal that must be exactly 1)
FIRES = {
    "py_openai": ("python", "import openai\n", "llm_api"),
    "py_anthropic_from": ("python", "from anthropic import Anthropic\n", "llm_api"),
    "js_openai": ("javascript", "import OpenAI from 'openai';\n", "llm_api"),
    "js_anthropic_scope": ("javascript", "const { Anthropic } = require('@anthropic-ai/sdk');\n", "llm_api"),
    "py_langchain": ("python", "from langchain.chains import LLMChain\n", "llm_orchestrator"),
    "py_llama_index": ("python", "from llama_index.core import VectorStoreIndex\n", "llm_orchestrator"),
    "py_langgraph": ("python", "from langgraph.graph import StateGraph\n", "llm_orchestrator"),
    "py_crewai": ("python", "import crewai\n", "llm_orchestrator"),
    "py_dspy": ("python", "import dspy\n", "llm_orchestrator"),
    "js_langchain_scope": (
        "javascript",
        "import { ChatPromptTemplate } from '@langchain/core/prompts';\n",
        "llm_orchestrator",
    ),
    "js_vercel_ai": ("javascript", "import { generateText } from 'ai';\n", "llm_orchestrator"),
    "py_chromadb": ("python", "import chromadb\n", "llm_vector_store"),
    "py_pinecone": ("python", "from pinecone import Pinecone\n", "llm_vector_store"),
    "js_chromadb": ("javascript", "import { ChromaClient } from 'chromadb';\n", "llm_vector_store"),
    "js_pinecone": ("javascript", "import { Pinecone } from '@pinecone-database/pinecone';\n", "llm_vector_store"),
    "py_sklearn": ("python", "from sklearn.ensemble import RandomForestClassifier\n", "ml_traditional"),
    "py_xgboost": ("python", "import xgboost as xgb\n", "ml_traditional"),
    "py_lightgbm": ("python", "import lightgbm\n", "ml_traditional"),
    "py_catboost": ("python", "from catboost import CatBoostClassifier\n", "ml_traditional"),
    "py_torch": ("python", "import torch\n", "dl_frameworks"),
    "py_torchvision": ("python", "from torchvision import transforms\n", "dl_frameworks"),
    "py_tensorflow": ("python", "import tensorflow as tf\n", "dl_frameworks"),
    "py_keras": ("python", "from keras.layers import Dense\n", "dl_frameworks"),
    "py_transformers": ("python", "from transformers import AutoModel\n", "dl_frameworks"),
    "js_tfjs": ("javascript", "import * as tf from '@tensorflow/tfjs';\n", "dl_frameworks"),
    "js_transformers_js": ("javascript", "import { pipeline } from '@xenova/transformers';\n", "dl_frameworks"),
}
KEYS = ("llm_api", "llm_orchestrator", "llm_vector_store", "ml_traditional", "dl_frameworks")

# (language, source): no signal in KEYS may fire
QUIET = {
    "py_comment": ("python", "# import torch\n# from openai import OpenAI\n"),
    "py_string": ("python", "s = 'import openai'\nt = \"from sklearn import svm\"\n"),
    "py_variable_names": ("python", "openai = 1\ntorch = 2\nkeras = 3\n"),
    "py_prefix_sibling": ("python", "import torch_helpers\nimport openai_utils\nimport sklearn_extra_local\n"),
    "py_attribute_use": ("python", "y = self.chromadb.query(x)\n"),
    "py_local_module": ("python", "from .openai import client\nfrom myproj.torch import net\n"),
    "js_relative": ("javascript", "import ai from './ai';\nimport openai from '../openai';\n"),
    "js_lookalike_package": ("javascript", "import x from 'ai-utils';\nimport y from 'openai-helpers';\n"),
    "js_tokenizer_runs_locally": ("javascript", "import { countTokens } from '@anthropic-ai/tokenizer';\n"),
    "js_sklearn_stated_absence": ("javascript", "import svm from 'sklearn';\n"),
    # name-list boundaries: real libraries the lists do not name (pinned so adding one is deliberate)
    "py_faiss_unlisted": ("python", "import faiss\n"),
    "py_llama_cpp_unlisted": ("python", "import llama_cpp\n"),
    "py_onnxruntime_unlisted": ("python", "import onnxruntime\n"),
    "js_onnx_unlisted": ("javascript", "import * as ort from 'onnxruntime-web';\n"),
}


def _counts(lang, text):
    counts, *_ = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).coding_analysis([(lang, text, 0)])
    return counts


@pytest.mark.parametrize("lang,text,key", list(FIRES.values()), ids=list(FIRES))
def test_listed_import_fires_exactly_its_signal(lang, text, key):
    counts = _counts(lang, text)
    got = {k: counts[k] for k in KEYS if counts[k]}
    assert got == {key: 1}, (text, got)


BOTH = {
    "py_langchain_anthropic": ("python", "from langchain_anthropic import ChatAnthropic\n"),
    "py_langchain_openai": ("python", "from langchain_openai import ChatOpenAI\n"),
    "js_ai_sdk_openai": ("javascript", "import { openai } from '@ai-sdk/openai';\n"),
}


@pytest.mark.parametrize("lang,text", list(BOTH.values()), ids=list(BOTH))
def test_provider_adapter_counts_under_both_signals(lang, text):
    counts = _counts(lang, text)
    assert {k: counts[k] for k in KEYS if counts[k]} == {"llm_api": 1, "llm_orchestrator": 1}, text


@pytest.mark.parametrize("lang,text", list(QUIET.values()), ids=list(QUIET))
def test_near_misses_and_unlisted_names_stay_quiet(lang, text):
    counts = _counts(lang, text)
    assert {k: counts[k] for k in KEYS if counts[k]} == {}, text


def test_redos_immune():
    text = "import " + "a.b, " * 4000 + "x" + " " * 5000 + "\nfrom " + "torch." * 3000 + "\n"
    js = "import x from '" + "@a/" * 4000 + "'\n" + "const y = require(" + "(" * 3000 + "\n"
    for lang, src in (("python", text), ("javascript", js)):
        assert_cpu_below(lambda lang=lang, src=src: _counts(lang, src), 5.0, what=f"{lang} AI-import probe")
