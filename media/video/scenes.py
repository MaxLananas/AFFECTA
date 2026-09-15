"""
Les 8 scènes de la vidéo AFFECTA. Chaque fonction rend une image RGBA pour un
temps local t (secondes) dans une scène de durée dur.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

import render_lib as R
from render_lib import (
    W, H, font, text, text_width, paragraph, new_frame,
    rounded_panel, soft_circle, glow_dot, line, draw_arrow, wrap,
    ease_out, ease_in_out, ease_out_back, clamp, lerp, lerp_color,
    INK, MUTE, ACCENT, ACCENT2, GOLD, GREEN, RED, VIOLET, PANEL, PANEL_LN,
)

CHAPTERS = [
    None,
    "Le mouvement",
    "L'algorithme",
    "Les garanties",
    "Deux temps",
    "Performance",
    "Robustesse",
    None,
]


def _header(img, d, idx):
    if CHAPTERS[idx] is not None:
        R.chapter_tag(d, CHAPTERS[idx], idx)
    R.brand_mark(d, 120, H - 70, scale=0.8)
    R.draw_progress_dots(d, idx, 8)


def _fade_edges(img, t, dur, fin=0.6, fout=0.5):
    """Fade from/to black at scene edges."""
    if t < fin:
        R.vfade(img, ease_out(t / fin))
    if t > dur - fout:
        R.fade_to_black(img, ease_in_out((t - (dur - fout)) / fout))


# =========================================================== background particles
_RNG = random.Random(7)
_NODES = [(_RNG.uniform(0, W), _RNG.uniform(0, H), _RNG.uniform(0.2, 1.0)) for _ in range(46)]


def _network_bg(img, t, alpha=1.0):
    d = ImageDraw.Draw(img, "RGBA")
    pts = []
    for (x, y, ph) in _NODES:
        yy = y + math.sin(t * 0.5 + ph * 6.28) * 14
        xx = x + math.cos(t * 0.35 + ph * 6.28) * 12
        pts.append((xx, yy))
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dx = pts[i][0] - pts[j][0]
            dy = pts[i][1] - pts[j][1]
            dd = math.hypot(dx, dy)
            if dd < 240:
                a = int((1 - dd / 240) * 46 * alpha)
                d.line([pts[i], pts[j]], fill=(*ACCENT, a), width=1)
    for p in pts:
        d.ellipse([p[0]-2, p[1]-2, p[0]+2, p[1]+2], fill=(*ACCENT2, int(120*alpha)))


# =========================================================== Scene 1 — Intro
def scene1(t, dur, idx):
    img = new_frame().convert("RGBA")
    _network_bg(img, t, alpha=0.8)
    d = ImageDraw.Draw(img, "RGBA")

    cx, cy = W / 2, H / 2 - 40
    # converging nodes -> logo
    conv = ease_out_back(clamp((t - 0.3) / 1.3))
    node_src = [(-320, -150), (-300, 170), (330, -120), (300, 160), (0, -260)]
    for (sx, sy) in node_src:
        nx = cx + sx * (1 - conv)
        ny = cy + sy * (1 - conv)
        a = int(200 * clamp((t - 0.3) / 0.6))
        d.line([(nx, ny), (cx, cy)], fill=(*ACCENT, int(a * 0.4)), width=2)
        glow_dot(img, (nx, ny), 6, ACCENT2, intensity=int(120 * conv + 20))
    d = ImageDraw.Draw(img, "RGBA")
    # convergence flash — fades out before the wordmark locks in, so it never sits on a letter
    flash = clamp((conv - 0.5) / 0.5) * (1.0 - clamp((t - 1.4) / 0.5))
    if flash > 0:
        glow_dot(img, (cx, cy), int(10 + 8 * conv), ACCENT,
                 intensity=int(180 * flash), core_alpha=int(255 * flash))

    # wordmark
    ta = clamp((t - 1.5) / 1.0)
    if ta > 0:
        text(d, (cx, cy + 8), "AFFECTA", font("bold", 132),
             fill=(*INK, int(255 * ease_out(ta))), anchor="mm", tracking=int(18 * ease_out(ta)),
             shadow=True)
    # underline sweep
    if t > 2.2:
        sw = ease_out(clamp((t - 2.2) / 0.9))
        lw = 460 * sw
        line(d, (cx - lw / 2, cy + 92), (cx + lw / 2, cy + 92), ACCENT2, width=4,
             alpha=int(255 * sw))
    # tagline
    tg = clamp((t - 3.1) / 1.1)
    if tg > 0:
        text(d, (cx, cy + 150), "Moteur d'affectation des enseignants du premier degré",
             font("sans", 40), fill=(*MUTE, int(255 * ease_out(tg))), anchor="mm")
    tg2 = clamp((t - 3.9) / 1.1)
    if tg2 > 0:
        for i, (w, c) in enumerate([("RAPIDE", ACCENT), ("JUSTE", ACCENT2), ("TRANSPARENT", GOLD)]):
            xx = cx + (i - 1) * 300
            aa = int(255 * ease_out(clamp((t - 3.9 - i * 0.25) / 0.8)))
            text(d, (xx, cy + 232), w, font("bold", 32), fill=(*c, aa), anchor="mm", tracking=4)
            if i < 2:
                text(d, (xx + 150, cy + 232), "•", font("bold", 32), fill=(*MUTE, aa), anchor="mm")

    R.draw_progress_dots(d, idx, 8)
    _fade_edges(img, t, dur, fin=0.5, fout=0.6)
    return img


# =========================================================== Scene 2 — Le problème
def scene2(t, dur, idx):
    img = new_frame().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    _header(img, d, idx)

    title_a = clamp(t / 0.8)
    text(d, (W/2, 210), "Des milliers d'enseignants, des milliers de postes",
         font("bold", 52), fill=(*INK, int(255*ease_out(title_a))), anchor="mm")

    # two clouds of dots
    left_c = (560, 560)
    right_c = (1360, 560)
    grid_a = clamp((t - 0.7) / 1.4)
    n = 60
    for i in range(n):
        row, col = divmod(i, 10)
        appear = clamp((grid_a * n - i) / 6)
        if appear <= 0:
            continue
        # teachers
        lx = left_c[0] - 220 + col * 46
        ly = left_c[1] - 130 + row * 46
        soft_circle(img, (lx, ly), int(9 * ease_out(appear)), ACCENT, alpha=int(220*appear))
        # posts (squares)
        rx = right_c[0] - 220 + col * 46
        ry = right_c[1] - 130 + row * 46
        s = int(9 * ease_out(appear))
        ImageDraw.Draw(img, "RGBA").rectangle([rx-s, ry-s, rx+s, ry+s],
                                              outline=(*ACCENT2, int(230*appear)), width=2)
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (left_c[0], left_c[1] + 200), "ENSEIGNANTS", font("bold", 28),
         fill=(*ACCENT, int(255*grid_a)), anchor="mm", tracking=4)
    text(d, (right_c[0], right_c[1] + 200), "POSTES", font("bold", 28),
         fill=(*ACCENT2, int(255*grid_a)), anchor="mm", tracking=4)

    # regulatory order chain appears
    chain_a = clamp((t - 3.2) / 0.5)
    if chain_a > 0:
        text(d, (W/2, 800), "Un ordre réglementaire strict, poste par poste",
             font("sans", 34), fill=(*MUTE, int(255*chain_a)), anchor="mm")
        steps = ["Priorité", "Barème", "Rang du vœu", "Départages"]
        cols = [VIOLET, GOLD, ACCENT, ACCENT2]
        bw, gap = 300, 40
        total = len(steps)*bw + (len(steps)-1)*gap
        x0 = W/2 - total/2
        for i, (s, c) in enumerate(zip(steps, cols)):
            ap = ease_out(clamp((t - 3.6 - i*0.35) / 0.6))
            if ap <= 0:
                continue
            bx = x0 + i*(bw+gap)
            yy = 890
            rounded_panel(img, (bx, yy, bx+bw*ap, yy+70), radius=16,
                          fill=PANEL, outline=c, width=2, alpha=int(255*ap))
            dd = ImageDraw.Draw(img, "RGBA")
            if ap > 0.7:
                text(dd, (bx+bw/2, yy+35), s, font("bold", 30), fill=(*INK, 255), anchor="mm")
            if i < len(steps)-1 and ap > 0.9:
                R.draw_arrow(dd, (bx+bw+6, yy+35), (bx+bw+gap-6, yy+35), MUTE, width=3, head=9)
    d = ImageDraw.Draw(img, "RGBA")
    _header(img, d, idx)
    _fade_edges(img, t, dur)
    return img


# =========================================================== Scene 3 — Algorithme (star)
def scene3(t, dur, idx):
    img = new_frame().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")

    text(d, (W/2, 190), "Acceptation différée — Gale & Shapley",
         font("bold", 50), fill=(*INK, int(255*ease_out(clamp(t/0.7)))), anchor="mm")

    # layout: 4 agents left, 3 posts right
    agents = [("A1", GREEN), ("A2", ACCENT), ("A3", GOLD), ("A4", VIOLET)]
    ay = [360, 500, 640, 780]
    ax = 460
    posts = ["P1", "P2", "P3"]
    py = [430, 600, 770]
    px = 1420

    def apos(i): return (ax, ay[i])
    def ppos(j): return (px, py[j])

    # storyboard of proposals over time. (t_start, agent_idx, post_idx, outcome)
    # outcome: 'win' (green), 'reject'(red flash then re-propose)
    # We narrate a small cascade converging.
    intro = 1.2
    # Draw posts panels
    for j, p in enumerate(posts):
        pa = ease_out(clamp((t - 0.5 - j*0.15) / 0.6))
        if pa <= 0:
            continue
        cx, cy = ppos(j)
        rounded_panel(img, (cx-110, cy-52, cx+110, cy+52), radius=18,
                      fill=PANEL, outline=ACCENT2, width=2, alpha=int(255*pa), glow=None)
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (cx, cy-24), p, font("bold", 30), fill=(*ACCENT2, int(255*pa)), anchor="mm")
        text(dd, (cx, cy+16), "poste", font("sans", 20), fill=(*MUTE, int(220*pa)), anchor="mm")

    # Draw agents
    for i, (a, c) in enumerate(agents):
        pa = ease_out(clamp((t - 0.5 - i*0.12) / 0.6))
        if pa <= 0:
            continue
        cx, cy = apos(i)
        glow_dot(img, (cx, cy), int(26*pa), c, intensity=90)
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (cx, cy), a, font("bold", 26), fill=(0,0,0,int(255*pa)), anchor="mm")

    d = ImageDraw.Draw(img, "RGBA")

    # Phase captions timed
    caps = [
        (intro, 4.3, "1 — Chaque enseignant propose son meilleur vœu"),
        (4.3, 8.5, "2 — Le poste ne retient que la meilleure candidature"),
        (8.5, 12.8, "3 — L'évincé se repropose sur son vœu suivant"),
        (12.8, 99, "4 — Convergence : affectation stable"),
    ]
    for (a0, a1, s) in caps:
        if a0 <= t < a1:
            ca = clamp((t - a0)/0.4) * clamp((a1 - t)/0.4)
            text(d, (W/2, 940), s, font("sans", 34),
                 fill=(*INK, int(255*clamp(ca))), anchor="mm")

    # animated proposal arrows and assignment states.
    # define final assignment: A1->P1, A2->P2, A3->P1(loses to A1)->P3, A4->P2(loses)->stays? keep simple:
    # We'll show dynamic: phase1 all propose their first choice; conflicts resolve.
    def draw_prop(i, j, prog, color, reject=False):
        p0 = apos(i); p1 = ppos(j)
        p0 = (p0[0]+30, p0[1]); p1 = (p1[0]-112, p1[1])
        x = lerp(p0[0], p1[0], ease_in_out(prog))
        y = lerp(p0[1], p1[1], ease_in_out(prog))
        line(d, p0, (x, y), color, width=3, alpha=180)
        soft_circle(img, (x, y), 8, color, alpha=230)

    # Phase 1: t in [intro,4.3] agents propose first choices: A1->P1, A2->P2, A3->P1, A4->P2
    if intro <= t < 4.6:
        pr = clamp((t - intro)/1.6)
        for (i, j, col) in [(0,0,GREEN),(1,1,ACCENT),(2,0,GOLD),(3,1,VIOLET)]:
            draw_prop(i, j, pr, col)

    # Phase 2: t in [4.3,8.5] posts pick winners; P1 keeps A1 (reject A3), P2 keeps A2 (reject A4)
    if 4.6 <= t < 8.8:
        # winners locked
        _lock_edge(d, img, apos(0), ppos(0), GREEN)
        _lock_edge(d, img, apos(1), ppos(1), ACCENT)
        # rejects flash
        rf = 0.5 + 0.5*math.sin(t*8)
        if t < 7.0:
            draw_prop(2, 0, 1.0, RED); draw_prop(3, 1, 1.0, RED)
            _x_mark(d, ppos(0), RED, alpha=int(200*rf))
            _x_mark(d, ppos(1), RED, alpha=int(200*rf))

    # Phase 3: t in [8.5,12.8] A3->P3, A4-> re-propose P3 loses to A3 -> A4->P1? keep: A4->P3 loses, stays searching then P2? 
    if 8.8 <= t < 13.0:
        _lock_edge(d, img, apos(0), ppos(0), GREEN)
        _lock_edge(d, img, apos(1), ppos(1), ACCENT)
        pr = clamp((t-8.8)/1.6)
        draw_prop(2, 2, pr, GOLD)   # A3 -> P3

    # Phase 4: t>=12.8 final stable state
    if t >= 13.0:
        _lock_edge(d, img, apos(0), ppos(0), GREEN)
        _lock_edge(d, img, apos(1), ppos(1), ACCENT)
        _lock_edge(d, img, apos(2), ppos(2), GOLD)
        # A4 finds the last remaining slot (P2 has capacity 2 here) -> fully matched
        pr = ease_in_out(clamp((t-13.0)/1.1))
        if pr > 0:
            p0 = (apos(3)[0]+30, apos(3)[1]); p1 = (ppos(1)[0]-112, ppos(1)[1]+22)
            x = lerp(p0[0], p1[0], pr); y = lerp(p0[1], p1[1], pr)
            line(d, p0, (x, y), VIOLET, width=3, alpha=210)
            soft_circle(img, (x, y), 8, VIOLET, alpha=235)
            if pr >= 0.999:
                _lock_edge(d, img, apos(3), (ppos(1)[0], ppos(1)[1]+22), VIOLET)
        d = ImageDraw.Draw(img, "RGBA")
        # badge
        ba = ease_out(clamp((t-14.2)/0.8))
        if ba > 0:
            bx, by = W/2, 880
            rounded_panel(img, (bx-280, by-42, bx+280, by+42), radius=22,
                          fill=(16,40,30), outline=GREEN, width=2, alpha=int(255*ba), glow=GREEN)
            dd = ImageDraw.Draw(img, "RGBA")
            _check(dd, (bx-236, by), GREEN, s=16, alpha=int(255*ba))
            text(dd, (bx+8, by), "Appariement STABLE", font("bold", 34),
                 fill=(*INK, int(255*ba)), anchor="mm")

    d = ImageDraw.Draw(img, "RGBA")
    _header(img, d, idx)
    _fade_edges(img, t, dur)
    return img


def _lock_edge(d, img, a, p, color):
    p0 = (a[0]+30, a[1]); p1 = (p[0]-112, p[1])
    line(d, p0, p1, color, width=5, alpha=235)
    soft_circle(img, p1, 7, color, alpha=255)


def _x_mark(d, c, color, alpha=200, s=16):
    x, y = c[0], c[1]-70
    line(d, (x-s, y-s), (x+s, y+s), color, width=4, alpha=alpha)
    line(d, (x-s, y+s), (x+s, y-s), color, width=4, alpha=alpha)


def _check(d, c, color, s=14, alpha=255, width=5):
    x, y = c
    d.line([(x-s, y), (x-s*0.2, y+s*0.8)], fill=(*color, alpha), width=width)
    d.line([(x-s*0.2, y+s*0.8), (x+s*1.1, y-s*0.9)], fill=(*color, alpha), width=width)


# =========================================================== Scene 4 — Garanties
def scene4(t, dur, idx):
    img = new_frame().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (W/2, 200), "Trois garanties mathématiques", font("bold", 52),
         fill=(*INK, int(255*ease_out(clamp(t/0.7)))), anchor="mm")

    cards = [
        ("Sans envie justifiée",
         "Jamais un candidat mieux classé n'est privé d'un poste au profit d'un moins bien classé.",
         ACCENT, "shield"),
        ("Optimal pour les enseignants",
         "Parmi toutes les affectations stables, celle qui satisfait le mieux les vœux.",
         ACCENT2, "star"),
        ("Non manipulable",
         "Déclarer des vœux insincères ne peut jamais améliorer sa situation.",
         GOLD, "lock"),
    ]
    cw, gap = 500, 60
    total = 3*cw + 2*gap
    x0 = W/2 - total/2
    for i, (title, body, c, icon) in enumerate(cards):
        ap = ease_out_back(clamp((t - 0.8 - i*0.45)/0.8))
        if ap <= 0:
            continue
        bx = x0 + i*(cw+gap)
        by = 320
        bh = 460
        cur_h = int(bh*clamp(ap))
        rounded_panel(img, (bx, by, bx+cw, by+cur_h), radius=24,
                      fill=PANEL, outline=c, width=2, alpha=int(255*min(ap,1)), glow=c)
        if ap > 0.75:
            dd = ImageDraw.Draw(img, "RGBA")
            _icon(dd, img, (bx+cw/2, by+120), c, icon)
            text(dd, (bx+cw/2, by+230), title, font("bold", 34), fill=(*INK,255),
                 anchor="mm")
            paragraph(dd, (bx+cw/2, by+300), body, font("sans", 27), fill=MUTE,
                      max_w=cw-70, anchor="mt")
    d = ImageDraw.Draw(img, "RGBA")
    # bottom note
    na = clamp((t-3.4)/0.8)
    if na > 0:
        text(d, (W/2, 860), "Vérifié par un contrôleur indépendant — 300 / 300 instances sans envie justifiée",
             font("mono", 28), fill=(*GREEN, int(255*na)), anchor="mm")
    _header(img, d, idx)
    _fade_edges(img, t, dur)
    return img


def _icon(d, img, c, color, kind):
    x, y = c
    r = 46
    soft_circle(img, c, r+8, color, alpha=40, blur=10)
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([x-r, y-r, x+r, y+r], outline=(*color,255), width=3)
    if kind == "shield":
        pts = [(x, y-24),(x+22, y-12),(x+22, y+6),(x, y+26),(x-22, y+6),(x-22,y-12)]
        d.polygon(pts, outline=(*color,255), width=3)
        _check(d, (x-9, y-2), color, s=12, alpha=255, width=4)
    elif kind == "star":
        pts = []
        for k in range(10):
            ang = -math.pi/2 + k*math.pi/5
            rr = 26 if k % 2 == 0 else 11
            pts.append((x+rr*math.cos(ang), y+rr*math.sin(ang)))
        d.polygon(pts, fill=(*color,255))
    elif kind == "lock":
        d.rounded_rectangle([x-20, y-4, x+20, y+26], radius=6, outline=(*color,255), width=3)
        d.arc([x-13, y-24, x+13, y+6], start=180, end=360, fill=(*color,255), width=3)
        d.ellipse([x-4, y+6, x+4, y+14], fill=(*color,255))


# =========================================================== Scene 5 — Deux temps
def scene5(t, dur, idx):
    img = new_frame().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (W/2, 195), "La procédure en deux temps", font("bold", 52),
         fill=(*INK, int(255*ease_out(clamp(t/0.7)))), anchor="mm")

    # Phase 1 panel
    p1a = ease_out(clamp((t-0.6)/0.8))
    bx1 = (200, 330, 900, 720)
    if p1a > 0:
        rounded_panel(img, bx1, radius=24, fill=PANEL, outline=ACCENT, width=2,
                      alpha=int(255*p1a), glow=ACCENT)
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (550, 380), "PHASE 1", font("mono_bold", 26), fill=(*ACCENT,int(255*p1a)),
             anchor="mm", tracking=4)
        text(dd, (550, 430), "Acceptation différée", font("bold", 38),
             fill=(*INK,int(255*p1a)), anchor="mm")
        # dots mostly filled
        for i in range(24):
            row, col = divmod(i, 8)
            filled = i < 21
            cxx = 320 + col*62; cyy = 520 + row*60
            ap = clamp((t-1.2)*6 - i*0.3)
            if ap <= 0: continue
            col_c = GREEN if filled else RED
            soft_circle(img, (cxx, cyy), int(15*ease_out(ap)), col_c, alpha=int(230*ap))
        text(dd, (550, 700), "Affectation stable, optimale", font("sans", 26),
             fill=(*MUTE,int(255*p1a)), anchor="mm")

    # arrow
    ar = ease_out(clamp((t-2.6)/0.6))
    if ar > 0:
        R.draw_arrow(d, (900, 525), (900+120*ar, 525), ACCENT2, width=5, head=16)

    # Phase 2 panel
    p2a = ease_out(clamp((t-3.0)/0.8))
    bx2 = (1020, 330, 1720, 720)
    if p2a > 0:
        rounded_panel(img, bx2, radius=24, fill=PANEL, outline=ACCENT2, width=2,
                      alpha=int(255*p2a), glow=ACCENT2)
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (1370, 380), "PHASE 2", font("mono_bold", 26), fill=(*ACCENT2,int(255*p2a)),
             anchor="mm", tracking=4)
        text(dd, (1370, 430), "Extension", font("bold", 38), fill=(*INK,int(255*p2a)), anchor="mm")
        for i in range(24):
            row, col = divmod(i, 8)
            cxx = 1140 + col*62; cyy = 520 + row*60
            # the 3 previously red now turn green progressively
            was_red = i >= 21
            fill_prog = clamp((t-3.8)*1.5 - (i-21)*0.6) if was_red else 1.0
            ap = clamp((t-3.2)*6 - i*0.3)
            if ap <= 0: continue
            if was_red:
                col_c = lerp_color(RED, GREEN, ease_out(clamp(fill_prog)))
            else:
                col_c = GREEN
            soft_circle(img, (cxx, cyy), int(15*ease_out(ap)), col_c, alpha=int(230*ap))
        text(dd, (1370, 700), "Obligatoires affectés d'office", font("sans", 26),
             fill=(*MUTE,int(255*p2a)), anchor="mm")

    d = ImageDraw.Draw(img, "RGBA")
    fin = clamp((t-6.0)/0.8)
    if fin > 0:
        rounded_panel(img, (W/2-390, 800, W/2+390, 884), radius=22,
                      fill=(16,40,30), outline=GREEN, width=2, alpha=int(255*fin), glow=GREEN)
        dd = ImageDraw.Draw(img, "RGBA")
        _check(dd, (W/2-336, 842), GREEN, s=16, alpha=int(255*fin))
        text(dd, (W/2+18, 842), "100 % affectés, stabilité préservée",
             font("bold", 34), fill=(*INK,int(255*fin)), anchor="mm")
    _header(img, d, idx)
    _fade_edges(img, t, dur)
    return img


# =========================================================== Scene 6 — Performance
def scene6(t, dur, idx):
    img = new_frame().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (W/2, 185), "Performance à grande échelle", font("bold", 52),
         fill=(*INK, int(255*ease_out(clamp(t/0.7)))), anchor="mm")

    # animated counter to 100,000,000
    ca = clamp((t-0.6)/4.5)
    val = int(ease_out(ca) * 100_000_000)
    text(d, (W/2, 380), f"{val:,}".replace(",", " "), font("mono_bold", 150),
         fill=(*ACCENT2, 255), anchor="mm")
    text(d, (W/2, 490), "agents affectés", font("sans", 40), fill=(*MUTE,255), anchor="mm")

    # bar chart of scaling (log-ish visual). data: (label, seconds, color)
    data = [("1 M", 0.2), ("10 M", 1.9), ("50 M", 9.7), ("100 M", 20.0)]
    maxv = 20.0
    bx0 = 470; by0 = 900; bw = 210; gap = 90; bh_max = 300
    for i, (lab, sec) in enumerate(data):
        ap = ease_out(clamp((t - 5.0 - i*0.4)/0.7))
        if ap <= 0: continue
        h = int(bh_max * (sec/maxv) * ap)
        bx = bx0 + i*(bw+gap)
        col = lerp_color(ACCENT, VIOLET, i/3)
        rounded_panel(img, (bx, by0-h, bx+bw, by0), radius=12, fill=col,
                      outline=None, width=0, alpha=int(230))
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (bx+bw/2, by0-h-28), f"{sec:g}s", font("bold", 30),
             fill=(*INK,int(255*ap)), anchor="mm")
        text(dd, (bx+bw/2, by0+34), lab, font("bold", 30), fill=(*MUTE,int(255*ap)), anchor="mm")
    d = ImageDraw.Draw(img, "RGBA")
    lab_a = clamp((t-5.0)/0.6)
    if lab_a>0:
        text(d, (W/2, 620), "Appariement — cœur natif C (2 cœurs)", font("sans", 28),
             fill=(*MUTE,int(255*lab_a)), anchor="mm")
    _header(img, d, idx)
    _fade_edges(img, t, dur)
    return img


# =========================================================== Scene 7 — Robustesse
def scene7(t, dur, idx):
    img = new_frame().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (W/2, 195), "Robuste, éprouvé, sans compromis", font("bold", 52),
         fill=(*INK, int(255*ease_out(clamp(t/0.7)))), anchor="mm")

    # terminal-style panel with check lines
    pan = (360, 300, 1560, 780)
    pa = ease_out(clamp((t-0.5)/0.7))
    if pa > 0:
        rounded_panel(img, pan, radius=20, fill=(10,14,26), outline=PANEL_LN, width=2,
                      alpha=int(255*pa))
        dd = ImageDraw.Draw(img, "RGBA")
        # window dots
        for k, cc in enumerate([RED, GOLD, GREEN]):
            dd.ellipse([400+k*30-8, 340-8, 400+k*30+8, 340+8], fill=(*cc,int(255*pa)))
        text(dd, (760, 340), "affecta — vérification", font("mono", 24),
             fill=(*MUTE,int(255*pa)), anchor="lm")
    lines = [
        ("81 / 81  tests réussis", GREEN),
        ("300 / 300  instances sans envie justifiée", GREEN),
        ("AddressSanitizer + UBSan : aucune erreur mémoire", GREEN),
        ("ThreadSanitizer : 0 course de données (parallèle sans verrou)", GREEN),
        ("LeakSanitizer : 0 fuite mémoire", GREEN),
        ("Équivalence C ↔ Python : identique au bit près", ACCENT2),
    ]
    dd = ImageDraw.Draw(img, "RGBA")
    for i, (s, c) in enumerate(lines):
        la = clamp((t - 1.1 - i*0.85)/0.5)
        if la <= 0: continue
        yy = 410 + i*62
        _check(dd, (430, yy+8), c, s=13, alpha=int(255*la), width=4)
        text(dd, (480, yy), s, font("mono", 30), fill=(*INK,int(255*la)), anchor="lm")
        # blinking cursor on last revealed line
    # cursor
    cur_i = int(clamp((t-1.1)/0.85))
    if cur_i < len(lines) and (t*2 % 1) < 0.5:
        yy = 410 + min(cur_i,len(lines)-1)*62
        s = lines[min(cur_i,len(lines)-1)][0]
        xx = 480 + text_width(dd, s, font("mono",30))
        # only after line drawn
    _header(img, d, idx)
    _fade_edges(img, t, dur)
    return img


# =========================================================== Scene 8 — Outro
def scene8(t, dur, idx):
    img = new_frame().convert("RGBA")
    _network_bg(img, t+5, alpha=0.7)
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = W/2, H/2 - 30

    a = ease_out(clamp(t/1.0))
    # logo glyph flash — fades out as the wordmark settles
    gflash = a * (1.0 - clamp((t - 0.9) / 0.5))
    if gflash > 0:
        glow_dot(img, (cx, cy-60), int(12*a), ACCENT,
                 intensity=int(160*gflash), core_alpha=int(255*gflash))
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (cx, cy+30), "AFFECTA", font("bold", 128), fill=(*INK,int(255*a)),
         anchor="mm", tracking=int(16*a), shadow=True)
    sw = ease_out(clamp((t-0.8)/0.8))
    line(d, (cx-230*sw, cy+110), (cx+230*sw, cy+110), ACCENT2, width=4, alpha=int(255*sw))

    tg = clamp((t-1.4)/1.0)
    if tg > 0:
        for i, (w, c) in enumerate([("RAPIDE", ACCENT), ("JUSTE", ACCENT2), ("AUDITABLE", GOLD)]):
            xx = cx + (i-1)*300
            aa = int(255*ease_out(clamp((t-1.4-i*0.2)/0.8)))
            text(d, (xx, cy+180), w, font("bold", 34), fill=(*c,aa), anchor="mm", tracking=4)
            if i < 2:
                text(d, (xx+150, cy+180), "•", font("bold", 34), fill=(*MUTE,aa), anchor="mm")
    rp = clamp((t-2.6)/1.0)
    if rp > 0:
        text(d, (cx, cy+280), "github.com/MaxLananas/AFFECTA", font("mono", 30),
             fill=(*MUTE,int(255*rp)), anchor="mm")

    R.draw_progress_dots(d, idx, 8)
    _fade_edges(img, t, dur, fin=0.5, fout=1.2)
    return img


SCENES = [scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8]
DURATIONS = [10.6, 15.9, 19.7, 13.9, 13.4, 12.5, 13.4, 9.2]
