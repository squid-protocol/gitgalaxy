from unittest.mock import patch

import pytest

# Adjust this import to match your project structure
from gitgalaxy.metrics.statistical_auditor import StatisticalAuditor

# ==============================================================================
# MOCK HARDWARE CALIBRATION
# ==============================================================================
# We provide mock language definitions so the auditor knows which languages
# have active logic sensors (preventing them from passing through the Inert Gate).

MOCK_LANG_DEFS = {
    "cpp": {"rules": {"branch": 1, "args": 1, "structural_boundaries": 1, "pointers": 1, "memory_alloc": 1}},
    "c": {"rules": {"branch": 1, "args": 1, "structural_boundaries": 1, "pointers": 1, "memory_alloc": 1}},
    "python": {"rules": {"branch": 1, "args": 1, "structural_boundaries": 1}},
    "json": {"rules": {}},  # Inert data format (0 logic signals)
}


@pytest.fixture
def auditor():
    """Initializes the Statistical Auditor with controlled definitions."""
    return StatisticalAuditor(lang_defs=MOCK_LANG_DEFS)


# ==============================================================================
# TEST 1: THE HEURISTIC CONSENSUS ENGINE (Exact Extension Match)
# ==============================================================================
def test_auditor_consensus_engine(auditor):
    """
    Proves that the engine uses the ecosystem's confident files to rescue
    and reclassify ambiguous/unresolved files with the same extension.
    """
    files = [
        # 4 Confident Core files
        {"path": "a.cpp", "lang_id": "cpp", "telemetry": {"identity_lock_tier": 1}},
        {"path": "b.cpp", "lang_id": "cpp", "telemetry": {"identity_lock_tier": 1}},
        {"path": "c.cpp", "lang_id": "cpp", "telemetry": {"identity_lock_tier": 1}},
        {"path": "d.cpp", "lang_id": "cpp", "telemetry": {"identity_lock_tier": 1}},
        # 1 Ambiguous File (Tier 4 / Unknown)
        {
            "path": "mystery.cpp",
            "name": "mystery.cpp",
            "lang_id": "unknown",
            "telemetry": {"identity_lock_tier": 4},
        },
    ]

    # We must patch the blended and sample guard so they don't interfere with this specific test
    with patch.object(StatisticalAuditor, "_is_highly_blended", return_value=False):
        verified, unparsable = auditor.audit(files)

    assert len(verified) == 5, "Consensus Engine failed to rescue the ambiguous file!"

    mystery_file = next((f for f in verified if f["path"] == "mystery.cpp"), None)
    assert mystery_file is not None
    assert mystery_file["lang_id"] == "cpp", "Failed to inherit the ecosystem consensus!"
    assert mystery_file["telemetry"]["identity_lock_tier"] == 2, "Failed to elevate the lock tier!"


# ==============================================================================
# TEST 2: THE ZERO-DENSITY THRESHOLD (Data Dump Guard)
# ==============================================================================
def test_auditor_zero_density_threshold(auditor):
    """
    Proves that a massive file with 0 structural logic is relegated to the Exclusion Queue,
    EVEN IF it has a Tier 0 Convergent Lock bypassing the Low-Sample Guard.
    """
    files = [
        {
            "path": "data_dump.cpp",
            "name": "data_dump.cpp",
            "lang_id": "cpp",
            "coding_loc": 150,  # > 50
            "equations": {"branch": 0, "structural_boundaries": 0},  # 0 logic signals
            "telemetry": {
                "identity_lock_tier": 0,  # <-- Tier 0 Bypass for the Low-Sample Guard!
                "identity_source_proof": "Absolute Override",
            },
        }
    ]

    verified, unparsable = auditor.audit(files)

    assert len(verified) == 0
    assert len(unparsable) == 1
    assert "Zero-Density Threshold" in unparsable[0]["reason"], "Failed to trigger the Zero-Density Threshold!"


# ==============================================================================
# TEST 3: THE PACKED PAYLOAD GUARD (Impossible Density)
# ==============================================================================
def test_auditor_packed_payload_guard(auditor):
    """Proves that a file with >3.0 signals per line is relegated as obscured noise."""
    files = [
        {
            "path": "packed_logic.cpp",
            "name": "packed_logic.cpp",
            "lang_id": "cpp",
            "coding_loc": 40,
            "equations": {"branch": 200, "structural_boundaries": 100},
            "telemetry": {"identity_lock_tier": 0},  # <--- CHANGE TO 0 (Bypass Low-Sample Guard)
        }
    ]

    verified, unparsable = auditor.audit(files)

    assert len(verified) == 0
    assert len(unparsable) == 1
    assert "Packed Payload Guard" in unparsable[0]["reason"], "Failed to trigger the Packed Payload Guard!"


# ==============================================================================
# TEST 4: THE THREAT QUARANTINE (Malware Override)
# ==============================================================================
def test_auditor_threat_quarantine_guard(auditor):
    """
    Proves that a file failing the Zero-Density Threshold is forcefully saved onto the map
    if it contains an active security signature.
    """
    files = [
        {
            "path": "malware.cpp",
            "name": "malware.cpp",
            "lang_id": "cpp",
            "coding_loc": 100,
            "equations": {"sec_high_risk_execution": 1},
            "telemetry": {"identity_lock_tier": 0},  # <--- Bypasses the Low-Sample Guard
        }
    ]

    verified, unparsable = auditor.audit(files)

    assert len(verified) == 1, "Threat Quarantine failed to save the malicious file!"
    assert len(unparsable) == 0
    assert verified[0].get("is_quarantined") is True, "Failed to inject the quarantine flag!"


