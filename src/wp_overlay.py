from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import random

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


THEMES = [
    ((18, 24, 28), 18),   # dark teal
    ((22, 18, 28), 18),   # dark purple
    ((16, 22, 18), 18),   # dark green
    ((28, 20, 18), 18),   # dark brown
    ((15, 15, 18), 18),   # near-black blue
    ((30, 35, 40), 16),   # gray-ish
]


def _draw_whatsapp_theme(d: ImageDraw.ImageDraw, W: int, chat_h: int, theme_seed: int) -> None:
    rng = random.Random(theme_seed)

    base_rgb, _alpha = rng.choice(THEMES)

    # ✅ temiz, premium base
    d.rectangle([0, 0, W, chat_h], fill=(*base_rgb, 255))

    # ✅ desen de her videoda değişsin
    style = rng.choice(PATTERN_STYLES)
    _draw_pattern(d, W, chat_h, style=style, theme_seed=theme_seed)

def _draw_pattern(d: ImageDraw.ImageDraw, W: int, chat_h: int, style: str, theme_seed: int):
    rng = random.Random(theme_seed * 99991 + 17)

    if style == "none":
        return

    # çok hafif, gözü yormasın
    alpha = rng.choice([10, 12, 14, 16])
    col = (255, 255, 255, alpha)

    if style == "dots":
        step = rng.choice([70, 80, 90])
        r = rng.choice([4, 5, 6])
        for y in range(0, chat_h + step, step):
            for x in range(0, W + step, step):
                d.ellipse([x - r, y - r, x + r, y + r], fill=col)

    elif style == "diagonal":
        step = rng.choice([60, 72, 84])
        for i in range(-chat_h, W, step):
            d.line([i, 0, i + chat_h, chat_h], fill=col, width=2)

    elif style == "waves":
        step = rng.choice([80, 90, 100])
        amp = rng.choice([10, 14, 18])
        # basit dalga çizgileri
        for y0 in range(50, chat_h, step):
            points = []
            for x in range(0, W + 1, 40):
                y = y0 + int(amp * (1 if (x // 40) % 2 == 0 else -1))
                points.append((x, y))
            d.line(points, fill=col, width=2)

def render_whatsapp_overlays(
    out_dir: Path,
    msgs: List[Msg],
    W: int = 1080,
    H: int = 1920,
    chat_h: int = 980,
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
) -> List[Path]:
    """
    For each message k, produces 4 overlays:
      overlay_01_typ1.png, overlay_01_typ2.png, overlay_01_typ3.png, overlay_01.png
      overlay_02_typ1.png, ...
    Returns overlays in that exact order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    header_font = _font(font_path, 42)
    msg_font = _font(font_path, 44)
    time_font = _font(font_path, 30)

    # Bubble colors
    left_bg = (245, 245, 245, 235)
    left_fg = (25, 25, 25, 255)

    right_bg = (26, 115, 56, 230)
    right_fg = (255, 255, 255, 255)

    # Layout constants
    x_left = 60
    x_right = 520
    y0 = 140
    gap = 145
    radius = 28
    pad_x = 28
    pad_y = 18

    def wrap_lines(d: ImageDraw.ImageDraw, text: str, max_w: int) -> List[str]:
        words = (text or "").strip().split()
        lines: List[str] = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if d.textlength(test, font=msg_font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw_message(d: ImageDraw.ImageDraw, m: Msg, y: int) -> None:
        is_left = (m.who == "A")
        bx = x_left if is_left else x_right
        max_w = 900 if is_left else 500

        lines = wrap_lines(d, m.text, max_w=max_w)
        line_h = msg_font.size + 10
        bubble_h = pad_y * 2 + line_h * len(lines) + 36
        bubble_w = min(max_w + pad_x * 2, 960)

        fill = left_bg if is_left else right_bg
        fill_txt = left_fg if is_left else right_fg

        box = [bx, y, bx + bubble_w, y + bubble_h]
        d.rounded_rectangle(box, radius=radius, fill=fill)

        tx = bx + pad_x
        ty = y + pad_y
        for ln in lines:
            d.text((tx, ty), ln, font=msg_font, fill=fill_txt)
            ty += line_h

        time_y = y + bubble_h - 42
        if is_left:
            d.text((bx + pad_x, time_y), m.hhmm, font=time_font, fill=(0, 0, 0, 140))
        else:
            d.text((bx + pad_x, time_y), m.hhmm, font=time_font, fill=(255, 255, 255, 160))
            d.text((bx + pad_x + 170, time_y), "✓✓", font=time_font, fill=(255, 255, 255, 160))

    def draw_typing_bubble(d: ImageDraw.ImageDraw, who: str, y: int, dots_on: int) -> None:
        is_left = (who == "A")
        bx = x_left if is_left else x_right

        bubble_h = 86
        bubble_w = 220
        fill = left_bg if is_left else right_bg
        box = [bx, y, bx + bubble_w, y + bubble_h]
        d.rounded_rectangle(box, radius=radius, fill=fill)

        dot_col = left_fg if is_left else right_fg
        dot_off = (dot_col[0], dot_col[1], dot_col[2], 90)

        cx0 = bx + 60
        cy = y + 43
        r = 7
        gapx = 26

        for i in range(3):
            col = dot_col if i < dots_on else dot_off
            x = cx0 + i * gapx
            d.ellipse([x - r, cy - r, x + r, cy + r], fill=col)

    def draw_screen(
        num_msgs_visible: int,
        typing_for_index: Optional[int],
        dots_on: int,
        theme_seed: int,
    ) -> Image.Image:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        _draw_whatsapp_theme(d, W, chat_h, theme_seed)

        d.text((50, 25), "WhatsApp", font=header_font, fill=(255, 255, 255, 235))

        y = y0
        for i in range(num_msgs_visible):
            draw_message(d, msgs[i], y)
            y += gap

        if typing_for_index is not None and typing_for_index < len(msgs):
            draw_typing_bubble(d, msgs[typing_for_index].who, y, dots_on=dots_on)

        return img

    overlays: List[Path] = []
    theme_seed = random.randint(1, 10_000_000)  # one theme per video

    for k in range(len(msgs)):
        # 3 typing frames
        for frame, dots_on in enumerate([1, 2, 3], start=1):
            img_t = draw_screen(num_msgs_visible=k, typing_for_index=k, dots_on=dots_on, theme_seed=theme_seed)
            p_t = out_dir / f"overlay_{k+1:02d}_typ{frame}.png"
            img_t.save(p_t)
            overlays.append(p_t)

        # full frame
        img_f = draw_screen(num_msgs_visible=k + 1, typing_for_index=None, dots_on=3, theme_seed=theme_seed)
        p_f = out_dir / f"overlay_{k+1:02d}.png"
        img_f.save(p_f)
        overlays.append(p_f)

    return overlays
