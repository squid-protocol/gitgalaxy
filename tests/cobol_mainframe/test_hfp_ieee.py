"""#4271: the IEEE <-> HFP conversion model in det/hfp.py (register C6): what GnuCOBOL stores against what z/OS holds."""

from __future__ import annotations

import random
import struct
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gitgalaxy.tools.cobol_to_java.det import hfp as H


def f32(x: float) -> int:
    return struct.unpack(">I", struct.pack(">f", x))[0]


def f64(x: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", x))[0]


# IBM's own examples (Principles of Operation): 1.0, -118.625, 0.1 (short 4019999A is truncated, so not an IEEE image)
@pytest.mark.parametrize(
    ("x", "short_hex", "long_hex"),
    [
        (1.0, "41100000", "4110000000000000"),
        (-118.625, "C276A000", "C276A00000000000"),
        (1.5, "41180000", "4118000000000000"),
        (100.5, "42648000", "4264800000000000"),
        (0.0, "00000000", "0000000000000000"),
    ],
)
def test_values_exact_in_both_formats_convert_both_ways(x, short_hex, long_hex):
    assert H.from_ieee(f32(x), 4).hex().upper() == short_hex
    assert H.from_ieee(f64(x), 8).hex().upper() == long_hex
    assert H.to_ieee(bytes.fromhex(short_hex)) == f32(x)
    assert H.to_ieee(bytes.fromhex(long_hex)) == f64(x)
    assert H.exact_in_both(F(x), True) and H.exact_in_both(F(x), False)


def test_a_binary64_always_fits_long_hfp_exactly():
    rng = random.Random(4271)
    for _ in range(3000):
        bits = (rng.getrandbits(1) << 63) | (rng.randrange(1, 2047) << 52) | rng.getrandbits(52)
        v = H.ieee_value(bits, 8)
        try:
            b = H.from_ieee(bits, 8)
        except H.HfpRange:
            assert abs(v) >= F(16) ** 63 or abs(v) < F(16) ** -65  # outside the HFP range, refused by name
            continue
        assert H.decode(b) == v
        assert H.to_ieee(b) == bits


def test_hfp_to_ieee_is_the_nearest_float_ties_to_even():
    rng = random.Random(7)
    for _ in range(3000):
        b = bytes([rng.getrandbits(1) << 7 | rng.randrange(40, 90)]) + rng.getrandbits(56).to_bytes(7, "big")
        if b[1] < 0x10:
            continue  # not normalized
        v = H.decode(b)
        assert H.ieee_value(H.to_ieee(b), 8) == F(float(v))  # Python rounds a Fraction to float half-even


def test_a_short_hfp_is_exact_in_binary32_inside_its_range():
    rng = random.Random(11)
    for _ in range(3000):
        b = bytes([rng.getrandbits(1) << 7 | rng.randrange(64 - 30, 64 + 30)]) + rng.getrandbits(24).to_bytes(3, "big")
        if b[1] < 0x10:
            continue
        assert H.ieee_value(H.to_ieee(b), 4) == H.decode(b)
        assert H.from_ieee(H.to_ieee(b), 4) == b


def test_the_two_formats_disagree_on_a_tenth():
    """0.1 is the C6 DIFFERS case: z/OS holds 4019999A / 3FFFFFFF-style truncation, the oracle the nearest binary."""
    z = H.for_item(F(1, 10), False)
    assert H.encode(z, False).hex().upper() == "4019999999999999"  # truncated: IBM's own 0.1
    assert (
        H.from_ieee(f64(0.1), 8).hex().upper() == "401999999999999A"
    )  # the oracle's nearest binary, a different image
    assert H.from_ieee(f32(0.1), 4).hex().upper() == "4019999A"
    ieee = H.ieee_value(f64(0.1), 8)
    assert ieee != F(1, 10) and z != F(1, 10) and z != ieee
    assert not H.exact_in_both(F(1, 10), False) and not H.exact_in_both(F(1, 10), True)
    assert H.exact_in_both(F(25, 100), True)


def test_out_of_range_and_special_patterns_are_refused_by_name():
    big = bytes.fromhex("7F100000")  # 16 ** 62: far beyond binary32
    with pytest.raises(H.HfpRange):
        H.to_ieee(big)
    with pytest.raises(H.HfpRange):
        H.to_ieee(bytes.fromhex("00100000"))  # 16 ** -65: below binary32's normal range
    assert H.to_ieee(bytes.fromhex("7F10000000000000")) == f64(float(F(16) ** 62))
    for bits, size in ((0x7FC00000, 4), (0x7F800000, 4), (0x00000001, 4), (0x7FF0000000000000, 8), (1, 8)):
        with pytest.raises(H.HfpRange):
            H.from_ieee(bits, size)
    with pytest.raises(H.HfpRange):
        H.from_ieee(f64(1e300), 8)  # beyond HFP's 7.2e75
