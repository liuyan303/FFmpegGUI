"""Generate ``assets/icon.ico`` and ``assets/icon.png`` with Pillow.

The generated files are committed to the repository, so running this is
only necessary when the icon design changes:

    python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

# Brand gradient (indigo -> blue), matching the app's accent color.
_TOP = (56, 108, 232)
_BOTTOM = (37, 99, 235)
_ACCENT = (124, 58, 237)

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _gradient(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / max(1, size - 1)
        # Blend top -> bottom, passing through the violet accent.
        if ratio < 0.5:
            local = ratio * 2
            color = tuple(
                int(_TOP[i] + (_ACCENT[i] - _TOP[i]) * local) for i in range(3)
            )
        else:
            local = (ratio - 0.5) * 2
            color = tuple(
                int(_ACCENT[i] + (_BOTTOM[i] - _ACCENT[i]) * local) for i in range(3)
            )
        draw.line([(0, y), (size, y)], fill=color)
    return image


def draw_icon(size: int = 1024) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Rounded-square background
    radius = int(size * 0.22)
    background = _gradient(size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    image.paste(background, (0, 0), mask)

    draw = ImageDraw.Draw(image)

    # Film-strip sprocket holes on the left edge
    hole_w = size * 0.055
    hole_h = size * 0.075
    hole_x = size * 0.115
    for index in range(3):
        hole_y = size * (0.30 + index * 0.20)
        draw.rounded_rectangle(
            [hole_x, hole_y, hole_x + hole_w, hole_y + hole_h],
            radius=hole_w * 0.35,
            fill=(255, 255, 255, 190),
        )

    # Play triangle
    left = size * 0.42
    top = size * 0.30
    bottom = size * 0.70
    right = size * 0.78
    draw.polygon(
        [(left, top), (left, bottom), (right, size * 0.5)],
        fill=(255, 255, 255, 255),
    )

    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = draw_icon(1024)
    icon.save(ASSETS / "icon.png")
    icon.save(ASSETS / "icon.ico", sizes=ICO_SIZES)
    print(f"wrote {ASSETS / 'icon.png'}")
    print(f"wrote {ASSETS / 'icon.ico'}")


if __name__ == "__main__":
    main()
