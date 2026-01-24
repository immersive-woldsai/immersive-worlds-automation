from dataclasses import dataclass
from pathlib import Path
from typing import List
from PIL import Image, ImageDraw, ImageFont


@dataclass
class Msg:
    who: str   # "A" left, "B" right
    text: str
    hhmm: str


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _draw_whatsapp_theme(d: ImageDraw.ImageDraw, W: int, chat_h: int):
    """
    Dark WhatsApp-like theme + subtle doodle pattern.
    """
    # Base dark background (WhatsApp dark-ish)
    d.rectangle([0, 0, W, chat_h], fill=(18, 24, 28, 255))

    # Subtle doodle-like pattern (very low alpha)
    step = 92
    col = (255, 255, 255, 18)
    for y in range(0, chat_h + step, step):
        for x in range(0, W + step, step):
            d.ellipse([x + 12, y + 18, x + 32, y + 38], outline=col, width=2)
            d.arc([x + 40, y + 10, x + 82, y + 52], start=0, end=220, fill=col, width=2)
            d.line([x + 10, y + 60, x + 70, y + 60], fill=col, width=2)


def render_whatsapp_overlays(
    out_dir: Path,
    msgs: List[Msg],
    W: int = 1080,
    H: int = 1920,
    chat_h: int = 980,
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
) -> List[Path]:
    """
    Returns overlays in this order:
      overlay_01_typing.png, overlay_01.png,
      overlay_02_typing.png, overlay_02.png,
      ...
    Each "typing" shows messages up to k-1 plus typing bubble for k.
    Each "full" shows messages up to k.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    header_font = _font(font_path, 42)
    msg_font = _font(font_path, 44)
    time_font = _font(font_path, 30)

    # Bubbles
    left_bg = (245, 245, 245, 235)       # incoming bubble
    left_fg = (25, 25, 25, 255)

    right_bg = (26, 115, 56, 230)        # whatsapp-ish green
    right_fg = (255, 255, 255, 255)

    # Layout
    x_left = 60
    x_right = 520
    y0 = 140
    gap = 145
    radius = 28
    pad_x = 28
    pad_y = 18

    def _wrap_lines(d: ImageDraw.ImageDraw, text: str, max_w: int) -> List[str]:
        words = (text or "").strip().split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            tw = d.textlength(test, font=msg_font)
            if tw <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def _draw_message(d: ImageDraw.ImageDraw, m: Msg, y: int):
        is_left = (m.who == "A")
        bx = x_left if is_left else x_right
        max_w = 900 if is_left else 500

        lines = _wrap_lines(d, m.text, max_w=max_w)

        line_h = msg_font.size + 10
        bubble_h = pad_y * 2 + line_h * len(lines) + 36
        bubble_w = min(max_w + pad_x * 2, 960)

        box = [bx, y, bx + bubble_w, y + bubble_h]
        fill = left_bg if is_left else right_bg
        d.rounded_rectangle(box, radius=radius, fill=fill)

        tx = bx + pad_x
        ty = y + pad_y
        fill_txt = left_fg if is_left else right_fg
        for ln in lines:
            d.text((tx, ty), ln, font=msg_font, fill=fill_txt)
            ty += line_h

        time_y = y + bubble_h - 42
        if is_left:
            d.text((bx + pad_x, time_y), m.hhmm, font=time_font, fill=(0, 0, 0, 140))
        else:
            d.text((bx + pad_x, time_y), m.hhmm, font=time_font, fill=(255, 255, 255, 160))
            d.text((bx + pad_x + 170, time_y), "✓✓", font=time_font, fill=(255, 255, 255, 160))

    def _draw_typing(d: ImageDraw.ImageDraw, who: str, y: int):
        is_left = (who == "A")
        bx = x_left if is_left else x_right

        bubble_h = 86
        bubble_w = 280
        box = [bx, y, bx + bubble_w, y + bubble_h]
        fill = left_bg if is_left else right_bg
        fill_txt = left_fg if is_left else right_fg

        d.rounded_rectangle(box, radius=radius, fill=fill)
        d.text((bx + 32, y + 16), "typing...", font=msg_font, fill=fill_txt)

    def _draw_screen(num_msgs_visible: int, typing_for_index: int | None) -> Image.Image:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Theme background (not pure black)
        _draw_whatsapp_theme(d, W, chat_h)

        # Header
        d.text((50, 25), "WhatsApp", font=header_font, fill=(255, 255, 255, 235))

        y = y0

        # Draw messages
        for i in range(num_msgs_visible):
            _draw_message(d, msgs[i], y)
            y += gap

        # Draw typing bubble (if requested and valid)
        if typing_for_index is not None and typing_for_index < len(msgs):
            _draw_typing(d, msgs[typing_for_index].who, y)

        return img

    overlays: List[Path] = []

    # For each message index k: typing screen then full screen
    for k in range(len(msgs)):
        # typing: show first k messages + typing bubble for k
        img_t = _draw_screen(num_msgs_visible=k, typing_for_index=k)
        p_t = out_dir / f"overlay_{k+1:02d}_typing.png"
        img_t.save(p_t)
        overlays.append(p_t)

        # full: show first k+1 messages
        img_f = _draw_screen(num_msgs_visible=k+1, typing_for_index=None)
        p_f = out_dir / f"overlay_{k+1:02d}.png"
        img_f.save(p_f)
        overlays.append(p_f)

    return overlays
