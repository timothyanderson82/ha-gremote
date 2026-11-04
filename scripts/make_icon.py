"""Generate the brand images from Centurion's logo.

Centurion only publishes the logo as a 400 px PNG, so this traces it to vector
paths and renders those at the sizes Home Assistant serves from
custom_components/gremote/brand/:

- icon: the helmet emblem alone, since the wordmark is unreadable at icon size
- logo: the full logo with the CENTURION wordmark

    uv run --with potracer --with cairosvg --with pillow python scripts/make_icon.py
"""

from pathlib import Path

import cairosvg
import numpy as np
import potrace
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "centurion-logo.png"
BRAND = ROOT / "custom_components" / "gremote" / "brand"
COLOUR = "#81C341"  # Centurion green, sampled from the logo
SCALE = 4  # trace an upscaled copy for smoother curves
# Rows of the source PNG holding the emblem; the wordmark starts below a gap at 250-261
EMBLEM_ROWS = (0, 256)


def trace(alpha: Image.Image) -> tuple[str, tuple[int, int, int, int]]:
    """Trace an alpha mask; return an SVG path and its bounding box."""
    big = alpha.resize((alpha.width * SCALE, alpha.height * SCALE), Image.BICUBIC)
    mask = np.array(big) > 127
    # potracer traces the False pixels, so hand it the inverse
    path = potrace.Bitmap(~mask).trace(turdsize=8, alphamax=1.0, opticurve=True)
    parts = []
    for curve in path:
        start = curve.start_point
        parts.append(f"M{start.x:.2f},{start.y:.2f}")
        for seg in curve.segments:
            if seg.is_corner:
                parts.append(
                    f"L{seg.c.x:.2f},{seg.c.y:.2f}L{seg.end_point.x:.2f},{seg.end_point.y:.2f}"
                )
            else:
                parts.append(
                    f"C{seg.c1.x:.2f},{seg.c1.y:.2f} {seg.c2.x:.2f},{seg.c2.y:.2f} "
                    f"{seg.end_point.x:.2f},{seg.end_point.y:.2f}"
                )
        parts.append("Z")
    ys, xs = np.nonzero(mask)
    return "".join(parts), (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


def svg(path: str, box: tuple[int, int, int, int], width: int, height: int, margin: float) -> str:
    """Fit the traced path, centred, into width x height with a margin."""
    x0, y0, x1, y1 = box
    scale = min(width * (1 - 2 * margin) / (x1 - x0), height * (1 - 2 * margin) / (y1 - y0))
    dx = (width - (x1 - x0) * scale) / 2 - x0 * scale
    dy = (height - (y1 - y0) * scale) / 2 - y0 * scale
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><path fill="{COLOUR}" fill-rule="evenodd" '
        f'transform="translate({dx:.2f},{dy:.2f}) scale({scale:.5f})" d="{path}"/></svg>'
    )


def render(name: str, markup: str) -> None:
    cairosvg.svg2png(bytestring=markup.encode(), write_to=str(BRAND / name))
    print(name, Image.open(BRAND / name).size)


def main() -> None:
    BRAND.mkdir(exist_ok=True)
    alpha = Image.open(SOURCE).convert("RGBA").split()[3]

    emblem = alpha.copy()
    emblem.paste(0, (0, EMBLEM_ROWS[1], alpha.width, alpha.height))
    path, box = trace(emblem)
    (ROOT / "assets" / "icon.svg").write_text(svg(path, box, 512, 512, 0.04))
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        render(name, svg(path, box, size, size, 0.04))

    path, box = trace(alpha)
    ratio = (box[2] - box[0]) / (box[3] - box[1])
    (ROOT / "assets" / "logo.svg").write_text(svg(path, box, round(256 * ratio), 256, 0))
    for name, height in (("logo.png", 128), ("logo@2x.png", 256)):
        render(name, svg(path, box, round(height * ratio), height, 0))


if __name__ == "__main__":
    main()
