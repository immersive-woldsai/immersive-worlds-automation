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
    # Dark WhatsApp-like background (NOT pure black)
    d.rectangle([0, 0, W, chat_h], fill=(18, 24, 28, 255))

    # subtle doodle pattern
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
    Returns overlays in order (for each message k):
      overlay_01_typ1.png, overlay_01_typ2.png, overlay_01_typ3.png, overlay_01.png,
      overlay_02_typ1.png, overlay_02_typ2.png, overlay_02_typ3.png, overlay_02.png,
      ...
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    header_font = _font(font_path, 42)
    msg_font = _font(font_path, 44)
    time_font = _font(font_path, 30)

    left_bg = (245, 245, 245, 235)
    left_fg = (25, 25, 25, 255)

    right_bg = (26, 115, 56, 230)
    right_fg = (255, 255, 255, 255)

    # layout
    x_left = 60
    x_right = 520
    y0 = 140
    gap = 145
    radius = 28
    pad_x = 28
    pad_y = 18

    def wrap_lines(d: ImageDraw.ImageDraw, text: str, max_w: int) -> List[str]:
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

    def draw_message(d: ImageDraw.ImageDraw, m: Msg, y: int):
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

    def draw_typing_bubble(d: ImageDraw.ImageDraw, who: str, y: int, dots_on: int):
        """
        dots_on: 1..3 (anim frame)
        """
        is_left = (who == "A")
        bx = x_left if is_left else x_right

        bubble_h = 86
        bubble_w = 220
        fill = left_bg if is_left else right_bg

        box = [bx, y, bx + bubble_w, y + bubble_h]
        d.rounded_rectangle(box, radius=radius, fill=fill)

        # draw 3 dots as circles (no unicode)
        # positions
        cx0 = bx + 60
        cy = y + 43
        r = 7
        gapx = 26

        # active color
        dot_col = left_fg if is_left else right_fg
        # inactive (more transparent)
        dot_off = (dot_col[0], dot_col[1], dot_col[2], 90)

        for i in range(3):
            col = dot_col if (i < dots_on) else dot_off
            x = cx0 + i * gapx
            d.ellipse([x - r, cy - r, x + r, cy + r], fill=col)

    def draw_screen(num_msgs_visible: int, typing_for_index: int | None, dots_on: int = 3) -> Image.Image:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        _draw_whatsapp_theme(d, W, chat_h)
        d.text((50, 25), "WhatsApp", font=header_font, fill=(255, 255, 255, 235))

        y = y0
        for i in range(num_msgs_visible):
            draw_message(d, msgs[i], y)
            y += gap

        if typing_for_index is not None and typing_for_index < len(msgs):
            draw_typing_bubble(d, msgs[typing_for_index].who, y, dots_on=dots_on)

        return img

    overlays: List[Path] = []

    for k in range(len(msgs)):
        # 3 typing frames (1 dot, 2 dots, 3 dots)
        for frame, dots_on in enumerate([1, 2, 3], start=1):
            img_t = draw_screen(num_msgs_visible=k, typing_for_index=k, dots_on=dots_on)
            p_t = out_dir / f"overlay_{k+1:02d}_typ{frame}.png"
            img_t.save(p_t)
            overlays.append(p_t)

        # full frame
        img_f = draw_screen(num_msgs_visible=k+1, typing_for_index=None)
        p_f = out_dir / f"overlay_{k+1:02d}.png"
        img_f.save(p_f)
        overlays.append(p_f)

    return overlays
