"""
Bibliothèque de rendu pour la vidéo de présentation AFFECTA.
Rendu image par image (Pillow + numpy), style institutionnel sombre.
Aucune dépendance externe hors Pillow/numpy.
"""
from __future__ import annotations

import math
import os
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
    "serif":      f"{FONT_DIR}/DejaVuSerif.ttf",
    "serif_bold": f"{FONT_DIR}/DejaVuSerif-Bold.ttf",
}

# ----------------------------------------------------------------------------- palette
BG_TOP    = (11, 16, 32)      # deep navy
BG_BOT    = (5, 8, 18)        # near-black
INK       = (233, 238, 250)   # near-white text
MUTE      = (140, 152, 180)   # muted grey-blue
ACCENT    = (86, 169, 255)    # bright blue
ACCENT2   = (0, 224, 198)     # teal/mint
GOLD      = (245, 197, 91)    # warm accent
GREEN     = (72, 210, 140)
RED       = (240, 96, 104)
VIOLET    = (168, 130, 255)
PANEL     = (22, 30, 52)
PANEL_LN  = (44, 58, 92)


@lru_cache(maxsize=128)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONTS[kind], size)


# ----------------------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):        # cubic
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


# ----------------------------------------------------------------------------- backgrounds
@lru_cache(maxsize=4)
def _base_gradient() -> Image.Image:
    """Vertical navy gradient with a faint vignette + subtle grid — cached."""
    top = np.array(BG_TOP, dtype=np.float32)
    bot = np.array(BG_BOT, dtype=np.float32)
    ramp = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    grad = (top[None, :] * (1 - ramp) + bot[None, :] * ramp)  # H x 3
    arr = np.repeat(grad[:, None, :], W, axis=1)              # H x W x 3

    # radial vignette
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W / 2, H * 0.42
    d = np.sqrt(((xx - cx) / (W * 0.75)) ** 2 + ((yy - cy) / (H * 0.75)) ** 2)
    vig = clamp_np(1.0 - 0.55 * d)
    arr *= vig[:, :, None]

    # faint glow near top center
    g = np.exp(-(((xx - cx) / (W * 0.42)) ** 2 + ((yy - cy) / (H * 0.34)) ** 2))
    arr += g[:, :, None] * np.array([10, 20, 40], dtype=np.float32)

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")

    # subtle grid overlay
    d2 = ImageDraw.Draw(img, "RGBA")
    step = 60
    for x in range(0, W, step):
        d2.line([(x, 0), (x, H)], fill=(255, 255, 255, 4), width=1)
    for y in range(0, H, step):
        d2.line([(0, y), (W, y)], fill=(255, 255, 255, 4), width=1)
    return img


def clamp_np(a):
    return np.clip(a, 0.0, 1.0)


def new_frame() -> Image.Image:
    return _base_gradient().copy()


# ----------------------------------------------------------------------------- text
def _anchor_xy(draw, xy, text, fnt, anchor):
    x, y = xy
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    tw, th = r - l, b - t
    if anchor in ("mm", "mt", "mb"):
        x -= tw / 2
    elif anchor in ("rm", "rt", "rb"):
        x -= tw
    if anchor in ("mm", "lm", "rm"):
        y -= th / 2 + t
    elif anchor in ("mb", "lb", "rb"):
        y -= th + t
    else:
        y -= t
    return x, y


def text(draw, xy, s, fnt, fill=INK, anchor="lt", alpha=255,
         shadow=False, tracking=0):
    """Draw text with optional letter-spacing (tracking) and drop shadow."""
    col = fill if len(fill) == 4 else (*fill, alpha)
    if tracking == 0:
        x, y = _anchor_xy(draw, xy, s, fnt, anchor)
        if shadow:
            draw.text((x + 2, y + 3), s, font=fnt, fill=(0, 0, 0, int(alpha * 0.5)))
        draw.text((x, y), s, font=fnt, fill=col)
        return
    # manual tracking
    widths = [draw.textlength(ch, font=fnt) for ch in s]
    total = sum(widths) + tracking * (len(s) - 1)
    x, y = xy
    if anchor in ("mm", "mt", "mb"):
        x -= total / 2
    elif anchor in ("rm", "rt", "rb"):
        x -= total
    l, t, r, b = draw.textbbox((0, 0), s or "X", font=fnt)
    if anchor in ("mm", "lm", "rm"):
        y -= (b - t) / 2 + t
    for ch, wch in zip(s, widths):
        if shadow:
            draw.text((x + 2, y + 3), ch, font=fnt, fill=(0, 0, 0, int(alpha * 0.5)))
        draw.text((x, y), ch, font=fnt, fill=col)
        x += wch + tracking


def text_width(draw, s, fnt, tracking=0):
    w = sum(draw.textlength(ch, font=fnt) for ch in s)
    if tracking and len(s) > 1:
        w += tracking * (len(s) - 1)
    return w


def wrap(draw, s, fnt, max_w):
    words = s.split()
    lines, cur = [], ""
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


