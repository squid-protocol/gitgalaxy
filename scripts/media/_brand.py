"""Shared branding for the docs/media explainers: a plain "GitGalaxy" in the bottom-right corner of every frame."""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

_FONT = ImageFont.truetype(str(pathlib.Path("/usr/share/fonts/truetype/dejavu") / "DejaVuSans-Bold.ttf"), 15)


def brand(im: Image.Image) -> Image.Image:
    out = im.convert("RGBA")
    d = ImageDraw.Draw(out)
    w, h = out.size
    d.text((w - 18, h - 8), "GitGalaxy", font=_FONT, fill=(240, 239, 236, 210), anchor="rd")
    return out
