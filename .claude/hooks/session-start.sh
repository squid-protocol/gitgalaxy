#!/bin/bash
# SessionStart hook for Claude Code on the web (#3778, epic #3772).
#
# Installs what the test suite, the baseline-gated audits and the call-graph
# gates need, at CI's pins, and fetches the sibling corpora -- so a fresh cloud
# session can run `python tests/tools/callgraph_check.py` with no manual
# installs. Idempotent: a second start only confirms what is already there.
# Web sessions only; a local checkout keeps its own environment.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
PARENT="$(dirname "$PWD")"
warn() { echo "session-start: WARNING -- $*" >&2; }

# --- tiktoken only when its cl100k_base encoding can actually be fetched. An
# installed tiktoken whose encoding download is blocked makes gitgalaxy's own
# import fail (detector.py loads the encoding at import time, #3791) instead of
# falling back to Zero-Dependency Mode -- so in a network-restricted environment
# it must be absent, and full-precision golden masters are left to CI.
TIKTOKEN_URL="https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
if curl -fsS -o /dev/null --max-time 15 --head "$TIKTOKEN_URL" 2>/dev/null; then
  TIKTOKEN="tiktoken"
else
  TIKTOKEN=""
  python -m pip uninstall -y -q tiktoken >/dev/null 2>&1 || true
  warn "tiktoken's encoding host is unreachable (openaipublic.blob.core.windows.net): tiktoken left" \
       "uninstalled so scans run in Zero-Dependency Mode, and full-precision golden masters will not run" \
       "here -- allow that host in the environment's network settings, or rely on CI's crucible-audit (full-precision)"
fi

# --- python: the package, CI's test/ML/audit extras, the call-graph references
python -m pip install -q --disable-pip-version-check -e ".[yaml]" \
  networkx ${TIKTOKEN} numpy pandas xgboost \
  pytest pytest-xdist \
  mypy types-PyYAML "ruff==0.16.0" \
  "pyan3==2.8.1" tree-sitter-language-pack 2>&1 | grep -v -i "warning: running pip as" || true

# --- node: the TypeScript checker the typescript baseline is pinned to. 7.x (npm's
# `latest`) is the native port and ships no JavaScript compiler API.
TS_PIN="6.0.2"
if command -v npm >/dev/null 2>&1; then
  have="$(NODE_PATH="$(npm root -g)" node -e \
    "try{const t=require('typescript');process.stdout.write(typeof t.createProgram==='function'?t.version:'')}catch(e){}" \
    2>/dev/null || true)"
  if [ "$have" != "$TS_PIN" ]; then
    npm install --global --silent "typescript@${TS_PIN}" >/dev/null 2>&1 || warn "npm install typescript@${TS_PIN} failed"
  fi
else
  warn "no node/npm: the typescript call-graph gate cannot run"
fi

# --- PATH for the session: keep the current `node` first (another node in the
# python scripts dir would switch npm's global root away from typescript), then
# this interpreter's scripts, ahead of the uv tool shims -- so `pytest`, `mypy`
# and `ruff` are the ones that can import gitgalaxy and carry CI's pins.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  py_scripts="$(python -c 'import sysconfig; print(sysconfig.get_path("scripts"))')"
  node_dir="$(dirname "$(command -v node 2>/dev/null || echo /nonexistent/node)")"
  {
    echo "export PATH=\"${node_dir}:${py_scripts}:\$PATH\""
    echo "export NODE_PATH=\"\$(npm root -g 2>/dev/null)\""
  } >> "$CLAUDE_ENV_FILE"
fi

# --- corpora, as siblings of the checkout (never inside it: an untracked corpus
# poisons the golden masters -- .claude/rules/golden-master-guidelines.md)
CRUCIBLE_TAG="$(sed -n 's/^PINNED_TAG = "\(.*\)"/\1/p' tests/_crucible_pin.py)"
if [ ! -d "$PARENT/language-crucible/.git" ]; then
  git clone -q --branch "$CRUCIBLE_TAG" --depth 1 \
    https://github.com/squid-protocol/language-crucible.git "$PARENT/language-crucible" \
    || warn "could not clone language-crucible ${CRUCIBLE_TAG}"
fi
python tests/tools/import_graph_accuracy.py --fetch-only >/dev/null 2>&1 \
  || warn "could not fetch the pinned import-graph corpus (import_graph_accuracy.py --fetch-only)"

# --- the tag the AST accuracy audit archives its pinned corpus from (a shallow
# clone has no tags)
AST_TAG="$(sed -n 's/^CORPUS_REF = "\(.*\)"/\1/p' tests/ast_accuracy_audit.py)"
if [ -n "$AST_TAG" ] && ! git rev-parse -q --verify "refs/tags/${AST_TAG}" >/dev/null; then
  git fetch -q --depth 1 origin tag "$AST_TAG" 2>/dev/null || warn "could not fetch tag ${AST_TAG} (ast-accuracy audit)"
fi

exit 0
