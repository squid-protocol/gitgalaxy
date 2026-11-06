"""Dockerfile: a rule member that starts with `-` must not sit behind a leading `\\b` (#4108)."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["dockerfile"]["rules"]

FIRES = [
    ("memory_alloc", "RUN java -Xmx512m -jar app.jar"),
    ("memory_alloc", "CMD java -Xms256m -jar app.jar"),
    ("memory_alloc", "RUN node --max-old-space-size=4096 build.js"),
    ("memory_alloc", "RUN docker run --memory=512m img"),
    ("memory_alloc", "ENV JAVA_OPTS=x"),
    ("telemetry", "CMD app --log-level debug"),
    ("telemetry", "ENV LOG_LEVEL=info"),
    ("test_skip", "RUN npx jest --passWithNoTests"),
    ("test_skip", "RUN npm install --no-audit"),
]
NO_FIRE = [
    ("memory_alloc", "RUN echo x--memory=1"),
    ("memory_alloc", "RUN echo a-Xmx1"),
    ("telemetry", "CMD app x--log-level debug"),
    ("test_skip", "RUN app --no-auditing"),
    ("test_skip", "RUN app x--no-audit"),
]


@pytest.mark.parametrize(("rule", "text"), FIRES)
def test_fires(rule, text):
    assert RULES[rule].search(text)


@pytest.mark.parametrize(("rule", "text"), NO_FIRE)
def test_no_fire(rule, text):
    assert not RULES[rule].search(text)
