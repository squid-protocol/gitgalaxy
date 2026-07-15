#!/bin/bash

# Extract UI inputs from Azure DevOps environment variables
TARGET=${INPUT_TARGET:-"."}
MAX_RISK=${INPUT_MAXRISK:-"95.0"}
FAIL_SECRETS=${INPUT_FAILONSECRETS:-"true"}

# Construct the base engine arguments
ARGS="--max-risk-exposure $MAX_RISK --sarif-only --output$(Agent.TempDirectory)/gitgalaxy-results.json"

if [ "$FAIL_SECRETS" = "true" ]; then
  ARGS="$ARGS --fail-on-secrets"
fi

echo "Installing GitGalaxy & Heavy Physics Engines..."
python -m pip install --upgrade pip
pip install gitgalaxy networkx tiktoken xgboost pandas numpy

echo "Running: galaxyscope $TARGET$ARGS"
galaxyscope $TARGET$ARGS