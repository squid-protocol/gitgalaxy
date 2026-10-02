# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at [https://polyformproject.org/licenses/noncommercial/1.0.0/](https://polyformproject.org/licenses/noncommercial/1.0.0/)
# ==============================================================================
# GitGalaxy Core: Model-Weight Header Sniffing (#4138)
#
# The aperture's Model Weight Shunt used to classify by extension alone, so any
# `.pb` / `.bin` / `.onnx` file counted as a local model -- including ordinary
# protobuf test data (kubernetes' `k8s\0`-framed `.pb` fixtures) -- and every
# shunted file became an `llm_local_compute` hit. This module confirms the claim:
# a file is a model only when its header matches a model format its extension can
# carry.
#
# DEFENSIVE DESIGN (zero-trust aperture): a sniff is one bounded binary read of
# the file's head -- HEADER_BYTES, or H5_SCAN_BYTES for HDF5's attribute search --
# never the whole file, whatever its size. No byte is decoded as text, no length
# field read from the file drives a further read, and the protobuf walk is bounded
# by the buffer (each step consumes at least one byte), so a crafted header cannot
# cost more than the read it already got.
# ==============================================================================
import re
import struct
from pathlib import Path
from typing import Callable, Optional, Union

HEADER_BYTES = 4096
H5_SCAN_BYTES = 64 * 1024

# Upper bound on a believable safetensors JSON header (TensorScanner's own cap).
_SAFETENSORS_MAX_HEADER = 100 * 1024 * 1024

# torch.save (>= 1.6) writes a zip whose entries live under one top-level
# directory: `archive/data.pkl`, `archive/data/0`, `archive/version`, ...
# TorchScript (torch.jit.save) archives use the same layout plus `code/` and
# `constants.pkl`. The first local entry's name is enough to tell them apart from
# any other zip.
_TORCH_ZIP_ENTRY = re.compile(
    rb"^[^/]+/(?:data\.pkl|constants\.pkl|version|byteorder|\.format_version|\.storage_alignment|\.data/|data/|code/)"
)

# Legacy (pre-zip) torch.save: a protocol-2 pickle whose first object is torch's
# MAGIC_NUMBER long, 0x1950a86a20f9469cfc6c (`\x8a\x0a` = LONG1, 10 bytes).
_TORCH_LEGACY_MAGIC = b"\x80\x02\x8a\x0a" + (0x1950A86A20F9469CFC6C).to_bytes(10, "little")

# llama.cpp's pre-GGUF containers, as their little-endian uint32 magic lands on
# disk: 'ggml' (unversioned), 'ggmf', 'ggjt'.
_GGML_MAGICS = (b"lmgg", b"fmgg", b"tjgg")

_HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
# HDF5 is a general scientific container; only a Keras model/weights file carries
# these root-group attribute or group names.
_KERAS_H5_TOKENS = (b"keras_version", b"model_config", b"layer_names", b"model_weights")

# onnx.proto ModelProto: field number -> protobuf wire type (0 = varint, 2 = bytes).
_ONNX_MODEL_FIELDS = {1: 0, 2: 2, 3: 2, 4: 2, 5: 0, 6: 2, 7: 2, 8: 2, 14: 2, 20: 2, 25: 2}
_ONNX_STRING_FIELDS = {2, 3, 4}  # producer_name, producer_version, domain
_ONNX_BODY_FIELDS = {7, 8}  # graph, opset_import

_TF_OP_NAME = re.compile(rb"^[A-Z][A-Za-z0-9_]*$")


def _varint(buf: bytes, pos: int) -> Optional[tuple[int, int]]:
    """Decode a protobuf varint at `pos`; None if truncated or longer than 10 bytes."""
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(buf):
            return None
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
    return None


def _printable(raw: bytes) -> bool:
    return all(0x20 <= b < 0x7F for b in raw)


def _is_safetensors(head: bytes, size: int) -> bool:
    if len(head) < 9:
        return False
    header_len = struct.unpack("<Q", head[:8])[0]
    return 2 <= header_len <= min(_SAFETENSORS_MAX_HEADER, size - 8) and head[8:9] == b"{"


def _is_gguf(head: bytes) -> bool:
    if len(head) < 8 or head[:4] != b"GGUF":
        return False
    version = struct.unpack("<I", head[4:8])[0]
    return 1 <= version <= 64


def _is_ggml(head: bytes) -> bool:
    return head[:4] in _GGML_MAGICS


def _is_tflite(head: bytes) -> bool:
    return head[4:8] == b"TFL3"


def _is_torch(head: bytes) -> bool:
    if head.startswith(_TORCH_LEGACY_MAGIC):
        return True
    if len(head) < 30 or head[:4] != b"PK\x03\x04":
        return False
    name_len = struct.unpack("<H", head[26:28])[0]
    name = head[30 : 30 + name_len]
    return len(name) == name_len and bool(_TORCH_ZIP_ENTRY.match(name))