# ==============================================================================
# TEST 5: THE LOW-SAMPLE THRESHOLD GUARD (Hallucination Stripping)
# ==============================================================================
def test_auditor_low_sample_threshold_guard(auditor):
    """
    Proves that a tiny population (1 file) with a weak confidence tier gets
    its hallucinated language stripped and reverted to plaintext.
    """
    files = [
        {
            "path": "weird_file.python",
            "name": "weird_file.python",
            "lang_id": "python",
            "coding_loc": 10,
            "equations": {"branch": 5},
            "telemetry": {"identity_lock_tier": 3},  # <--- CHANGE TO 3 (Survives Gate 0, Dies to Low-Sample Guard)
        }
    ]

    with patch.object(auditor, "_is_highly_blended", return_value=False):
        verified, unparsable = auditor.audit(files)

    assert len(verified) == 1
    assert verified[0]["lang_id"] == "plaintext", "Low-Sample Guard failed to strip the hallucinated language!"
    assert "Low-Sample Guard Fallback" in verified[0]["telemetry"]["identity_source_proof"]


# ==============================================================================
# TEST 6: THE DEAD CODE BYPASS
# ==============================================================================
def test_auditor_dead_code_bypass(auditor):
    """
    Proves that a file heavily weighted with comments/dead code that triggers
    a density exclusion is saved via the Dead Code Bypass.
    """
    files = [
        {
            "path": "graveyard.cpp",
            "name": "graveyard.cpp",
            "lang_id": "cpp",
            "coding_loc": 100,
            "equations": {"branch": 0, "structural_boundaries": 0},  # Would normally fail Zero-Density
            "doc_loc": 600,  # Massive comment-to-code ratio triggers dead code bypass
            "telemetry": {"identity_lock_tier": 0},
        }
    ]

    verified, unparsable = auditor.audit(files)

    assert len(verified) == 1, "Dead Code Bypass failed to save the commented file!"
    assert verified[0].get("is_necrotic") is True, "Failed to flag file as Dead Code!"


# ==============================================================================
# TEST 7: STATISTICAL MAD OUTLIER DETECTION (Z-Score Math)
# ==============================================================================
def test_auditor_statistical_mad_outliers(auditor):
    """
    Creates a mathematically significant population (N=50) to build a baseline,
    then injects a 'hollow' statistical outlier to prove the Z-Score math drops it.
    """
    # Create 50 normal files with a perfectly uniform density (rho = 2.5)
    files = [
        {
            "path": f"normal_{i}.cpp",
            "name": f"normal_{i}.cpp",
            "lang_id": "cpp",
            "coding_loc": 10,
            "equations": {"branch": 25},  # 25 / 10 = 2.5 rho
            "telemetry": {"identity_lock_tier": 0, "identity_confidence": 0.95},
        }
        for i in range(50)
    ]

    # Inject 1 hollow outlier (rho = 0.1).
    # Bypasses 50/0 Law (loc < 50, rho > 0), but is mathematically anomalous.
    files.append(
        {
            "path": "outlier.cpp",
            "name": "outlier.cpp",
            "lang_id": "cpp",
            "coding_loc": 10,
            "equations": {"branch": 1},  # 1 / 10 = 0.1 rho
            "telemetry": {"identity_lock_tier": 0, "identity_confidence": 0.95},
        }
    )

    with patch.object(auditor, "_is_highly_blended", return_value=False):
        verified, unparsable = auditor.audit(files)

    # 50 survive, 1 is relegated to the Exclusion Queue
    assert len(verified) == 50
    assert len(unparsable) == 1
    assert "Statistical Anomaly" in unparsable[0]["reason"], "MAD Z-Score math failed to detect the outlier!"


# ==============================================================================
# TEST 8: THE GLOBAL C-FAMILY HEADER FALLBACK
# ==============================================================================
def test_auditor_c_family_header_fallback(auditor):
    """
    Proves that if an ambiguous header file (.h) lacks a direct 80% consensus match,
    it falls back to the dominant C-Family language in the global repository.
    """
    files = [
        # Establish a global macro-state dominated by 'c'.
        # Tier 0 locks ensure the tiny population survives the Low-Sample Guard.
        {"path": "1.c", "lang_id": "c", "telemetry": {"identity_lock_tier": 0}},
        {"path": "2.c", "lang_id": "c", "telemetry": {"identity_lock_tier": 0}},
        {"path": "3.cpp", "lang_id": "cpp", "telemetry": {"identity_lock_tier": 1}},
        # Ambiguous header file
        {
            "path": "shared.h",
            "name": "shared.h",
            "lang_id": "unknown",
            "telemetry": {"identity_lock_tier": 4},
        },
    ]

    with patch.object(StatisticalAuditor, "_is_highly_blended", return_value=False):
        verified, _ = auditor.audit(files)

    header = next((f for f in verified if f["path"] == "shared.h"), None)
    assert header is not None
    assert header["lang_id"] == "c", "Global C-Family fallback failed to assign the dominant repository language!"
    assert "Global C-Family Dominance" in header["telemetry"]["identity_source_proof"]


# ==============================================================================
# TEST 9: INERT DATA FORMAT BYPASS
# ==============================================================================
def test_auditor_inert_data_bypass(auditor):
    """
    Proves that data formats with no active logic signals (like JSON)
    skip all statistical density checks entirely.
    """
    files = [
        {
            "path": "data.json",
            "name": "data.json",
            "lang_id": "json",  # Configured in MOCK_LANG_DEFS with 0 signals
            "coding_loc": 1000,
            "equations": {},
            "telemetry": {"identity_lock_tier": 0},
        }
    ]

    verified, unparsable = auditor.audit(files)

    assert len(verified) == 1, "Inert data was incorrectly audited!"
    assert len(unparsable) == 0
