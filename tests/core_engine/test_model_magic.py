"""
#4138: the aperture's Model Weight Shunt (and so `llm_local_compute`) used to
fire on a file extension alone. `gitgalaxy/core/model_magic.py` now requires the
header to prove the claimed model format. Every fixture here is a tiny, real
header built in-test -- one positive per format, and look-alike non-models that
must not count.
"""

import io
import random
import struct
import zipfile

import pytest

from gitgalaxy.core import model_magic
from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.core.model_magic import HEADER_BYTES, sniff_model_format

# ==============================================================================
# Tiny protobuf encoder (enough for ONNX / TensorFlow headers)
# ==============================================================================


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field_varint(field: int, value: int) -> bytes:
    return _varint(field << 3) + _varint(value)


def _field_bytes(field: int, payload: bytes) -> bytes:
    return _varint((field << 3) | 2) + _varint(len(payload)) + payload


# ==============================================================================
# Real-format headers
# ==============================================================================


def _safetensors() -> bytes:
    header = b'{"weight":{"dtype":"F32","shape":[2,2],"data_offsets":[0,16]}}'
    return struct.pack("<Q", len(header)) + header + b"\x00" * 16


def _gguf() -> bytes:
    return b"GGUF" + struct.pack("<IQQ", 3, 0, 0)


def _ggml_bin() -> bytes:
    return b"tjgg" + struct.pack("<I", 3) + b"\x00" * 32


def _tflite() -> bytes:
    # FlatBuffer root offset (uint32), then the file identifier at offset 4.
    return struct.pack("<I", 0x1C) + b"TFL3" + b"\x00" * 40


def _onnx_model() -> bytes:
    node = _field_bytes(1, b"x") + _field_bytes(2, b"y") + _field_bytes(4, b"Relu")
    graph = _field_bytes(1, node) + _field_bytes(2, b"main_graph")
    opset = _field_bytes(1, b"") + _field_varint(2, 17)
    return (
        _field_varint(1, 8)  # ir_version
        + _field_bytes(2, b"pytorch")  # producer_name
        + _field_bytes(3, b"2.1.0")  # producer_version
        + _field_bytes(7, graph)  # graph
        + _field_bytes(8, opset)  # opset_import
    )


def _onnx_long_docstring() -> bytes:
    # The graph sits past the sniffed head; the walk runs off the end validly.
    return _field_varint(1, 9) + _field_bytes(6, b"d" * (HEADER_BYTES * 2)) + _field_bytes(7, b"")


def _tf_saved_model() -> bytes:
    meta_info = _field_bytes(4, b"serve") + _field_bytes(5, b"2.15.0")
    meta_graph = _field_bytes(1, meta_info)
    return _field_varint(1, 1) + _field_bytes(2, meta_graph)


def _tf_graph_def() -> bytes:
    node = _field_bytes(1, b"input") + _field_bytes(2, b"Placeholder")
    return _field_bytes(1, node) + _field_bytes(4, _field_varint(1, 1087))


def _torch_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("archive/data.pkl", b"\x80\x02}q\x00.")
        zf.writestr("archive/data/0", b"\x00" * 16)
        zf.writestr("archive/version", b"3\n")
    return buf.getvalue()


def _torch_legacy() -> bytes:
    return model_magic._TORCH_LEGACY_MAGIC + b".\x80\x02M\xe9\x03."


def _keras_h5() -> bytes:
    superblock = b"\x89HDF\r\n\x1a\n" + b"\x00" * 200
    return superblock + b"keras_version\x00\x00\x002.13.1\x00" + b"\x00" * 64


POSITIVES = [
    ("model.safetensors", _safetensors, "safetensors"),
    ("model.gguf", _gguf, "gguf"),
    ("llama-7b.Q4_K.bin", _gguf, "gguf"),
    ("ggml-model.bin", _ggml_bin, "ggml"),
    ("model.tflite", _tflite, "tflite"),
    ("model.onnx", _onnx_model, "onnx"),
    ("documented.onnx", _onnx_long_docstring, "onnx"),
    ("saved_model.pb", _tf_saved_model, "tensorflow"),
    ("frozen_graph.pb", _tf_graph_def, "tensorflow"),
    ("model.pt", _torch_zip, "pytorch"),
    ("model.pth", _torch_legacy, "pytorch"),
    ("pytorch_model.bin", _torch_zip, "pytorch"),
    ("model.h5", _keras_h5, "keras_h5"),
]


@pytest.mark.parametrize("name,build,expected", POSITIVES, ids=[p[0] for p in POSITIVES])
def test_real_model_headers_are_recognised(tmp_path, name, build, expected):
    path = tmp_path / name
    path.write_bytes(build())
    assert sniff_model_format(path) == expected


# ==============================================================================
# Look-alikes that must NOT count as models
# ==============================================================================


def _random(n: int = 2048) -> bytes:
    return random.Random(4138).randbytes(n)