def paragraph(draw, xy, s, fnt, fill=INK, max_w=1000, line_h=None,
              anchor="lt", alpha=255):
    lines = wrap(draw, s, fnt, max_w)
    if line_h is None:
        asc, desc = fnt.getmetrics()
        line_h = int((asc + desc) * 1.35)
    x, y = xy
    for i, ln in enumerate(lines):
        a = "m" + anchor[1] if anchor[0] == "m" else anchor
        text(draw, (x, y + i * line_h), ln, fnt, fill=fill, anchor=a, alpha=alpha)
    return len(lines) * line_h


# ----------------------------------------------------------------------------- shapes
def rounded_panel(img, box, radius=24, fill=PANEL, outline=PANEL_LN,
                  width=2, alpha=255, glow=None):
    x0, y0, x1, y1 = box
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    if glow is not None:
        # Blur only a padded crop around the box, not the whole frame (much cheaper).
        pad = 40
        gx0 = max(0, int(x0) - pad); gy0 = max(0, int(y0) - pad)
        gx1 = min(img.size[0], int(x1) + pad); gy1 = min(img.size[1], int(y1) + pad)
        gw, gh = gx1 - gx0, gy1 - gy0
        if gw > 0 and gh > 0:
            gl = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
            gd = ImageDraw.Draw(gl, "RGBA")
            gd.rounded_rectangle([x0 - gx0, y0 - gy0, x1 - gx0, y1 - gy0],
                                 radius=radius, fill=(*glow, 90))
            gl = gl.filter(ImageFilter.GaussianBlur(20))
            img.alpha_composite(gl, (gx0, gy0))
    fcol = (*fill, alpha) if len(fill) == 3 else fill
    d.rounded_rectangle(box, radius=radius, fill=fcol)
    if outline and width:
        ocol = (*outline, alpha) if len(outline) == 3 else outline
        d.rounded_rectangle(box, radius=radius, outline=ocol, width=width)
    img.alpha_composite(overlay)


def soft_circle(img, center, r, color, alpha=255, blur=0):
    cx, cy = center
    pad = int(r + blur * 3 + 2)
    x0 = int(cx) - pad; y0 = int(cy) - pad
    size = pad * 2
    if size <= 0:
        return
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    lc = pad
    d.ellipse([lc - r, lc - r, lc + r, lc + r], fill=(*color, alpha))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer, (x0, y0))


def glow_dot(img, center, r, color, intensity=160, core_alpha=255):
    soft_circle(img, center, r * 2.6, color, alpha=int(intensity * 0.5), blur=r)
    soft_circle(img, center, r, color, alpha=core_alpha)


def line(draw, p0, p1, color, width=3, alpha=255):
    draw.line([p0, p1], fill=(*color, alpha), width=width)


def draw_arrow(draw, p0, p1, color, width=4, head=14, alpha=255):
    draw.line([p0, p1], fill=(*color, alpha), width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for da in (math.radians(150), math.radians(-150)):
        hx = p1[0] + head * math.cos(ang + da)
        hy = p1[1] + head * math.sin(ang + da)
        draw.line([p1, (hx, hy)], fill=(*color, alpha), width=width)


# ----------------------------------------------------------------------------- fx
def fade_to_black(img, k):
    """k in [0,1]; 0 = full image, 1 = black."""
    if k <= 0:
        return img
    black = Image.new("RGBA", img.size, (0, 0, 0, int(255 * clamp(k))))
    img.alpha_composite(black)
    return img


def vfade(img, k):
    """k in [0,1]; 0 black, 1 image (fade FROM black)."""
    return fade_to_black(img, 1 - k)


def draw_progress_dots(draw, idx, total, y=H - 46):
    gap = 34
    total_w = gap * (total - 1)
    x0 = W / 2 - total_w / 2
    for i in range(total):
        c = ACCENT if i == idx else (70, 84, 120)
        r = 7 if i == idx else 5
        draw.ellipse([x0 + i * gap - r, y - r, x0 + i * gap + r, y + r],
                     fill=(*c, 255))


def chapter_tag(draw, label, num):
    text(draw, (120, 90), f"{num:02d}", font("mono_bold", 30), fill=ACCENT2)
    text(draw, (180, 96), label.upper(), font("bold", 24), fill=MUTE, tracking=6)
    line(draw, (120, 132), (180 + text_width(draw, label.upper(), font("bold", 24), 6), 132),
         PANEL_LN, width=2)


# ----------------------------------------------------------------------------- watermark / brand
def brand_mark(draw, x, y, scale=1.0, alpha=255):
    """Small AFFECTA wordmark with a node glyph."""
    r = int(11 * scale)
    cx, cy = x, y
    # glyph: three nodes converging
    pts = [(cx - int(16*scale), cy - int(10*scale)),
           (cx - int(16*scale), cy + int(10*scale)),
           (cx + int(14*scale), cy)]
    for p in pts[:2]:
        draw.line([p, pts[2]], fill=(*ACCENT, alpha), width=max(2, int(3*scale)))
    for p in pts:
        draw.ellipse([p[0]-r//2, p[1]-r//2, p[0]+r//2, p[1]+r//2], fill=(*ACCENT2, alpha))
    text(draw, (cx + int(28*scale), cy), "AFFECTA",
         font("bold", int(30*scale)), fill=(*INK, alpha), anchor="lm", tracking=3)
