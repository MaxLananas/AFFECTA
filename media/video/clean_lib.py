"""
AFFECTA — Bibliothèque de rendu « corporate clair » (v2).

Style : fond clair, aplats de couleur, cartes à ombre douce, typographie large,
beaucoup d'espace — inspiration keynote institutionnel (type Stripe/Apple).
Rendu image par image (Pillow + numpy), aucune dépendance externe hors Pillow/numpy.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----------------------------------------------------------------------------- config
W, H = 1920, 1080
FPS = 30

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONTS = {
    "sans":       f"{FONT_DIR}/DejaVuSans.ttf",
    "bold":       f"{FONT_DIR}/DejaVuSans-Bold.ttf",
    "mono":       f"{FONT_DIR}/DejaVuSansMono.ttf",
    "mono_bold":  f"{FONT_DIR}/DejaVuSansMono-Bold.ttf",
}

# ----------------------------------------------------------------------------- palette
BG        = (244, 246, 250)
BG2       = (236, 240, 247)
CARD      = (255, 255, 255)
INK       = (15, 23, 42)
SUB       = (51, 65, 85)
MUTE      = (108, 122, 145)
HAIR      = (222, 228, 238)

# Code couleur sémantique (réutilisé PARTOUT — voir la scène « légende »).
PRIMARY   = (37, 99, 235)       # bleu — Enseignant / structure
TEAL      = (13, 148, 136)      # teal — Poste
GREEN     = (22, 163, 74)       # vert — Vœu satisfait / succès
AMBER     = (217, 119, 6)       # ambre — Barème / attention
RED       = (225, 29, 72)       # rouge — Évincé / échec
VIOLET    = (124, 58, 237)      # violet — Priorité réglementaire
SLATE     = (100, 116, 139)     # gris — neutre / STAY


def tint(c, k=0.14):
    return tuple(int(round(c[i] * k + 255 * (1 - k))) for i in range(3))


@lru_cache(maxsize=256)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONTS[kind], size)


# ----------------------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 3 * t * t - 2 * t * t * t


def ease_out_back(t):
    t = clamp(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = clamp(t)
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


# ----------------------------------------------------------------------------- background
@lru_cache(maxsize=2)
def _bg() -> Image.Image:
    top = np.array((248, 250, 253), dtype=np.float32)
    bot = np.array((234, 238, 246), dtype=np.float32)
    ramp = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    grad = top[None, :] * (1 - ramp) + bot[None, :] * ramp
    arr = np.repeat(grad[:, None, :], W, axis=1)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    step = 54
    for y in range(step, H, step):
        for x in range(step, W, step):
            d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(15, 23, 42, 9))
    return img


def new_frame() -> Image.Image:
    return _bg().copy()


# ----------------------------------------------------------------------------- text
def _anchor_xy(draw, xy, s, fnt, anchor):
    x, y = xy
    l, t, r, b = draw.textbbox((0, 0), s, font=fnt)
    tw, th = r - l, b - t
    if anchor[0] == "m":
        x -= tw / 2
    elif anchor[0] == "r":
        x -= tw
    if anchor[1] == "m":
        y -= th / 2 + t
    elif anchor[1] == "b":
        y -= th + t
    else:
        y -= t
    return x, y


def text(draw, xy, s, fnt, fill=INK, anchor="lt", alpha=255, tracking=0, shadow=False):
    col = fill if len(fill) == 4 else (*fill, alpha)
    if tracking == 0:
        x, y = _anchor_xy(draw, xy, s, fnt, anchor)
        if shadow:
            draw.text((x, y + 2), s, font=fnt, fill=(15, 23, 42, int(alpha * 0.14)))
        draw.text((x, y), s, font=fnt, fill=col)
        return
    widths = [draw.textlength(ch, font=fnt) for ch in s]
    total = sum(widths) + tracking * (len(s) - 1)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    l, t, r, b = draw.textbbox((0, 0), s or "X", font=fnt)
    if anchor[1] == "m":
        y -= (b - t) / 2 + t
    elif anchor[1] == "b":
        y -= (b - t) + t
    else:
        y -= t
    for ch, wch in zip(s, widths):
        draw.text((x, y), ch, font=fnt, fill=col)
        x += wch + tracking


def text_width(draw, s, fnt, tracking=0):
    w = sum(draw.textlength(ch, font=fnt) for ch in s)
    if tracking and len(s) > 1:
        w += tracking * (len(s) - 1)
    return w


def wrap(draw, s, fnt, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def paragraph(draw, xy, s, fnt, fill=SUB, max_w=1000, line_h=None, anchor="lt", alpha=255):
    lines = wrap(draw, s, fnt, max_w)
    if line_h is None:
        asc, desc = fnt.getmetrics()
        line_h = int((asc + desc) * 1.4)
    x, y = xy
    a = ("m" + anchor[1]) if anchor[0] == "m" else anchor
    for i, ln in enumerate(lines):
        text(draw, (x, y + i * line_h), ln, fnt, fill=fill, anchor=a, alpha=alpha)
    return len(lines) * line_h


# ----------------------------------------------------------------------------- shapes
def _shadow(img, box, radius, blur=26, alpha=42, dy=12):
    x0, y0, x1, y1 = box
    pad = blur * 3 + 8
    gx0 = max(0, int(x0) - pad); gy0 = max(0, int(y0) - pad)
    gx1 = min(W, int(x1) + pad); gy1 = min(H, int(y1) + pad + dy)
    gw, gh = gx1 - gx0, gy1 - gy0
    if gw <= 0 or gh <= 0:
        return
    layer = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.rounded_rectangle([x0 - gx0, y0 - gy0 + dy, x1 - gx0, y1 - gy0 + dy],
                        radius=radius, fill=(20, 30, 60, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer, (gx0, gy0))


def card(img, box, radius=22, fill=CARD, border=HAIR, width=1, alpha=255,
         shadow=True, accent=None, accent_w=6):
    if shadow and alpha > 30:
        _shadow(img, box, radius, alpha=int(42 * (alpha / 255)))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    fcol = (*fill, alpha) if len(fill) == 3 else fill
    d.rounded_rectangle(box, radius=radius, fill=fcol)
    if border and width:
        d.rounded_rectangle(box, radius=radius, outline=(*border, alpha), width=width)
    if accent is not None:
        x0, y0, x1, y1 = box
        bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar, "RGBA")
        bd.rounded_rectangle([x0, y0, x0 + accent_w * 3, y1], radius=radius,
                             fill=(*accent, alpha))
        mask = Image.new("L", img.size, 0)
        md = ImageDraw.Draw(mask)
        md.rectangle([x0, y0, x0 + accent_w, y1], fill=255)
        overlay.paste(bar, (0, 0), Image.composite(bar.split()[3], Image.new("L", img.size, 0), mask))
    img.alpha_composite(overlay)


def pill(img, box, color, radius=None, alpha=255):
    x0, y0, x1, y1 = box
    if radius is None:
        radius = (y1 - y0) / 2
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    d.rounded_rectangle(box, radius=radius, fill=(*color, alpha))
    img.alpha_composite(overlay)


def chip(img, cx, cy, w, h, color, label, fnt, text_col=None, alpha=255, radius=None):
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    pill(img, box, color, radius=radius, alpha=alpha)
    d = ImageDraw.Draw(img, "RGBA")
    tc = text_col or (255, 255, 255)
    if label:
        text(d, (cx, cy), label, fnt, fill=(*tc, alpha), anchor="mm")


def soft_dot(img, center, r, color, alpha=255, blur=0):
    cx, cy = center
    pad = int(r + blur * 3 + 2)
    size = pad * 2
    if size <= 0:
        return
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    d.ellipse([pad - r, pad - r, pad + r, pad + r], fill=(*color, alpha))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer, (int(cx) - pad, int(cy) - pad))


def node(img, center, r, color, alpha=255, ring=True):
    soft_dot(img, center, r * 1.7, color, alpha=int(alpha * 0.18), blur=r * 0.7)
    soft_dot(img, center, r, color, alpha=alpha)
    if ring:
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy = center
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, int(alpha * 0.6)), width=2)


def square(img, center, r, color, alpha=255, fill=False):
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = center
    box = [cx - r, cy - r, cx + r, cy + r]
    if fill:
        d.rounded_rectangle(box, radius=max(3, r * 0.28), fill=(*color, alpha))
    else:
        d.rounded_rectangle(box, radius=max(3, r * 0.28), outline=(*color, alpha), width=3)


def line(draw, p0, p1, color, width=3, alpha=255):
    draw.line([p0, p1], fill=(*color, alpha), width=width)


def arrow(draw, p0, p1, color, width=5, head=15, alpha=255):
    draw.line([p0, p1], fill=(*color, alpha), width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for da in (math.radians(148), math.radians(-148)):
        hx = p1[0] + head * math.cos(ang + da)
        hy = p1[1] + head * math.sin(ang + da)
        draw.line([p1, (hx, hy)], fill=(*color, alpha), width=width)


def check(draw, c, color, s=14, alpha=255, width=5):
    x, y = c
    draw.line([(x - s, y), (x - s * 0.2, y + s * 0.8)], fill=(*color, alpha), width=width)
    draw.line([(x - s * 0.2, y + s * 0.8), (x + s * 1.1, y - s * 0.9)], fill=(*color, alpha), width=width)


def cross(draw, c, color, s=13, alpha=255, width=5):
    x, y = c
    draw.line([(x - s, y - s), (x + s, y + s)], fill=(*color, alpha), width=width)
    draw.line([(x - s, y + s), (x + s, y - s)], fill=(*color, alpha), width=width)


# ----------------------------------------------------------------------------- fx / chrome
def fade_white(img, k):
    if k <= 0:
        return img
    w = Image.new("RGBA", img.size, (247, 249, 252, int(255 * clamp(k))))
    img.alpha_composite(w)
    return img


def fade_edges(img, t, dur, fin=0.5, fout=0.5):
    if t < fin:
        fade_white(img, 1 - ease_out(t / fin))
    if t > dur - fout:
        fade_white(img, ease_in_out((t - (dur - fout)) / fout))


def logo_mark(draw, img, x, y, scale=1.0, alpha=255):
    r = int(9 * scale)
    pts = [(x - int(16 * scale), y - int(11 * scale)),
           (x - int(16 * scale), y + int(11 * scale)),
           (x + int(15 * scale), y)]
    for p in pts[:2]:
        draw.line([p, pts[2]], fill=(*PRIMARY, alpha), width=max(2, int(3 * scale)))
    for i, p in enumerate(pts):
        col = TEAL if i == 2 else PRIMARY
        draw.ellipse([p[0] - r // 2, p[1] - r // 2, p[0] + r // 2, p[1] + r // 2],
                     fill=(*col, alpha))


def header(img, num, total, kicker, title_alpha=255):
    d = ImageDraw.Draw(img, "RGBA")
    logo_mark(d, img, 92, 82, scale=0.85)
    text(d, (128, 82), "AFFECTA", font("bold", 26), fill=INK, anchor="lm", tracking=2)
    if kicker:
        label = kicker.upper()
        fnt = font("bold", 22)
        tw = text_width(d, label, fnt, tracking=3)
        bx1 = W - 90
        bx0 = bx1 - tw - 70
        pill(img, (bx0, 64, bx1, 104), tint(PRIMARY, 0.10))
        d = ImageDraw.Draw(img, "RGBA")
        text(d, (bx0 + 22, 84), f"{num:02d}", font("mono_bold", 22), fill=PRIMARY, anchor="lm")
        text(d, (bx0 + 58, 84), label, fnt, fill=PRIMARY, anchor="lm", tracking=3)


def progress(img, idx, total):
    d = ImageDraw.Draw(img, "RGBA")
    y = H - 54
    x0, x1 = 92, W - 92
    seg = (x1 - x0) / total
    d.rounded_rectangle([x0, y - 2, x1, y + 2], radius=2, fill=(*HAIR, 255))
    fillx = x0 + seg * (idx + 1)
    d.rounded_rectangle([x0, y - 2, fillx, y + 2], radius=2, fill=(*PRIMARY, 255))