def _k8s_protobuf() -> bytes:
    # Kubernetes' protobuf envelope: the 'k8s\0' magic, then runtime.Unknown.
    type_meta = _field_bytes(1, b"v1") + _field_bytes(2, b"Pod")
    return b"k8s\x00" + _field_bytes(1, type_meta) + _field_bytes(2, b"\x0a\x03pod")


def _onnx_tensor_proto() -> bytes:
    # onnx's backend test data `input_0.pb`: a TensorProto (dims, data_type, raw_data).
    return _field_varint(1, 1) + _field_varint(1, 3) + _field_varint(2, 1) + _field_bytes(9, b"\x00" * 12)


def _generic_protobuf() -> bytes:
    # An ordinary message: a string, then a nested message whose op is not a TF op.
    return _field_bytes(1, _field_bytes(1, b"user") + _field_bytes(2, b"lower_case")) + _field_varint(3, 7)


def _plain_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"hello")
    return buf.getvalue()


def _plain_hdf5() -> bytes:
    return b"\x89HDF\r\n\x1a\n" + b"\x00" * 200 + b"temperature\x00samples" + b"\x00" * 64


def _oversized_safetensors_claim() -> bytes:
    return struct.pack("<Q", 10_000) + b'{"a":1}'


NEGATIVES = [
    ("random.pb", _random),
    ("random.bin", _random),
    ("random.onnx", _random),
    ("random.pt", _random),
    ("random.tflite", _random),
    ("random.gguf", _random),
    ("random.h5", _random),
    ("random.safetensors", _random),
    ("pod.pb", _k8s_protobuf),
    ("input_0.pb", _onnx_tensor_proto),
    ("message.pb", _generic_protobuf),
    ("message.onnx", _generic_protobuf),
    ("archive.pt", _plain_zip),
    ("dataset.h5", _plain_hdf5),
    ("lying.safetensors", _oversized_safetensors_claim),
    ("tensor.onnx", _onnx_tensor_proto),
    ("empty.bin", lambda: b""),
    ("text.bin", lambda: b"not a model at all\n" * 20),
]


@pytest.mark.parametrize("name,build", NEGATIVES, ids=[n[0] for n in NEGATIVES])
def test_non_model_payloads_are_rejected(tmp_path, name, build):
    path = tmp_path / name
    path.write_bytes(build())
    assert sniff_model_format(path) is None


def test_format_must_match_the_claimed_extension(tmp_path):
    """A real TFLite header named `.onnx` is not an ONNX model."""
    path = tmp_path / "mislabelled.onnx"
    path.write_bytes(_tflite())
    assert sniff_model_format(path) is None


def test_non_model_extension_and_directories_are_not_sniffed(tmp_path):
    source = tmp_path / "weights.py"
    source.write_bytes(_gguf())
    assert sniff_model_format(source) is None

    directory = tmp_path / "shards.bin"
    directory.mkdir()
    assert sniff_model_format(directory) is None
    assert sniff_model_format(tmp_path / "missing.onnx") is None


def test_sniff_reads_only_a_bounded_head(tmp_path, monkeypatch):
    """Zero-trust aperture: one bounded read, whatever the file size."""
    path = tmp_path / "huge.bin"
    path.write_bytes(_gguf() + b"\x00" * (HEADER_BYTES * 64))
    reads = []
    real_open = open

    class _Spy:
        def __init__(self, handle):
            self._handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._handle.close()

        def read(self, size=-1):
            reads.append(size)
            return self._handle.read(size)

    monkeypatch.setattr(model_magic, "open", lambda *a, **k: _Spy(real_open(*a, **k)), raising=False)
    assert sniff_model_format(path) == "gguf"
    assert reads == [HEADER_BYTES]


# ==============================================================================
# Aperture integration: only a proven header takes the Model Weight Shunt
# ==============================================================================


@pytest.fixture
def aperture(tmp_path):
    return ApertureFilter(
        root_dir=tmp_path,
        language_definitions={"python": {"extensions": [".py"], "exact_matches": []}},
        aperture_config={"MAX_FILE_SIZE_MB": 10, "MAX_FILE_SIZE_HARD_MB": 100},
    )


def test_aperture_shunts_a_real_onnx_model(aperture, tmp_path):
    path = tmp_path / "model.onnx"
    path.write_bytes(_onnx_model())
    is_valid, _, reason = aperture.evaluate_path_integrity(path)
    assert is_valid is False
    assert "AI MODEL WEIGHTS" in reason
    assert "onnx header" in reason


@pytest.mark.parametrize("name,build", [("pod.pb", _k8s_protobuf), ("blob.bin", _random), ("x.onnx", _random)])
def test_aperture_does_not_shunt_protobuf_or_binary_test_data(aperture, tmp_path, name, build):
    path = tmp_path / "testdata" / name
    path.parent.mkdir()
    path.write_bytes(build())
    _, _, reason = aperture.evaluate_path_integrity(path)
    assert "AI MODEL WEIGHTS" not in reason