def _is_keras_h5(head: bytes) -> bool:
    # The HDF5 superblock sits at 0, or after a user block at 512, 1024, 2048, ...
    if not (head.startswith(_HDF5_MAGIC) or head[512:520] == _HDF5_MAGIC):
        return False
    return any(token in head for token in _KERAS_H5_TOKENS)


def _is_onnx(head: bytes) -> bool:
    """
    ONNX ModelProto: serializers emit fields in field-number order, so the file
    opens with ir_version (field 1, varint). Every following tag inside the head
    must be a ModelProto field of the right wire type, in non-decreasing order;
    the walk must reach graph/opset_import, or run off the end of the head after
    at least one more valid field (a long doc_string can push the graph past it).
    """
    if not head.startswith(b"\x08"):
        return False
    decoded = _varint(head, 1)
    if decoded is None or not 1 <= decoded[0] <= 64:
        return False
    pos, last_field, fields_after = decoded[1], 1, 0
    while pos < len(head):
        tag = _varint(head, pos)
        if tag is None:
            break
        field, wire = tag[0] >> 3, tag[0] & 7
        pos = tag[1]
        if _ONNX_MODEL_FIELDS.get(field) != wire or field < last_field:
            return False
        if field in _ONNX_BODY_FIELDS:
            return True
        last_field = field
        fields_after += 1
        payload = _varint(head, pos)
        if payload is None:
            break
        if wire == 0:
            pos = payload[1]
            continue
        start, end = payload[1], payload[1] + payload[0]
        if field in _ONNX_STRING_FIELDS and end <= len(head) and not _printable(head[start:end]):
            return False
        pos = end
    return fields_after > 0


def _is_tf_graph(head: bytes) -> bool:
    """
    TensorFlow protobufs. A SavedModel (`saved_model.pb`) opens with
    saved_model_schema_version = 1 then meta_graphs -> MetaGraphDef.meta_info_def:
    `08 01 12 <len> 0a`. A frozen GraphDef opens with its first NodeDef:
    `0a <len> 0a <name> 12 <op>`, where op is a CamelCase TF op name.
    """
    if head.startswith(b"\x08\x01\x12"):
        length = _varint(head, 3)
        return length is not None and head[length[1] : length[1] + 1] == b"\x0a"
    if not head.startswith(b"\x0a"):
        return False
    node = _varint(head, 1)
    if node is None or head[node[1] : node[1] + 1] != b"\x0a":
        return False
    name = _varint(head, node[1] + 1)
    if name is None or name[0] == 0:
        return False
    name_end = name[1] + name[0]
    if name_end > len(head) or not _printable(head[name[1] : name_end]) or head[name_end : name_end + 1] != b"\x12":
        return False
    op = _varint(head, name_end + 1)
    if op is None or op[0] == 0:
        return False
    return bool(_TF_OP_NAME.match(head[op[1] : op[1] + op[0]]))


# Extension -> the (format name, header check) pairs a file with that extension may
# be. Each check takes (head, file size in bytes).
_Check = Callable[[bytes, int], bool]
_SNIFFERS: dict[str, tuple[tuple[str, _Check], ...]] = {
    ".safetensors": (("safetensors", _is_safetensors),),
    ".gguf": (("gguf", lambda h, _s: _is_gguf(h)),),
    ".onnx": (("onnx", lambda h, _s: _is_onnx(h)),),
    ".pt": (("pytorch", lambda h, _s: _is_torch(h)),),
    ".pth": (("pytorch", lambda h, _s: _is_torch(h)),),
    ".bin": (
        ("pytorch", lambda h, _s: _is_torch(h)),
        ("gguf", lambda h, _s: _is_gguf(h)),
        ("ggml", lambda h, _s: _is_ggml(h)),
    ),
    ".tflite": (("tflite", lambda h, _s: _is_tflite(h)),),
    ".pb": (("tensorflow", lambda h, _s: _is_tf_graph(h)), ("onnx", lambda h, _s: _is_onnx(h))),
    ".h5": (("keras_h5", lambda h, _s: _is_keras_h5(h)),),
}

MODEL_EXTENSIONS = frozenset(_SNIFFERS)


def sniff_model_format(file_path: Union[str, Path], size_bytes: Optional[int] = None) -> Optional[str]:
    """
    Return the model format a file's header proves (e.g. "onnx", "safetensors"),
    or None when its extension is not a model extension, the header does not match
    any format that extension carries, or the file cannot be read.
    """
    path = Path(file_path)
    sniffers = _SNIFFERS.get(path.suffix.lower())
    if not sniffers:
        return None
    limit = H5_SCAN_BYTES if path.suffix.lower() == ".h5" else HEADER_BYTES
    try:
        if not path.is_file():
            return None
        if size_bytes is None:
            size_bytes = path.stat().st_size
        with open(path, "rb") as handle:
            head = handle.read(limit)
    except OSError:
        return None
    for fmt, check in sniffers:
        if check(head, size_bytes):
            return fmt
    return None
