#!/bin/bash
set -e

echo "============================================================"
echo "    GitGalaxy Extraction Hardening & Crucible Automator"
echo "============================================================"
echo ""
echo "[1/4] Running pytest to ensure all static analysis and extraction rules pass..."
venv/bin/pytest tests/core_engine/test_language_standards_strict.py tests/extraction/
echo "✅ Pytest passed!"
echo ""
echo "[2/4] Regenerating Golden Masters (Full Precision and Zero Dependency)..."
venv/bin/python tests/tools/crucible_check.py --update --yes
echo "✅ Golden Masters updated!"
echo ""
echo "[3/4] Staging ONLY the modified golden master files..."
git add tests/golden_master_audit.json tests/golden_master_zero_dep_audit.json
echo "✅ Golden masters staged."
echo ""
echo "[4/4] Status check:"
git status -s
echo ""
echo "Done! The golden masters have been safely updated and staged. You can now commit."
