# ==============================================================================
# GitGalaxy
# Phase 7.8: Tensor Scanner (AI Artifact Inspection)
# ==============================================================================

# galaxyscope:ignore sec_io


import json
import struct
import math
import logging
from pathlib import Path
from typing import Dict, Any


class TensorScanner:
    """
    Surgically inspects massive AI model binaries (.safetensors, .gguf)
    without loading them into RAM. Extracts parameter counts, quantization,
    and architecture families from binary headers.
    """

    def __init__(self, parent_logger: logging.Logger = None):
        self.logger = parent_logger.getChild("tensor_scanner") if parent_logger else logging.getLogger("tensor_scanner")

    def audit_model(self, file_path: str) -> Dict[str, Any]:
        """Routes the binary to the correct header parser."""
        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".safetensors":
                return self._parse_safetensors(file_path)
            elif ext == ".gguf":
                return self._parse_gguf(file_path)
            else:
                return {
                    "architecture": "Unknown",
                    "parameters": "Unknown",
                    "quantization": "Unknown",
                }
        except Exception as e:
            self.logger.warning(f"Tensor Scanner failed to parse {file_path}: {e}")
            return {
                "architecture": "Corrupted/Unknown",
                "parameters": "Error",
                "quantization": "Error",
            }

    def _parse_safetensors(self, file_path: str) -> Dict[str, Any]:
        """
        Safetensors format:
        [8 bytes (uint64 little-endian) = N] -> [N bytes of JSON metadata] -> [Binary Tensor Data]
        """
        with open(file_path, "rb") as f:
            # ==================================================================
            # DEFENSIVE ARCHITECTURE: O(1) Memory Footprint
            # We explicitly do NOT use `torch.load()` or `safetensors.safe_open()`.
            # Loading a 70B parameter model into RAM would instantly trigger an
            # OOM (Out of Memory) kill in CI/CD pipelines. By only reading the
            # first 8 bytes to extract the JSON header size, we keep the memory
            # footprint microscopic.
            # ==================================================================
            header_size_bytes = f.read(8)
            if len(header_size_bytes) < 8:
                raise ValueError("File too small to be a valid safetensors file.")

            header_size = struct.unpack("<Q", header_size_bytes)[0]

            # ==================================================================
            # DEFENSIVE ARCHITECTURE: Denial of Service (DoS) / Memory Bomb Guard
            # A malicious actor could craft a tiny safetensor file that claims its
            # JSON header is 500GB. When Python attempts to read those bytes, it
            # causes a catastrophic memory exhaustion attack. We hard-cap the read
            # buffer at 100MB to mathematically guarantee pipeline survival.
            # ==================================================================
            if header_size > 100 * 1024 * 1024:
                raise ValueError(f"Safetensors header is suspiciously large: {header_size} bytes")

            # 2. Read the JSON header
            header_json_bytes = f.read(header_size)
            header = json.loads(header_json_bytes.decode("utf-8"))

            # 3. Extract Metadata
            metadata = header.get("__metadata__", {})
            architecture = metadata.get("architecture", metadata.get("format", "Unknown Transformer"))

            # 4. Calculate Parameters (Sum of the product of all tensor shapes)
            total_params = 0
            for key, tensor_info in header.items():
                if key != "__metadata__":
                    shape = tensor_info.get("shape", [])
                    total_params += math.prod(shape)

            return {
                "architecture": architecture,
                "parameters": self._format_params(total_params),
                "quantization": "fp16/bf16 (Standard Safetensors)",
                "raw_param_count": total_params,
            }

    def _parse_gguf(self, file_path: str) -> Dict[str, Any]:
        """
        GGUF format:
        [4 bytes Magic 'GGUF'] -> [uint32 Version] -> [uint64 Tensor Count] -> [uint64 KV Count] -> [KV Pairs]
        """
        with open(file_path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                raise ValueError("Invalid GGUF magic number.")

            # ==================================================================
            # DEFENSIVE ARCHITECTURE: Algorithmic Complexity Guard
            # The GGUF format uses a deeply nested binary tree for KV pairs.
            # Writing a pure Python binary tree walker introduces a massive risk of
            # infinite loops (ReDoS equivalents) if the parsed file is malformed.
            # Instead, we read a flat 1MB chunk and extract known ASCII signatures.
            # This guarantees an O(1) time complexity and O(1) space complexity.
            # ==================================================================
            chunk = f.read(1024 * 1024)
            chunk_str = chunk.decode("ascii", errors="ignore")

            # Heuristic extraction from the binary string chunk
            arch = "Unknown GGUF"
            if "llama" in chunk_str.lower():
                arch = "LLaMA Architecture"
            elif "mistral" in chunk_str.lower():
                arch = "Mistral Architecture"
            elif "qwen" in chunk_str.lower():
                arch = "Qwen Architecture"

            quant_match = "Unknown Quantization"
            if "Q4_K" in chunk_str or "q4_k" in file_path.lower():
                quant_match = "4-Bit (Q4_K)"
            elif "Q8_0" in chunk_str or "q8_0" in file_path.lower():
                quant_match = "8-Bit (Q8_0)"
            elif "Q5_K" in chunk_str or "q5_k" in file_path.lower():
                quant_match = "5-Bit (Q5_K)"

            return {
                "architecture": arch,
                "parameters": "Embedded in GGUF Tensors",
                "quantization": quant_match,
                "raw_param_count": 0,
            }

    def _format_params(self, count: int) -> str:
        """Converts raw integer parameters into human-readable B/M format."""
        if count == 0:
            return "Unknown"
        if count >= 1_000_000_000:
            return f"{count / 1_000_000_000:.1f}B"
        elif count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        return str(count)
