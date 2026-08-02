import json
import struct

import pytest

# Adjust this import to match your project structure
from gitgalaxy.metrics.tensor_scanner import TensorScanner


@pytest.fixture
def scanner():
    """Initializes the Tensor Scanner."""
    return TensorScanner()


# ==============================================================================
# TEST 1: SAFETENSORS BINARY PARSING (Exact Parameter Calculation)
# ==============================================================================
def test_tensor_scanner_safetensors_success(scanner, tmp_path):
    """
    Proves the scanner correctly unpacks the uint64 header, reads the JSON,
    and multiplies the tensor shapes to calculate the exact parameter count.
    """
    # 1. Create a mock Safetensors JSON header
    header_data = {
        "__metadata__": {"format": "pt", "architecture": "LlamaForCausalLM"},
        "layer_0.weight": {
            "dtype": "F16",
            "shape": [4096, 4096],
            "data_offsets": [0, 33554432],
        },  # 16,777,216 params
        "layer_0.bias": {
            "dtype": "F16",
            "shape": [4096],
            "data_offsets": [33554432, 33562624],
        },  # 4,096 params
    }

    header_json = json.dumps(header_data).encode("utf-8")
    header_size = len(header_json)

    # 2. Pack the 8-byte little-endian uint64 size, followed by the JSON string
    binary_payload = struct.pack("<Q", header_size) + header_json

    st_file = tmp_path / "mock_model.safetensors"
    st_file.write_bytes(binary_payload)

    # 3. Audit the model
    result = scanner.audit_model(str(st_file))

    # 16,777,216 + 4,096 = 16,781,312 total parameters
    assert result["architecture"] == "LlamaForCausalLM"
    assert result["raw_param_count"] == 16781312
    assert result["parameters"] == "16.8M", "Failed to properly format the parameter count!"


# ==============================================================================
# TEST 2: GGUF BINARY PARSING & HEURISTICS
# ==============================================================================
def test_tensor_scanner_gguf_success(scanner, tmp_path):
    """
    Proves the scanner validates the GGUF magic bytes and successfully extracts
    quantization and architecture clues from the raw binary stream.
    """
    # 1. Create a mock GGUF file (Magic 'GGUF' followed by random binary noise and our ASCII clues)
    binary_payload = (
        b"GGUF\x02\x00\x00\x00" + b"\x88\x99\xaa\xbb" + b"model.architecture...mistral...quantization...Q4_K"
    )

    gguf_file = tmp_path / "mock_mistral.gguf"
    gguf_file.write_bytes(binary_payload)

    result = scanner.audit_model(str(gguf_file))

    assert result["architecture"] == "Mistral Architecture"
    assert result["quantization"] == "4-Bit (Q4_K)"


def test_tensor_scanner_gguf_bad_magic(scanner, tmp_path):
    """Proves the scanner safely rejects corrupted files missing the magic bytes."""
    binary_payload = b"BADF\x02\x00\x00\x00"  # 'BADF' instead of 'GGUF'

    bad_file = tmp_path / "corrupt.gguf"
    bad_file.write_bytes(binary_payload)

    result = scanner.audit_model(str(bad_file))

    assert result["architecture"] == "Corrupted/Unknown"
    assert result["parameters"] == "Error"


# ==============================================================================
# TEST 3: DOS / MEMORY BOMB GUARD (Safetensors OOM Protection)
# ==============================================================================
def test_tensor_scanner_safetensors_massive_header(scanner, tmp_path):
    """
    Proves that a maliciously crafted safetensors file claiming to have an
    absurdly large JSON header (e.g., 101MB) is safely rejected before reading.
    """
    # 101 MB in bytes
    massive_size = 101 * 1024 * 1024

    # Pack the massive size into the 8-byte header
    binary_payload = struct.pack("<Q", massive_size) + b"fake_data"

    st_file = tmp_path / "malicious.safetensors"
    st_file.write_bytes(binary_payload)

    result = scanner.audit_model(str(st_file))

    assert result["architecture"] == "Corrupted/Unknown", "Failed to block the massive Memory Bomb trap!"
    assert result["parameters"] == "Error"


# ==============================================================================
# TEST 4: PARAMETER FORMATTING
# ==============================================================================
def test_tensor_scanner_param_formatting(scanner):
    """Proves the engine accurately translates raw parameters into human scales."""
    assert scanner._format_params(0) == "Unknown"
    assert scanner._format_params(500) == "500"
    assert scanner._format_params(7_100_000) == "7.1M"
    assert scanner._format_params(70_200_000_000) == "70.2B"
