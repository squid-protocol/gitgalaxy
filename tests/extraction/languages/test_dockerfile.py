"""
Dockerfile extraction hardening (epic #813, issue #842). See
tests/extraction/how_to_harden_extraction.md for the methodology.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

DOCKERFILE_RULES = LANGUAGE_DEFINITIONS["dockerfile"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNC_START_VALID = [
    ("RUN apt-get update", "RUN"),
    ('cMd ["echo", "hello"]', "cMd"),
    ('EnTrYpOInT ["sh", "-c"]', "EnTrYpOInT"),
    ("hEaLtHcHeCk CMD curl -f http://localhost/", "hEaLtHcHeCk"),
]

FUNC_START_PATHOLOGICAL = [
    ('RUN \\ \n  echo "hello"', "RUN"),
    ("RUN --mount=type=cache,target=/root/.cache/pip pip install", "RUN"),
    ("RUN <<EOF\necho hello\nEOF", "RUN"),
]

FUNC_START_INVALID = [
    ('ENV MY_VAR="HEALTHCHECK NONE"'),
    ('LABEL fake_cmd="CMD echo hi"'),
    ("# RUN apt-get install -y evil"),
]


@pytest.mark.parametrize("payload,expected", FUNC_START_VALID)
def test_func_start_valid(payload, expected):
    assert_valid_match(DOCKERFILE_RULES["func_start"], payload, expected, "func_start")


@pytest.mark.parametrize("payload,expected", FUNC_START_PATHOLOGICAL)
def test_func_start_pathological(payload, expected):
    assert_pathological_match(DOCKERFILE_RULES["func_start"], payload, expected, "func_start")


@pytest.mark.parametrize("payload", FUNC_START_INVALID)
def test_func_start_invalid(payload):
    assert_invalid_no_match(DOCKERFILE_RULES["func_start"], payload, "func_start")


def test_func_start_redos():
    assert_redos_immune(DOCKERFILE_RULES["func_start"], "RUN " + " " * 50000 + "!")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_START_VALID = [
    ("FROM ubuntu:20.04", "ubuntu:20.04"),
    ("FROM ubuntu AS builder", "builder"),
    ("fRoM   --platform=linux/amd64 ubuntu", "ubuntu"),
    ("FROM scratch", "scratch"),
    ("FROM golang:${GO_VERSION}-${BASE_DEBIAN_DISTRO} AS base", "base"),
    ("FROM --platform=$BUILDPLATFORM tonistiigi/xx:${XX_VERSION} AS xx", "xx"),
    ("FROM scratch AS binary-dummy", "binary-dummy"),
    ("FROM base AS criu", "criu"),
    ("FROM debian:${BASE_DEBIAN_DISTRO}", "debian:${BASE_DEBIAN_DISTRO}"),
]

CLASS_START_INVALID = [
    ('RUN echo "FROM ubuntu"'),
    ("# FROM fake_base"),
    ('ENV BASE="FROM node:18"'),
]


@pytest.mark.parametrize("payload,expected", CLASS_START_VALID)
def test_class_start_valid(payload, expected):
    assert_valid_match(DOCKERFILE_RULES["class_start"], payload, expected, "class_start")


@pytest.mark.parametrize("payload", CLASS_START_INVALID)
def test_class_start_invalid(payload):
    assert_invalid_no_match(DOCKERFILE_RULES["class_start"], payload, "class_start")


def test_class_start_redos():
    assert_redos_immune(DOCKERFILE_RULES["class_start"], "FROM " + " " * 50000 + "!")


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_VALID = [
    ("ARG VERSION=latest", "ARG"),
    ("aRg BUILD_DATE", "aRg"),
    ('ARG MY_VAR="value with spaces"', "ARG"),
]

ARGS_INVALID = [
    ("# ARG FOO=bar"),
    ('RUN echo "ARG BAZ=qux"'),
    ('LABEL my.arg="ARG HELLO"'),
]


@pytest.mark.parametrize("payload,expected", ARGS_VALID)
def test_args_valid(payload, expected):
    assert_valid_match(DOCKERFILE_RULES["args"], payload, expected, "args")


@pytest.mark.parametrize("payload", ARGS_INVALID)
def test_args_invalid(payload):
    assert_invalid_no_match(DOCKERFILE_RULES["args"], payload, "args")


def test_args_redos():
    assert_redos_immune(DOCKERFILE_RULES["args"], "ARG " + " " * 50000 + "!")


# ==============================================================================
# DEPENDENCY_CAPTURE (_dependency_capture)
# ==============================================================================
DEP_VALID = [
    ("FROM registry.gitlab.com/org/repo:1.2.3 AS build", "registry.gitlab.com/org/repo:1.2.3"),
    ("COPY --from=builder /src /dest", "builder"),
    ("COPY --chown=1000:1000 --from=nginx:alpine /etc /etc", "nginx:alpine"),
    ("FROM --platform=linux/amd64 ubuntu:22.04 as base", "ubuntu:22.04"),
]

DEP_INVALID = [
    ("# FROM ubuntu:latest"),
    ("# COPY --from=build / /"),
    ('RUN echo "FROM alpine"'),
]


@pytest.mark.parametrize("payload,expected", DEP_VALID)
def test_dependency_valid(payload, expected):
    assert_valid_dependency_match(DOCKERFILE_RULES["_dependency_capture"], payload, expected, "_dependency_capture")


@pytest.mark.parametrize("payload", DEP_INVALID)
def test_dependency_invalid(payload):
    assert_invalid_no_match(DOCKERFILE_RULES["_dependency_capture"], payload, "_dependency_capture")


def test_dependency_redos():
    assert_redos_immune(DOCKERFILE_RULES["_dependency_capture"], "FROM " + " " * 50000 + "!")
