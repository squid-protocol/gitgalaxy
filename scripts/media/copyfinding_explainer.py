#!/usr/bin/env python3
"""Render "Finding a copy without its name" from REAL ranks (layered structural fingerprint, OpenSSL C -> BoringSSL C++).

Every number drawn here was computed by scripts/media/copyfinding_data.py, which runs the temporal-crucible LAY study's
own scoring code (tools/lay_eval.py) over the study's scans: each OpenSSL function is ranked against all 6,802
BoringSSL functions of >= 6 lines with no names used, and the rank of its true BoringSSL copy is recorded per layer:

  coarse  = L1, the sfs profile (size, complexity, ~32 signal densities)
  +calls  = reciprocal-rank fusion of L1 and L2 (the set of functions it calls)
  +shape  = fusion of L1, L2 and L3 (control-flow skeleton) -- LAY's "FUSED" layered fingerprint

A line is drawn only when the true copy ranks first. The closing numbers are the LAY study's published aggregates
(temporal-crucible docs/lay.md, 2026-11-06). Truth follows LAY: same function name and token Jaccard >= 0.5 (the
renamed set also strips OpenSSL 3's `ossl_` prefix before comparing names). No vulnerability or patch data is used.

    python scripts/media/copyfinding_explainer.py --out docs/media/copyfinding

Needs Pillow, numpy and ffmpeg (docs tooling only).
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1280, 720, 12
FD = pathlib.Path("/usr/share/fonts/truetype/dejavu")


def font(name, size):
    return ImageFont.truetype(str(FD / name), size)


f_title = font("DejaVuSans-Bold.ttf", 38)
f_sub = font("DejaVuSans.ttf", 20)
f_bar = font("DejaVuSans-Bold.ttf", 20)
f_leg = font("DejaVuSans.ttf", 18)
f_stat = font("DejaVuSans.ttf", 18)
f_statb = font("DejaVuSans-Bold.ttf", 18)
f_code = font("DejaVuSansMono.ttf", 14)
f_rank = font("DejaVuSansMono.ttf", 13)
f_hdr = font("DejaVuSans-Bold.ttf", 16)
f_small = font("DejaVuSans.ttf", 13)
f_cnt = font("DejaVuSans-Bold.ttf", 34)
f_tiny = font("DejaVuSans.ttf", 11)
INK, INK2, MUTED, DIM = (240, 239, 236), (195, 194, 183), (143, 142, 134), (88, 92, 110)
C_FN, C_FILE, C_MATCH, C_REN = (96, 165, 250), (52, 211, 153), (167, 139, 250), (244, 114, 182)

OPENSSL_SHA, BORINGSSL_SHA, CANDIDATES = "2172e0c098cd", "e375adcf13f8", 6802
# (OpenSSL function, OpenSSL file, BoringSSL function, BoringSSL file, BoringSSL line, rank coarse, +calls, +shape, loc)
FILE_ROWS = [
    (
        "x509v3_add_len_value",
        "crypto/x509/v3_utl.c",
        "x509V3_add_len_value",
        "crypto/x509/v3_utl.cc",
        42,
        177,
        3,
        1,
        39,
    ),
    ("X509V3_conf_free", "crypto/x509/v3_utl.c", "X509V3_conf_free", "crypto/x509/v3_utl.cc", 707, 2, 1, 1, 9),
    (
        "X509V3_add_value_bool",
        "crypto/x509/v3_utl.c",
        "bssl::X509V3_add_value_bool",
        "crypto/x509/v3_utl.cc",
        717,
        1,
        1,
        1,
        7,
    ),
    ("bignum_to_string", "crypto/x509/v3_utl.c", "bignum_to_string", "crypto/x509/v3_utl.cc", 85, 106, 1, 3, 35),
    ("i2s_ASN1_ENUMERATED", "crypto/x509/v3_utl.c", "i2s_ASN1_ENUMERATED", "crypto/x509/v3_utl.cc", 725, 16, 2, 2, 14),
    ("i2s_ASN1_INTEGER", "crypto/x509/v3_utl.c", "i2s_ASN1_INTEGER", "crypto/x509/v3_utl.cc", 739, 11, 1, 1, 14),
    (
        "X509V3_add_value_int",
        "crypto/x509/v3_utl.c",
        "bssl::X509V3_add_value_int",
        "crypto/x509/v3_utl.cc",
        815,
        1,
        1,
        1,
        14,
    ),
    (
        "X509V3_get_value_int",
        "crypto/x509/v3_utl.c",
        "bssl::X509V3_get_value_int",
        "crypto/x509/v3_utl.cc",
        862,
        5,
        1,
        1,
        11,
    ),
    ("strip_spaces", "crypto/x509/v3_utl.c", "strip_spaces", "crypto/x509/v3_utl.cc", 110, 105, 1, 1, 19),
    ("equal_nocase", "crypto/x509/v3_utl.c", "equal_nocase", "crypto/x509/v3_utl.cc", 195, 273, 273, 4, 28),
    ("equal_case", "crypto/x509/v3_utl.c", "equal_case", "crypto/x509/v3_utl.cc", 221, 500, 502, 502, 9),
    ("equal_email", "crypto/x509/v3_utl.c", "equal_email", "crypto/x509/v3_utl.cc", 232, 385, 1, 1, 25),
    ("wildcard_match", "crypto/x509/v3_utl.c", "wildcard_match", "crypto/x509/v3_utl.cc", 258, 108, 1, 1, 46),
    ("valid_star", "crypto/x509/v3_utl.c", "valid_star", "crypto/x509/v3_utl.cc", 310, 1, 1, 1, 62),
    ("equal_wildcard", "crypto/x509/v3_utl.c", "equal_wildcard", "crypto/x509/v3_utl.cc", 366, 383, 1, 1, 19),
    ("do_check_string", "crypto/x509/v3_utl.c", "do_check_string", "crypto/x509/v3_utl.cc", 387, 21, 1, 1, 43),
    ("X509_check_ip", "crypto/x509/v3_utl.c", "X509_check_ip", "crypto/x509/v3_utl.cc", 1153, 688, 1, 1, 7),
    ("X509_check_ip_asc", "crypto/x509/v3_utl.c", "X509_check_ip_asc", "crypto/x509/v3_utl.cc", 1161, 854, 2, 2, 12),
    ("a2i_IPADDRESS", "crypto/x509/v3_utl.c", "a2i_IPADDRESS", "crypto/x509/v3_utl.cc", 1179, 1, 1, 1, 22),
    ("a2i_IPADDRESS_NC", "crypto/x509/v3_utl.c", "a2i_IPADDRESS_NC", "crypto/x509/v3_utl.cc", 1200, 55, 2, 2, 43),
    ("get_ipv4_component", "crypto/x509/v3_utl.c", "get_ipv4_component", "crypto/x509/v3_utl.cc", 510, 66, 66, 1, 27),
    ("get_ipv4_dot", "crypto/x509/v3_utl.c", "get_ipv4_dot", "crypto/x509/v3_utl.cc", 537, 296, 296, 217, 8),
    ("ipv4_from_asc", "crypto/x509/v3_utl.c", "ipv4_from_asc", "crypto/x509/v3_utl.cc", 545, 39, 1, 1, 10),
    ("ipv6_from_asc", "crypto/x509/v3_utl.c", "ipv6_from_asc", "crypto/x509/v3_utl.cc", 628, 5, 1, 1, 63),
    ("ipv6_cb", "crypto/x509/v3_utl.c", "ipv6_cb", "crypto/x509/v3_utl.cc", 584, 467, 1, 1, 35),
    ("ipv6_hex", "crypto/x509/v3_utl.c", "ipv6_hex", "crypto/x509/v3_utl.cc", 567, 567, 567, 49, 20),
    (
        "X509V3_NAME_from_section",
        "crypto/x509/v3_utl.c",
        "bssl::X509V3_NAME_from_section",
        "crypto/x509/v3_utl.cc",
        1264,
        188,
        1,
        1,
        48,
    ),
]
RENAMED_ROWS = [
    (
        "ossl_i2c_ASN1_BIT_STRING",
        "crypto/asn1/a_bitstr.c",
        "i2c_ASN1_BIT_STRING",
        "crypto/asn1/a_bitstr.cc",
        78,
        25,
        55,
        15,
        36,
    ),
    (
        "ossl_asn1_template_free",
        "crypto/asn1/tasn_fre.c",
        "bssl::ASN1_template_free",
        "crypto/asn1/tasn_fre.cc",
        118,
        9,
        1,
        1,
        23,
    ),
    ("ossl_asn1_do_adb", "crypto/asn1/tasn_utl.c", "bssl::asn1_do_adb", "crypto/asn1/tasn_utl.cc", 155, 1121, 3, 3, 65),
    (
        "ossl_asn1_enc_restore",
        "crypto/asn1/tasn_utl.c",
        "bssl::asn1_enc_restore",
        "crypto/asn1/tasn_utl.cc",
        136,
        34,
        69,
        85,
        15,
    ),
    (
        "ossl_asn1_enc_save",
        "crypto/asn1/tasn_utl.c",
        "bssl::asn1_enc_save",
        "crypto/asn1/tasn_utl.cc",
        112,
        1063,
        147,
        161,
        21,
    ),
    ("ossl_asn1_enc_init", "crypto/asn1/tasn_utl.c", "bssl::asn1_enc_init", "crypto/asn1/tasn_utl.cc", 97, 5, 1, 1, 10),
    (
        "ossl_asn1_enc_free",
        "crypto/asn1/tasn_utl.c",
        "bssl::asn1_enc_free",
        "crypto/asn1/tasn_utl.cc",
        105,
        337,
        12,
        3,
        11,
    ),
    (
        "ossl_asn1_set_choice_selector",
        "crypto/asn1/tasn_utl.c",
        "bssl::asn1_set_choice_selector",
        "crypto/asn1/tasn_utl.cc",
        45,
        1436,
        1,
        1,
        10,
    ),
    (
        "ossl_x25519_public_from_private",
        "crypto/ec/curve25519.c",
        "X25519_public_from_private",
        "crypto/curve25519/curve25519.cc",
        2265,
        185,
        4,
        5,
        27,
    ),
    ("ossl_x25519", "crypto/ec/curve25519.c", "X25519", "crypto/curve25519/curve25519.cc", 2256, 107, 1, 1, 8),
    (
        "ossl_ec_GFp_nistp_recode_scalar_bits",
        "crypto/ec/ecp_nistputil.c",
        "bssl::ec_GFp_nistp_recode_scalar_bits",
        "crypto/fipsmodule/ec/util.cc.inc",
        245,
        2,
        2,
        2,
        14,
    ),
    (
        "ossl_ec_GFp_simple_group_get_curve",
        "crypto/ec/ecp_smpl.c",
        "bssl::ec_GFp_simple_group_get_curve",
        "crypto/fipsmodule/ec/simple.cc.inc",
        76,
        1746,
        7,
        22,
        44,
    ),
    (
        "ossl_rsa_padding_add_PKCS1_PSS_mgf1",
        "crypto/rsa/rsa_pss.c",
        "RSA_padding_add_PKCS1_PSS_mgf1",
        "crypto/fipsmodule/rsa/padding.cc.inc",
        267,
        1,
        2,
        1,
        118,
    ),
    ("ossl_sha1", "crypto/sha/sha1_one.c", "SHA1", "include/openssl/sha.h", 81, 1670, 3, 3, 14),
]
# LAY study aggregates (temporal-crucible docs/lay.md): recall@1, coarse L1 vs layered FUSED.
STUDY = {"all": (90, 46, 80), "boringssl": (17, 29, 94)}
# Every current OpenSSL -> BoringSSL copy pair (name-keyed answer key, as in LAY), scored with the same three layers by
# copyfinding_data.py: true copy ranked first 11% (coarse) -> 44% (layered), 253 of 572. The study's 94% / 80% are
# CVE-touched functions in pre-fix code, so the general rate is shown first.
GENERAL = (572, 11, 44)
STAGES = ["profile", "+ calls", "+ skeleton"]

XL, XR = 470, 800  # left / right dot columns
X_RANK = 116  # right edge of the rank column
X_PANEL = 1150


def make_sky():
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.7)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2).clip(0, 1)
    sky = np.stack([14 - 10 * rr, 20 - 14 * rr, 48 - 32 * rr, np.full_like(rr, 255)], -1).astype(np.uint8)
    im = Image.fromarray(sky, "RGBA")
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(11)
    for _ in range(260):
        x, y, b = rng.uniform(0, W), rng.uniform(0, H), int(rng.uniform(50, 140))
        d.point((x, y), fill=(b, b, min(255, b + 30), 255))
    return im


SKY = make_sky()


def name_differs(a, b):
    return a != b


class Scene:
    """One two-column board: OpenSSL functions (left) and their BoringSSL copies (right)."""

    def __init__(self, rows, left_hdr, right_hdr, y0, step, right_order):
        self.rows = rows
        self.left_hdr, self.right_hdr = left_hdr, right_hdr
        self.ly = {i: y0 + i * step for i in range(len(rows))}
        order = sorted(range(len(rows)), key=right_order)
        self.ry = {i: y0 + k * step for k, i in enumerate(order)}

    def ranks(self, stage):
        return [r[5 + stage] for r in self.rows]


def curve(p, q, frac=1.0):
    pts = []
    for k in range(25):
        t = k / 24 * frac
        x = p[0] + (q[0] - p[0]) * t
        s = t * t * (3 - 2 * t)
        y = p[1] + (q[1] - p[1]) * s
        pts.append((x, y))
    return pts


def draw_frame(sc, title, stats, stage, lines, rank_alpha=255, panel=None, footer="", reveal=255):
    """lines: {row index: (alpha 0..255, growth 0..1)}"""
    im = SKY.copy()
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for i, (al, g) in lines.items():
        if al <= 0:
            continue
        ld.line(curve((XL + 8, sc.ly[i] + 9), (XR - 8, sc.ry[i] + 9), g), fill=C_MATCH + (int(al),), width=3)
    glow = lay.filter(ImageFilter.GaussianBlur(4))
    im = Image.alpha_composite(im, glow)
    im = Image.alpha_composite(im, lay)
    d = ImageDraw.Draw(im)
    # column headers: file chips
    for x, hdr, anchor in ((XL + 10, sc.left_hdr, "rs"), (XR - 10, sc.right_hdr, "ls")):
        wtxt = f_hdr.getlength(hdr)
        x0 = x - wtxt - 16 if anchor == "rs" else x
        d.rounded_rectangle((x0, 80, x0 + wtxt + 16, 106), 7, fill=(8, 40, 34, 230), outline=C_FILE, width=2)
        d.text((x0 + 8, 84), hdr, font=f_hdr, fill=(167, 243, 208))
    if stage is not None:
        d.text((X_RANK, 112), "true-copy rank", font=f_small, fill=MUTED + (rank_alpha,), anchor="ra")
    ranks = sc.ranks(stage) if stage is not None else None
    for i, r in enumerate(sc.rows):
        a, b = r[0], r[2]
        ren = name_differs(a, b)
        yl, yr = sc.ly[i], sc.ry[i]
        hit = ranks is not None and ranks[i] == 1
        ink = (INK if hit or ranks is None else INK2) + (reveal,)
        d.text((XL - 10, yl + 1), a + "()", font=f_code, fill=(C_REN + (reveal,)) if ren else ink, anchor="ra")
        d.text((XR + 10, yr + 1), b + "()", font=f_code, fill=(C_REN + (reveal,)) if ren else ink, anchor="la")
        for x, y in ((XL, yl), (XR, yr)):
            rr = 5
            d.ellipse((x - rr, y + 9 - rr, x + rr, y + 9 + rr), fill=C_FN + (reveal,))
        if ranks is not None:
            txt = "1st" if hit else f"#{ranks[i]:,}"
            col = (C_MATCH if hit else DIM) + (rank_alpha,)
            d.text((X_RANK, yl + 2), txt, font=f_rank, fill=col, anchor="ra")
    # right-hand counter panel
    if panel is not None:
        found, n, done = panel
        d.rounded_rectangle((X_PANEL, 118, W - 16, 330), 10, fill=(10, 14, 32, 215), outline=(60, 61, 90))
        d.text(((X_PANEL + W - 16) / 2, 128), "found first", font=f_small, fill=INK2, anchor="ma")
        d.text(((X_PANEL + W - 16) / 2, 148), f"{found}", font=f_cnt, fill=C_MATCH, anchor="ma")
        d.text(((X_PANEL + W - 16) / 2, 190), f"of {n}", font=f_small, fill=INK2, anchor="ma")
        for k, (lab, cnt) in enumerate(done):
            y = 218 + k * 36
            on = k == len(done) - 1
            d.text((X_PANEL + 10, y), lab, font=f_small, fill=INK if on else MUTED)
            d.text((W - 26, y + 16), f"{cnt} / {n}", font=f_small, fill=C_MATCH if on else MUTED, anchor="ra")
    # title bar + legend
    bar = (10, 14, 32, 215)
    d.rounded_rectangle((16, 12, W - 16, 66), 12, fill=bar)
    d.text((34, 26), title, font=f_bar, fill=INK)
    lg = [
        ("function", C_FN, "dot"),
        ("file", C_FILE, "box"),
        ("true copy ranked 1st", C_MATCH, "line"),
        ("names differ", C_REN, "box"),
    ]
    x0 = W - 16 - sum(int(f_leg.getlength(t)) + 46 for t, _, _ in lg) - 4
    for t, cl, kind in lg:
        if kind == "dot":
            d.ellipse((x0, 29, x0 + 20, 49), fill=cl)
        elif kind == "line":
            d.rounded_rectangle((x0, 36, x0 + 20, 42), 3, fill=cl)
        else:
            d.rounded_rectangle((x0, 29, x0 + 20, 49), 5, fill=cl)
        d.text((x0 + 27, 27), t, font=f_leg, fill=INK)
        x0 += int(f_leg.getlength(t)) + 46
    # status bar (one or two lines)
    d.rounded_rectangle((16, H - 88, W - 16, H - 24), 12, fill=bar)
    s1, s2 = (stats + ["", ""])[:2]
    d.text((34, H - 80), s1, font=f_statb, fill=INK)
    d.text((34, H - 54), s2, font=f_stat, fill=INK2)
    d.text((18, H - 18), footer or ATTRIB, font=f_tiny, fill=MUTED)
    return im


ATTRIB = (
    f"Function names from OpenSSL {OPENSSL_SHA} (2026-03-31) and BoringSSL {BORINGSSL_SHA} (2026-11-06), both "
    "Apache-2.0. Ranks recomputed with the temporal-crucible LAY scorer; names are never used to match."
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    file_sc = Scene(
        FILE_ROWS,
        "OpenSSL · crypto/x509/v3_utl.c · C",
        "BoringSSL · crypto/x509/v3_utl.cc · C++",
        132,
        18,
        lambda i: FILE_ROWS[i][4],
    )
    ren_sc = Scene(
        RENAMED_ROWS,
        "OpenSSL 3 · ossl_-prefixed · C",
        "BoringSSL · C++",
        136,
        34,
        lambda i: (RENAMED_ROWS[i][3], RENAMED_ROWS[i][4]),
    )
    nF, nR = len(FILE_ROWS), len(RENAMED_ROWS)
    cnt = lambda sc, s: sum(x == 1 for x in sc.ranks(s))  # noqa: E731
    fc = [cnt(file_sc, s) for s in range(3)]
    rc = [cnt(ren_sc, s) for s in range(3)]
    assert fc == [4, 18, 19] and rc == [1, 4, 5], (fc, rc)
    frames = []

    # 1. title card
    for i in range(30):
        im = SKY.copy()
        d = ImageDraw.Draw(im)
        al = int(255 * min(1, i / 8))
        d.text((W // 2, 300), "Finding a copy without its name", font=f_title, fill=INK + (al,), anchor="mm")
        d.text(
            (W // 2, 352),
            "OpenSSL (C) → BoringSSL (C++) · layered structural fingerprint · real ranks",
            font=f_sub,
            fill=INK2 + (al,),
            anchor="mm",
        )
        frames.append(im)

    # 2. the two files, no matching yet
    intro = [
        "The matcher never sees a name: every OpenSSL function is ranked against all "
        f"{CANDIDATES:,} BoringSSL functions.",
        f"{nF} functions in this file have a known BoringSSL copy (same name, ≥ 50% shared tokens): the answer key.",
    ]
    for i in range(14):
        frames.append(
            draw_frame(
                file_sc, "Two codebases, one shared ancestor", intro, None, {}, reveal=int(255 * min(1, (i + 1) / 10))
            )
        )
    frames += [frames[-1]] * 30

    def play_layers(sc, n, counts, titles, texts, hold_end):
        state = {}  # row -> (alpha, growth)
        done = []
        for s in range(3):
            ranks = sc.ranks(s)
            done = done + [(STAGES[s], counts[s])]
            prev = {i for i, (al, _g) in state.items() if al > 0}
            now = {i for i, r in enumerate(ranks) if r == 1}
            gone, new = sorted(prev - now), [i for i in sorted(now - prev, key=lambda i: sc.ly[i])]
            # rank column fades in
            shown = len(prev)
            for t in range(6):
                frames.append(
                    draw_frame(
                        sc,
                        titles[s],
                        texts[s](shown),
                        s,
                        dict(state),
                        rank_alpha=int(255 * (t + 1) / 6),
                        panel=(shown, n, done[:-1] + [(STAGES[s], shown)]),
                    )
                )
            for i in gone:
                for t in range(8):
                    state[i] = (int(255 * (1 - (t + 1) / 8)), 1.0)
                    frames.append(
                        draw_frame(
                            sc,
                            titles[s],
                            texts[s](shown - (t == 7)),
                            s,
                            dict(state),
                            panel=(shown - (t == 7), n, done[:-1] + [(STAGES[s], shown - (t == 7))]),
                        )
                    )
                state.pop(i)
                shown -= 1
            per = 3 if len(new) <= 6 else 2
            for i in new:
                for t in range(per):
                    state[i] = (255, (t + 1) / per)
                    c = shown + (t == per - 1)
                    frames.append(
                        draw_frame(
                            sc, titles[s], texts[s](c), s, dict(state), panel=(c, n, done[:-1] + [(STAGES[s], c)])
                        )
                    )
                shown += 1
            assert shown == counts[s]
            frames.extend([frames[-1]] * (hold_end if s == 2 else 26))
        return state, done

    ftitles = [
        "Layer 1: the coarse profile alone",
        "Layer 2: add the call set",
        "Layer 3: add the control-flow skeleton",
    ]
    ftexts = [
        lambda c: [
            f"Coarse profile (size, complexity, ~32 signal densities): true copy ranked 1st for {c} of {nF}",
            "Small helpers look alike by size and density, so most true copies rank far down the list.",
        ],
        lambda c: [
            f"+ call set (which functions each one calls): {c} of {nF} ranked 1st",
            "What a function calls survives the C → C++ rewrite: here it lifts 4 to 18.",
        ],
        lambda c: [
            f"+ control-flow skeleton (nesting of if / for / switch / return): {c} of {nF} ranked 1st",
            "Weak alone, it still lifts x509v3_add_len_value and get_ipv4_component; bignum_to_string slips to #3.",
        ],
    ]
    fstate, fdone = play_layers(file_sc, nF, fc, ftitles, ftexts, 30)

    # 3. renamed copies elsewhere in OpenSSL
    rtitles = ["Names differ, structure matches", "Names differ, structure matches", "Names differ, structure matches"]
    rtexts = [
        lambda c: [
            f"OpenSSL 3 renamed internals with an ossl_ prefix. Coarse profile alone: {c} of {nR} ranked 1st",
            "Names do not enter the score, so a rename costs nothing; only structure is compared.",
        ],
        lambda c: [
            f"+ call set: {c} of {nR} renamed copies ranked 1st (ossl_x25519 → X25519: #107 → 1st)",
            "Same 6,802 BoringSSL candidates; these come from 8 OpenSSL files.",
        ],
        lambda c: [
            f"+ control-flow skeleton: {c} of {nR} renamed copies ranked 1st",
            "5 of the other 9 rank in the top 5; enc_save (#161) and enc_restore (#85) stay far down.",
        ],
    ]
    for t in range(8):
        frames.append(
            draw_frame(
                ren_sc,
                rtitles[0],
                ["Renamed copies: OpenSSL 3 added an ossl_ prefix", ""],
                None,
                {},
                reveal=int(255 * (t + 1) / 8),
            )
        )
    frames += [frames[-1]] * 14
    play_layers(ren_sc, nR, rc, rtitles, rtexts, 30)

    # 4. close on the file with every layer, plus the study's own numbers
    (na, ca, la), (nb, cb, lb) = STUDY["all"], STUDY["boringssl"]
    ng, cg, lg_ = GENERAL
    final_stats = [
        f"All {ng} current OpenSSL → BoringSSL copies: found first {cg}% (profile) → {lg_}% (three layers). This file: {fc[0]} → {fc[2]} of {nF}.",
        f"LAY study, CVE-touched functions: BoringSSL C → C++ {cb}% → {lb}% (n = {nb}); all {na} copies {ca}% → {la}%.",
    ]
    final = draw_frame(
        file_sc, "All three layers: copies found by structure", final_stats, 2, fstate, panel=(fc[2], nF, fdone)
    )
    for t in range(6):
        frames.append(Image.blend(frames[-1].convert("RGBA"), final, (t + 1) / 6))
    frames += [final] * 60

    fdir = pathlib.Path(tempfile.mkdtemp(prefix="gg-copyfind-"))
    for i, im in enumerate(frames):
        im.convert("RGB").save(fdir / f"f{i:04d}.png")
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fdir / "f%04d.png")]
    subprocess.run(ff + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out) + ".mp4"], check=True)
    subprocess.run(
        ff
        + [
            "-vf",
            "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer",
            str(out) + ".gif",
        ],
        check=True,
    )
    shutil.copy(fdir / f"f{len(frames) - 1:04d}.png", str(out) + ".png")
    shutil.rmtree(fdir, ignore_errors=True)
    print(f"{out}: {len(frames)} frames; file {fc} of {nF}; renamed {rc} of {nR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
