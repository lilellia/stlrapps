from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from loguru import logger
from matplotlib import font_manager

from src.ui import TextAlignment


def get_system_fonts() -> dict[str, Path]:
    """Return a list of all fonts on the system.
    https://stackoverflow.com/a/75314833
    """
    fonts: dict[str, Path] = {}

    for filename in sorted(font_manager.findSystemFonts()):
        if "Emoji" in filename or "18030" in filename:
            logger.debug(f"ignoring font file: {filename}")
            continue

        font = ImageFont.FreeTypeFont(filename)
        name, weight = font.getname()
        fonts[f"{name} ({weight})"] = Path(filename)

    return fonts


def wrap_text(text: str, font: ImageFont.ImageFont | ImageFont.FreeTypeFont, width: int) -> str:
    """Define the wrap boundaries to keep the text within the given width box."""
    im = transparent_image(2 * width, width)
    lines: list[str] = [""]
    draw = ImageDraw.Draw(im)

    for word in text.split():
        current = lines[-1]
        extended = f"{current} {word}"

        if draw.textlength(extended, font=font) <= width:
            # It will fit, so put it on this line.
            lines[-1] = extended
        else:
            # It won't fit, so add it to the next line.
            lines.append(word)

    return "\n".join(lines)


def transparent_image(width: int, height: int) -> Image.Image:
    """Create a transparent image of the given size."""
    return Image.new("RGBA", (width, height), (255, 255, 255, 0))


def render_text(image: Image.Image, text: str, font: ImageFont.ImageFont | ImageFont.FreeTypeFont, pos: tuple[int, int],
                width: int, align: TextAlignment) -> Image.Image:
    """Render the text onto the image."""
    draw = ImageDraw.Draw(image)
    text = wrap_text(text=text, font=font, width=width)

    draw.multiline_text(pos, text, font=font, align=align.value, fill="black")

    return image
