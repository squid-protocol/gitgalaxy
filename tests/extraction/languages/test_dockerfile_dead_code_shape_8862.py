"""Dockerfile `dead_code` reads a commented instruction, not prose (#8862, unplanted_family_contracts.md)."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULE = LANGUAGE_DEFINITIONS["dockerfile"]["rules"]["dead_code"]

CODE = [
    "# RUN apt-get update",
    "#RUN make",
    "    # COPY old-file /app",
    "# COPY --link --from=criu          /build/ /usr/local/bin/",
    "# ADD src.tar /opt",
    "# ENV A=1",
    "# EXPOSE 8080",
    "# CMD [\"app\"]",
    "# ENTRYPOINT [\"/entry.sh\"]",
    "# WORKDIR /app",
    "# FROM ubuntu:20.04",
    "# FROM scratch",
    "# FROM --platform=linux/amd64 golang:1.22 AS build",
    "# FROM golang:1.22 as build",
]
PROSE = [
    "# from the https://github.com/go-delve/delve repository.",
    "#  run one of the following from an (elevated) Windows PowerShell prompt:",
    "# FROM statement is updated, it will not work when running autogen through hack\\make.ps1.",
    "# Copy the sources into the container",
    "# just a note",
    "# env vars follow",
    "# RUN",
    "# cmd line",
]


@pytest.mark.parametrize("text", CODE)
def test_a_commented_instruction_counts(text):
    assert RULE.search(text)


@pytest.mark.parametrize("text", PROSE)
def test_prose_is_not_dead_code(text):
    assert not RULE.search(text)
