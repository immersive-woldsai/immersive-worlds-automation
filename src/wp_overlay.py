from dataclasses import dataclass
from pathlib import Path
from typing import List
from PIL import Image, ImageDraw, ImageFont

@dataclass
class Msg:
    who: str   # "A" left, "B" right, "INNER" right-ish
    text: str
    hhmm: str

def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def render_whatsapp_overlays(
    out_dir: Path,
    msgs: List[Msg],
    W: int = 1080,
    H: int = 1920,
    chat_h: int = 980,
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
) -> List[Path]:
    """
    Creates overlay PNGs with alpha:
    overlay_01.png shows 1st msg, overlay_02 shows 1st+2nd, ...
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # style
    header_font = _font(font_path, 42)
    msg_font = _font(font_path, 44)
    time_font = _font(font_path, 30)

    left_bg = (245, 245, 245, 235)      # light bubble
    left_fg = (25, 25, 25, 255)

    right_bg = (26, 115, 56, 220)       # whatsapp-ish green
    right_fg = (255, 255, 255, 255)

    overlay_bg = (0, 0, 0, 110)         # dark glass at top

    overlays = []

    for k in range(1, len(msgs) + 1):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # dark top panel for readability
        d.rectangle([0, 0, W, chat_h], fill=overlay_bg)

        # header
        d.text((50, 25), "WhatsApp", font=header_font, fill=(255, 255, 255, 235))

        # bubbles layout
        x_left = 60
        x_right = 520
        y = 140
        gap = 145

        for i in range(k):
            m = msgs[i]
            text = m.text.strip()
            hhmm = m.hhmm.strip()

            is_left = (m.who == "A")
            bx = x_left if is_left else x_right
            max_w = 900 if is_left else 500
            pad_x = 28
            pad_y = 18

            # wrap text
            lines = []
            words = text.split()
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

            # compute bubble size
            line_h = msg_font.size + 10
            bubble_h = pad_y * 2 + line_h * len(lines) + 36
            bubble_w = min(max_w + pad_x * 2, 960)

            # background bubble (rounded)
            radius = 28
            box = [bx, y, bx + bubble_w, y + bubble_h]
            fill = left_bg if is_left else right_bg
            d.rounded_rectangle(box, radius=radius, fill=fill)

            # text
            tx = bx + pad_x
            ty = y + pad_y
            fill_txt = left_fg if is_left else right_fg
            for ln in lines:
                d.text((tx, ty), ln, font=msg_font, fill=fill_txt)
                ty += line_h

            # time
            time_y = y + bubble_h - 42
            if is_left:
                d.text((bx + pad_x, time_y), hhmm, font=time_font, fill=(0, 0, 0, 140))
            else:
                # time + ticks
                d.text((bx + pad_x, time_y), hhmm, font=time_font, fill=(255, 255, 255, 160))
                d.text((bx + pad_x + 170, time_y), "✓✓", font=time_font, fill=(255, 255, 255, 160))

            y += gap

        out_path = out_dir / f"overlay_{k:02d}.png"
        img.save(out_path)
        overlays.append(out_path)

    return overlays
