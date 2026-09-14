"""
--max-systemic-threat multiplies each file's cumulative risk by its PageRank
blast radius, which only networkx computes. Without networkx every blast radius
is a 0.0 placeholder, so the gate could never fail -- a CI job relying on it was
silently unprotected. It must now say so and be skipped, and behave exactly as
before whenever networkx is available.
"""

import logging
from unittest.mock import patch

from gitgalaxy.galaxyscope import Orchestrator


def test_ceiling_is_skipped_with_a_warning_without_networkx(caplog):
    with patch("gitgalaxy.galaxyscope.HAS_NETWORKX", False), caplog.at_level(logging.WARNING, logger="GalaxyScope"):
        assert Orchestrator._effective_systemic_threat_ceiling(40.0) == 0.0
    assert "--max-systemic-threat 40.0 was NOT evaluated" in caplog.text
    assert "networkx" in caplog.text


def test_ceiling_is_enforced_with_networkx(caplog):
    with patch("gitgalaxy.galaxyscope.HAS_NETWORKX", True), caplog.at_level(logging.WARNING, logger="GalaxyScope"):
        assert Orchestrator._effective_systemic_threat_ceiling(40.0) == 40.0
    assert "NOT evaluated" not in caplog.text


def test_an_unset_ceiling_warns_about_nothing(caplog):
    with patch("gitgalaxy.galaxyscope.HAS_NETWORKX", False), caplog.at_level(logging.WARNING, logger="GalaxyScope"):
        assert Orchestrator._effective_systemic_threat_ceiling(0.0) == 0.0
    assert caplog.text == ""
