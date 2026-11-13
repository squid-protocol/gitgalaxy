"""Shared branding for the docs/media explainers: a plain "GitGalaxy" in the bottom-right corner of every frame."""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

_FONT = ImageFont.truetype(str(pathlib.Path("/usr/share/fonts/truetype/dejavu") / "DejaVuSans-Bold.ttf"), 15)


def brand(im: Image.Image, fill: tuple[int, int, int, int] | None = None) -> Image.Image:
    """`fill` defaults to the light mark for dark films; light films pass a dark one."""
    out = im.convert("RGBA")
    d = ImageDraw.Draw(out)
    w, h = out.size
    d.text((w - 18, h - 8), "GitGalaxy", font=_FONT, fill=fill or (240, 239, 236, 210), anchor="rd")
    return out
