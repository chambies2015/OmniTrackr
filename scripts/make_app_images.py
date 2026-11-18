"""Draw the installed app's launch screens (iPhone) and shortcut icons from the app icon.

Run from the repository root after changing the icon:  python scripts/make_app_images.py
It writes app/static/splash/*.png and app/static/icons/shortcut-*.png, and prints the
<link rel="apple-touch-startup-image"> tags for app/templates/index.html and public_landing.html.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "app/static/icons/icon-512.png"
SPLASH = ROOT / "app/static/splash"
ICONS = ROOT / "app/static/icons"
BACKGROUND = (11, 10, 24)  # manifest background_color #0b0a18
VERSION = "20261118-app-1"

# Portrait iPhones: CSS width, CSS height, device pixel ratio.
IPHONES = (
    (320, 568, 2), (375, 667, 2), (414, 736, 3), (375, 812, 3), (414, 896, 2), (414, 896, 3),
    (390, 844, 3), (428, 926, 3), (393, 852, 3), (430, 932, 3), (402, 874, 3), (440, 956, 3), (420, 912, 3),
)


def splash_images() -> list[str]:
    icon = Image.open(ICON).convert("RGB")
    tags = []
    for width, height, ratio in IPHONES:
        size = (width * ratio, height * ratio)
        image = Image.new("RGB", size, BACKGROUND)
        side = round(size[0] * 0.42)
        image.paste(icon.resize((side, side), Image.LANCZOS), ((size[0] - side) // 2, (size[1] - side) // 2 - size[1] // 20))
        name = f"launch-{size[0]}x{size[1]}.png"
        image.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(SPLASH / name, optimize=True)
        tags.append(
            f'<link rel="apple-touch-startup-image" media="(device-width: {width}px) and (device-height: {height}px) and '
            f'(-webkit-device-pixel-ratio: {ratio}) and (orientation: portrait)" href="/static/splash/{name}?v={VERSION}">'
        )
    return tags


# Shortcut icons: a white outline glyph on the app's purple, drawn at 4x and scaled down.
GLYPHS = {
    "add": [("line", (48, 26, 48, 70)), ("line", (26, 48, 70, 48))],
    "radar": [("arc", (22, 22, 74, 74)), ("line", (48, 48, 64, 32)), ("dot", (48, 48))],
    "pick": [("rect", (24, 24, 72, 72)), ("dot", (38, 38)), ("dot", (58, 58)), ("dot", (48, 48))],
    "daily": [("rect", (24, 28, 72, 72)), ("line", (24, 40, 72, 40)), ("line", (36, 22, 36, 32)), ("line", (60, 22, 60, 32))],
}


def shortcut_icons() -> None:
    scale = 4
    for name, parts in GLYPHS.items():
        image = Image.new("RGBA", (96 * scale, 96 * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 96 * scale - 1, 96 * scale - 1), radius=22 * scale, fill=(124, 58, 237, 255))
        width = 6 * scale
        for kind, box in parts:
            box = tuple(value * scale for value in box)
            if kind == "line":
                draw.line(box, fill="white", width=width)
                for x, y in (box[:2], box[2:]):
                    draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill="white")
            elif kind == "arc":
                draw.ellipse(box, outline="white", width=width)
            elif kind == "rect":
                draw.rounded_rectangle(box, radius=8 * scale, outline="white", width=width)
            elif kind == "dot":
                x, y = box
                draw.ellipse((x - 5 * scale, y - 5 * scale, x + 5 * scale, y + 5 * scale), fill="white")
        image.resize((96, 96), Image.LANCZOS).save(ICONS / f"shortcut-{name}.png", optimize=True)


if __name__ == "__main__":
    SPLASH.mkdir(parents=True, exist_ok=True)
    print("\n".join(splash_images()))
    shortcut_icons()
