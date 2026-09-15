"""
Scènes de la vidéo AFFECTA v2 — style corporate clair.
Chaque fonction rend une image RGBA pour un temps local t (s) dans une scène de durée dur.
"""
from __future__ import annotations

import math

from PIL import ImageDraw

import clean_lib as C
from clean_lib import (
    W, H, font, text, text_width, paragraph, new_frame, card, pill, chip,
    node, square, soft_dot, line, arrow, check, cross, header, progress,
    fade_edges, ease_out, ease_in_out, ease_out_back, clamp, lerp, lerp_color, tint,
    INK, SUB, MUTE, HAIR, CARD, BG2,
    PRIMARY, TEAL, GREEN, AMBER, RED, VIOLET, SLATE,
)

TOTAL = 11


# ============================================================ helpers
def _title(d, s, y=200, alpha=255, size=60):
    text(d, (W / 2, y), s, font("bold", size), fill=(*INK, alpha), anchor="mm")


def _kicker(d, s, y, color=PRIMARY, alpha=255):
    text(d, (W / 2, y), s.upper(), font("bold", 24), fill=(*color, alpha),
         anchor="mm", tracking=5)


# ============================================================ Scene 1 — Intro
def scene1(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = W / 2, H / 2 - 30

    conv = ease_out(clamp((t - 0.2) / 1.2))
    node_fade = 1.0 - clamp((t - 1.2) / 0.4)   # gone by t≈1.6, before wordmark locks in
    if node_fade > 0:
        srcs = [(-360, -150, PRIMARY), (-330, 170, TEAL), (350, -140, PRIMARY),
                (320, 170, TEAL), (0, -250, VIOLET), (0, 250, GREEN)]
        for (sx, sy, col) in srcs:
            nx = cx + sx * (1 - conv)
            ny = (cy - 70) + sy * (1 - conv)
            a = int(210 * clamp((t - 0.2) / 0.5) * node_fade)
            if a <= 0:
                continue
            line(d, (nx, ny), (cx, cy - 70), lerp_color((235, 238, 245), col, 0.5),
                 width=2, alpha=int(a * 0.5))
            node(img, (nx, ny), int(8 * (0.5 + conv)), col, alpha=a)
        d = ImageDraw.Draw(img, "RGBA")

    ta = clamp((t - 1.3) / 0.9)
    if ta > 0:
        C.logo_mark(d, img, cx - 430, cy - 66, scale=1.6, alpha=int(255 * ease_out(ta)))
        text(d, (cx + 34, cy - 66), "AFFECTA", font("bold", 128),
             fill=(*INK, int(255 * ease_out(ta))), anchor="mm",
             tracking=int(10 * ease_out(ta)))
    if t > 2.0:
        sw = ease_out(clamp((t - 2.0) / 0.8))
        lw = 520 * sw
        d.rounded_rectangle([cx - lw / 2, cy + 14, cx + lw / 2, cy + 20], radius=3,
                            fill=(*PRIMARY, int(255 * sw)))
    tg = clamp((t - 2.7) / 1.0)
    if tg > 0:
        text(d, (cx, cy + 78), "Le moteur d'affectation des enseignants du premier degré",
             font("sans", 38), fill=(*SUB, int(255 * ease_out(tg))), anchor="mm")
    tg2 = clamp((t - 3.6) / 1.0)
    if tg2 > 0:
        labels = [("RAPIDE", PRIMARY), ("JUSTE", GREEN), ("TRANSPARENT", VIOLET)]
        gap = 300
        for i, (w, col) in enumerate(labels):
            aa = ease_out(clamp((t - 3.6 - i * 0.18) / 0.7))
            if aa <= 0:
                continue
            chip(img, cx + (i - 1) * gap, cy + 168, 236, 58, tint(col, 0.12), w,
                 font("bold", 26), text_col=col, alpha=int(255 * aa))
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur, fin=0.4, fout=0.5)
    return img


# ============================================================ Scene 2 — Le problème
def scene2(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 1, TOTAL, "Le mouvement")
    _title(d, "Des milliers d'enseignants. Des milliers de postes.",
           y=210, alpha=int(255 * ease_out(clamp(t / 0.7))), size=54)

    left_c = (560, 590)
    right_c = (1360, 590)
    grid_a = clamp((t - 0.6) / 1.6)
    n = 48
    for i in range(n):
        row, col = divmod(i, 8)
        ap = clamp((grid_a * n - i) / 5)
        if ap <= 0:
            continue
        lx = left_c[0] - 180 + col * 52
        ly = left_c[1] - 150 + row * 52
        node(img, (lx, ly), int(11 * ease_out(ap)), PRIMARY, alpha=int(255 * ap), ring=False)
        rx = right_c[0] - 180 + col * 52
        ry = right_c[1] - 150 + row * 52
        square(img, (rx, ry), int(10 * ease_out(ap)), TEAL, alpha=int(255 * ap), fill=True)
    d = ImageDraw.Draw(img, "RGBA")
    la = clamp((t - 1.4) / 0.6)
    if la > 0:
        chip(img, left_c[0], left_c[1] + 210, 300, 56, tint(PRIMARY, 0.12),
             "ENSEIGNANTS", font("bold", 26), text_col=PRIMARY, alpha=int(255 * la))
        chip(img, right_c[0], right_c[1] + 210, 300, 56, tint(TEAL, 0.12),
             "POSTES", font("bold", 26), text_col=TEAL, alpha=int(255 * la))

    qa = clamp((t - 2.6) / 0.8)
    if qa > 0:
        text(d, (W / 2, 590), "?", font("bold", 130), fill=(*MUTE, int(120 * qa)), anchor="mm")
    note = clamp((t - 3.4) / 0.8)
    if note > 0:
        text(d, (W / 2, 880),
             "Comment affecter le plus d'enseignants, au plus près de leurs vœux,",
             font("sans", 32), fill=(*SUB, int(255 * note)), anchor="mm")
        text(d, (W / 2, 924), "sous des contraintes réglementaires strictes ?",
             font("sans", 32), fill=(*SUB, int(255 * note)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 3 — Légende (code couleur)
_LEGEND = [
    (PRIMARY, "node",   "Enseignant",  "un candidat au mouvement"),
    (TEAL,    "square", "Poste",       "un support à pourvoir"),
    (GREEN,   "check",  "Vœu satisfait", "affectation sur un vœu"),
    (RED,     "cross",  "Évincé",      "candidature écartée"),
    (VIOLET,  "pill",   "Priorité",    "titre / exigence réglementaire"),
    (AMBER,   "pill",   "Barème",      "points de classement"),
]


def scene3(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 2, TOTAL, "Repères")
    _kicker(d, "Le code couleur", 150, alpha=int(255 * ease_out(clamp(t / 0.6))))
    _title(d, "Une grammaire visuelle, la même partout", y=222,
           alpha=int(255 * ease_out(clamp((t - 0.15) / 0.7))))

    cols = 2
    cw, ch = 700, 150
    gapx, gapy = 60, 40
    x0 = W / 2 - (cols * cw + (cols - 1) * gapx) / 2
    y0 = 360
    for i, (col, kind, name, desc) in enumerate(_LEGEND):
        r, c = divmod(i, cols)
        ap = ease_out(clamp((t - 0.8 - i * 0.22) / 0.7))
        if ap <= 0:
            continue
        bx = x0 + c * (cw + gapx)
        by = y0 + r * (ch + gapy)
        card(img, (bx, by, bx + cw, by + ch), radius=20, accent=col, alpha=int(255 * ap))
        if ap > 0.6:
            pill(img, (bx + 40, by + 40, bx + 140, by + ch - 40), tint(col, 0.14))
            dd = ImageDraw.Draw(img, "RGBA")
            ic = (bx + 90, by + ch / 2)
            if kind == "node":
                node(img, ic, 20, col)
            elif kind == "square":
                square(img, ic, 18, col, fill=True)
            elif kind == "check":
                check(dd, (ic[0] - 4, ic[1]), col, s=18, width=6)
            elif kind == "cross":
                cross(dd, ic, col, s=15, width=6)
            elif kind == "pill":
                pill(img, (ic[0] - 34, ic[1] - 14, ic[0] + 34, ic[1] + 14), col)
            dd = ImageDraw.Draw(img, "RGBA")
            text(dd, (bx + 180, by + 52), name, font("bold", 34), fill=INK, anchor="lm")
            text(dd, (bx + 180, by + 100), desc, font("sans", 26), fill=MUTE, anchor="lm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 4 — Ordre réglementaire
def scene4(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 3, TOTAL, "La règle")
    _kicker(d, "Traitement poste par poste", 150, alpha=int(255 * ease_out(clamp(t / 0.6))))
    _title(d, "Un ordre réglementaire strict, non négociable", y=222,
           alpha=int(255 * ease_out(clamp((t - 0.15) / 0.7))))

    steps = [
        ("1", "Priorité", "titre / exigence\n(CAPPEI, direction…)", VIOLET),
        ("2", "Barème", "points de\nclassement", AMBER),
        ("3", "Rang du vœu", "ordre déclaré\npar l'enseignant", PRIMARY),
        ("4", "Sous-rang", "position dans\nun vœu groupe", TEAL),
        ("5", "Départages", "ancienneté EN,\néchelon, aléa", SLATE),
    ]
    cw, gap = 300, 34
    total = len(steps) * cw + (len(steps) - 1) * gap
    x0 = W / 2 - total / 2
    y, ch = 400, 300
    for i, (num, name, desc, col) in enumerate(steps):
        ap = ease_out(clamp((t - 0.9 - i * 0.35) / 0.7))
        if ap <= 0:
            continue
        bx = x0 + i * (cw + gap)
        card(img, (bx, y, bx + cw, y + ch), radius=20, accent=col, alpha=int(255 * ap))
        if ap > 0.6:
            pcx, pcy = bx + cw / 2, y + 78
            soft_dot(img, (pcx, pcy), 40, col, alpha=int(255 * ap))
            dd = ImageDraw.Draw(img, "RGBA")
            text(dd, (pcx, pcy), num, font("bold", 44), fill=(255, 255, 255, int(255 * ap)), anchor="mm")
            text(dd, (pcx, y + 158), name, font("bold", 30), fill=INK, anchor="mm")
            for k, ln in enumerate(desc.split("\n")):
                text(dd, (pcx, y + 208 + k * 34), ln, font("sans", 24), fill=MUTE, anchor="mm")
        if i < len(steps) - 1 and ap > 0.9:
            axx = bx + cw + 4
            arrow(d, (axx, y + ch / 2), (axx + gap - 8, y + ch / 2), MUTE, width=3, head=9)

    src = clamp((t - 3.4) / 0.8)
    if src > 0:
        text(d, (W / 2, 800),
             "Conforme à la chaîne MVT1D publiée (académies de Bordeaux, Toulouse, Poitiers).",
             font("sans", 28), fill=(*SUB, int(255 * src)), anchor="mm")
        text(d, (W / 2, 848),
             "AFFECTA n'invente aucune règle — le non-sourcé reste marqué UNKNOWN.",
             font("sans", 26), fill=(*MUTE, int(255 * src)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 5 — Acceptation différée
def scene5(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 4, TOTAL, "L'algorithme")
    _title(d, "Acceptation différée — Gale & Shapley", y=200,
           alpha=int(255 * ease_out(clamp(t / 0.7))))

    agents = [("A1", 0), ("A2", 1), ("A3", 2), ("A4", 3)]
    ay = [370, 500, 630, 760]
    ax = 470
    posts = ["P1", "P2", "P3"]
    py = [430, 585, 740]
    px = 1430

    def apos(i): return (ax, ay[i])
    def ppos(j): return (px, py[j])

    for j, p in enumerate(posts):
        pa = ease_out(clamp((t - 0.5 - j * 0.12) / 0.6))
        if pa <= 0:
            continue
        cxp, cyp = ppos(j)
        card(img, (cxp - 120, cyp - 52, cxp + 120, cyp + 52), radius=18, accent=TEAL, alpha=int(255 * pa))
        dd = ImageDraw.Draw(img, "RGBA")
        square(img, (cxp - 66, cyp), 16, TEAL, fill=True, alpha=int(255 * pa))
        text(dd, (cxp + 20, cyp - 16), p, font("bold", 30), fill=(*INK, int(255 * pa)), anchor="mm")
        text(dd, (cxp + 20, cyp + 18), "poste", font("sans", 20), fill=(*MUTE, int(230 * pa)), anchor="mm")

    for i, (a, _) in enumerate(agents):
        pa = ease_out(clamp((t - 0.5 - i * 0.1) / 0.6))
        if pa <= 0:
            continue
        cxa, cya = apos(i)
        node(img, (cxa, cya), int(30 * pa), PRIMARY, alpha=int(255 * pa))
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (cxa, cya), a, font("bold", 26), fill=(255, 255, 255, int(255 * pa)), anchor="mm")

    d = ImageDraw.Draw(img, "RGBA")
    caps = [
        (1.0, 4.0, "Chaque enseignant propose son meilleur vœu"),
        (4.0, 8.0, "Le poste ne retient que la meilleure candidature"),
        (8.0, 12.0, "L'évincé se reporte sur son vœu suivant"),
        (12.0, 13.6, "Convergence : appariement stable"),
    ]
    for (a0, a1, s) in caps:
        if a0 <= t < a1:
            ca = clamp((t - a0) / 0.4) * clamp((a1 - t) / 0.4)
            chip(img, W / 2, 910, text_width(d, s, font("sans", 32)) + 90, 64,
                 tint(PRIMARY, 0.10), "", font("sans", 32), alpha=int(255 * ca))
            dd = ImageDraw.Draw(img, "RGBA")
            text(dd, (W / 2, 910), s, font("sans", 32), fill=(*INK, int(255 * ca)), anchor="mm")

    def prop(i, j, prog, color):
        p0 = apos(i); p1 = ppos(j)
        p0 = (p0[0] + 34, p0[1]); p1 = (p1[0] - 122, p1[1])
        x = lerp(p0[0], p1[0], ease_in_out(prog)); y = lerp(p0[1], p1[1], ease_in_out(prog))
        line(d, p0, (x, y), color, width=3, alpha=170)
        soft_dot(img, (x, y), 9, color, alpha=235)

    def lock(i, j, color, dy=0):
        p0 = apos(i); p1 = ppos(j)
        p0 = (p0[0] + 34, p0[1]); p1 = (p1[0] - 122, p1[1] + dy)
        line(d, p0, p1, color, width=6, alpha=240)
        soft_dot(img, p1, 8, color, alpha=255)

    if 1.0 <= t < 4.2:
        pr = clamp((t - 1.0) / 1.4)
        for (i, j) in [(0, 0), (1, 1), (2, 0), (3, 1)]:
            prop(i, j, pr, PRIMARY)
    if 4.2 <= t < 8.2:
        lock(0, 0, GREEN); lock(1, 1, GREEN)
        if t < 6.6:
            prop(2, 0, 1.0, RED); prop(3, 1, 1.0, RED)
            rf = int(200 * (0.5 + 0.5 * math.sin(t * 8)))
            cross(d, (ppos(0)[0], ppos(0)[1] - 68), RED, alpha=rf)
            cross(d, (ppos(1)[0], ppos(1)[1] - 68), RED, alpha=rf)
    if 8.2 <= t < 12.2:
        lock(0, 0, GREEN); lock(1, 1, GREEN)
        prop(2, 2, clamp((t - 8.2) / 1.5), PRIMARY)
    if t >= 12.2:
        lock(0, 0, GREEN); lock(1, 1, GREEN); lock(2, 2, GREEN)
        pr = ease_in_out(clamp((t - 12.2) / 1.1))
        if pr > 0:
            p0 = (apos(3)[0] + 34, apos(3)[1]); p1 = (ppos(1)[0] - 122, ppos(1)[1] + 24)
            x = lerp(p0[0], p1[0], pr); y = lerp(p0[1], p1[1], pr)
            line(d, p0, (x, y), GREEN, width=6, alpha=240)
            soft_dot(img, (x, y), 8, GREEN, alpha=255)
        ba = ease_out(clamp((t - 13.6) / 0.7))
        if ba > 0:
            bw = 460
            card(img, (W / 2 - bw / 2, 792, W / 2 + bw / 2, 868), radius=20,
                 fill=tint(GREEN, 0.12), border=GREEN, alpha=int(255 * ba))
            dd = ImageDraw.Draw(img, "RGBA")
            check(dd, (W / 2 - 176, 830), GREEN, s=16, alpha=int(255 * ba))
            text(dd, (W / 2 + 12, 830), "Appariement STABLE", font("bold", 34),
                 fill=(*INK, int(255 * ba)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 6 — Trois garanties
def scene6(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 5, TOTAL, "Les garanties")
    _title(d, "Trois garanties mathématiques", y=200,
           alpha=int(255 * ease_out(clamp(t / 0.7))))

    cards = [
        ("Sans envie justifiée",
         "Jamais un candidat mieux classé n'est privé d'un poste au profit d'un moins bien classé.",
         PRIMARY, "shield"),
        ("Optimal pour les enseignants",
         "Parmi toutes les affectations stables, celle qui satisfait le mieux les vœux.",
         GREEN, "star"),
        ("Non manipulable",
         "Déclarer des vœux insincères ne peut jamais améliorer sa situation.",
         VIOLET, "lock"),
    ]
    cw, gap = 500, 60
    total = 3 * cw + 2 * gap
    x0 = W / 2 - total / 2
    by, bh = 330, 470
    for i, (title, body, col, icon) in enumerate(cards):
        ap = ease_out_back(clamp((t - 0.8 - i * 0.4) / 0.8))
        if ap <= 0:
            continue
        bx = x0 + i * (cw + gap)
        card(img, (bx, by, bx + cw, by + bh), radius=24, accent=col, alpha=int(255 * min(ap, 1)))
        if ap > 0.7:
            _garantie_icon(img, (bx + cw / 2, by + 130), col, icon)
            dd = ImageDraw.Draw(img, "RGBA")
            text(dd, (bx + cw / 2, by + 250), title, font("bold", 33), fill=INK, anchor="mm")
            paragraph(dd, (bx + cw / 2, by + 310), body, font("sans", 26), fill=SUB,
                      max_w=cw - 80, anchor="mt")
    d = ImageDraw.Draw(img, "RGBA")
    na = clamp((t - 3.2) / 0.8)
    if na > 0:
        msg = "Vérifié indépendamment — 300 / 300 instances sans envie justifiée"
        fnt = font("mono", 26)
        tw = text_width(d, msg, fnt)
        bw = tw + 150
        card(img, (W / 2 - bw / 2, 858, W / 2 + bw / 2, 932), radius=20,
             fill=tint(GREEN, 0.12), border=GREEN, alpha=int(255 * na))
        dd = ImageDraw.Draw(img, "RGBA")
        check(dd, (W / 2 - bw / 2 + 46, 895), GREEN, s=15, alpha=int(255 * na))
        text(dd, (W / 2 + 40, 895), msg, fnt, fill=(*INK, int(255 * na)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


def _garantie_icon(img, c, col, kind):
    x, y = c
    soft_dot(img, c, 58, col, alpha=30, blur=8)
    d = ImageDraw.Draw(img, "RGBA")
    r = 50
    d.ellipse([x - r, y - r, x + r, y + r], outline=(*col, 255), width=3)
    if kind == "shield":
        pts = [(x, y - 26), (x + 24, y - 13), (x + 24, y + 7), (x, y + 28),
               (x - 24, y + 7), (x - 24, y - 13)]
        d.polygon(pts, outline=(*col, 255), width=3)
        check(d, (x - 10, y - 2), col, s=13, width=5)
    elif kind == "star":
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            rr = 28 if k % 2 == 0 else 12
            pts.append((x + rr * math.cos(ang), y + rr * math.sin(ang)))
        d.polygon(pts, fill=(*col, 255))
    elif kind == "lock":
        d.rounded_rectangle([x - 22, y - 4, x + 22, y + 28], radius=6, outline=(*col, 255), width=3)
        d.arc([x - 14, y - 26, x + 14, y + 6], start=180, end=360, fill=(*col, 255), width=3)
        d.ellipse([x - 4, y + 8, x + 4, y + 16], fill=(*col, 255))


# ============================================================ Scene 7 — Deux temps
def scene7(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 6, TOTAL, "La procédure")
    _title(d, "Le mouvement en deux temps", y=200,
           alpha=int(255 * ease_out(clamp(t / 0.7))))

    p1 = ease_out(clamp((t - 0.6) / 0.8))
    bx1 = (200, 330, 900, 730)
    if p1 > 0:
        card(img, bx1, radius=24, accent=PRIMARY, alpha=int(255 * p1))
        chip(img, 300, 390, 170, 48, tint(PRIMARY, 0.14), "PHASE 1",
             font("mono_bold", 22), text_col=PRIMARY, alpha=int(255 * p1))
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (550, 460), "Acceptation différée", font("bold", 36),
             fill=(*INK, int(255 * p1)), anchor="mm")
        for i in range(24):
            row, col = divmod(i, 8)
            filled = i < 21
            cxx = 330 + col * 62; cyy = 540 + row * 58
            ap = clamp((t - 1.2) * 6 - i * 0.3)
            if ap <= 0:
                continue
            cc = GREEN if filled else SLATE
            node(img, (cxx, cyy), int(15 * ease_out(ap)), cc, alpha=int(255 * ap), ring=False)
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (550, 710), "Affectation stable, optimale", font("sans", 26),
             fill=(*MUTE, int(255 * p1)), anchor="mm")

    ar = ease_out(clamp((t - 2.6) / 0.6))
    if ar > 0:
        arrow(d, (905, 530), (905 + 110 * ar, 530), PRIMARY, width=6, head=16)

    p2 = ease_out(clamp((t - 3.0) / 0.8))
    bx2 = (1020, 330, 1720, 730)
    if p2 > 0:
        card(img, bx2, radius=24, accent=TEAL, alpha=int(255 * p2))
        chip(img, 1120, 390, 170, 48, tint(TEAL, 0.14), "PHASE 2",
             font("mono_bold", 22), text_col=TEAL, alpha=int(255 * p2))
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (1370, 460), "Extension", font("bold", 36), fill=(*INK, int(255 * p2)), anchor="mm")
        for i in range(24):
            row, col = divmod(i, 8)
            cxx = 1150 + col * 62; cyy = 540 + row * 58
            was = i >= 21
            fp = clamp((t - 3.8) * 1.5 - (i - 21) * 0.6) if was else 1.0
            ap = clamp((t - 3.2) * 6 - i * 0.3)
            if ap <= 0:
                continue
            cc = lerp_color(SLATE, GREEN, ease_out(clamp(fp))) if was else GREEN
            node(img, (cxx, cyy), int(15 * ease_out(ap)), cc, alpha=int(255 * ap), ring=False)
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (1370, 710), "Obligatoires affectés d'office", font("sans", 26),
             fill=(*MUTE, int(255 * p2)), anchor="mm")

    fin = clamp((t - 6.0) / 0.8)
    if fin > 0:
        bw = 780
        card(img, (W / 2 - bw / 2, 800, W / 2 + bw / 2, 876), radius=20,
             fill=tint(GREEN, 0.12), border=GREEN, alpha=int(255 * fin))
        dd = ImageDraw.Draw(img, "RGBA")
        check(dd, (W / 2 - 336, 838), GREEN, s=15, alpha=int(255 * fin))
        text(dd, (W / 2 + 8, 838), "100 % affectés, stabilité préservée",
             font("bold", 32), fill=(*INK, int(255 * fin)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 8 — Efficacité de Pareto
def scene8(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 7, TOTAL, "Aller plus loin")
    _kicker(d, "Nouveau — efficacité de Pareto", 150,
            alpha=int(255 * ease_out(clamp(t / 0.6))), color=VIOLET)
    _title(d, "Des échanges gagnants pour tous", y=222,
           alpha=int(255 * ease_out(clamp((t - 0.15) / 0.7))))

    ax = [640, 640]; ay = [470, 720]
    px = [1280, 1280]; py = [470, 720]
    names = ["A", "B"]
    intro = ease_out(clamp((t - 0.7) / 0.7))
    for i in range(2):
        if intro <= 0:
            break
        node(img, (ax[i], ay[i]), int(34 * intro), PRIMARY, alpha=int(255 * intro))
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (ax[i], ay[i]), names[i], font("bold", 30),
             fill=(255, 255, 255, int(255 * intro)), anchor="mm")
        card(img, (px[i] - 130, py[i] - 56, px[i] + 130, py[i] + 56), radius=18,
             accent=TEAL, alpha=int(255 * intro))
        dd = ImageDraw.Draw(img, "RGBA")
        square(img, (px[i] - 74, py[i]), 16, TEAL, fill=True, alpha=int(255 * intro))
        text(dd, (px[i] + 16, py[i] - 14), f"Poste {i+1}", font("bold", 26),
             fill=(*INK, int(255 * intro)), anchor="mm")

    d = ImageDraw.Draw(img, "RGBA")
    if 1.6 <= t < 4.6:
        ca = clamp((t - 1.6) / 0.4) * clamp((4.6 - t) / 0.4)
        for i in range(2):
            line(d, (ax[i] + 36, ay[i]), (px[i] - 132, py[i]), SLATE, width=5, alpha=int(220 * ca))
            chip(img, (ax[i] + px[i]) / 2, ay[i] - 42, 150, 46, tint(AMBER, 0.16),
                 "VŒU 2", font("bold", 22), text_col=AMBER, alpha=int(255 * ca))
        text(d, (W / 2, 900), "Deux enseignants sur leur vœu n°2, sans poste vacant à gagner…",
             font("sans", 32), fill=(*SUB, int(255 * ca)), anchor="mm")

    if t >= 4.6:
        pr = ease_in_out(clamp((t - 4.6) / 1.6))
        for i, j in [(0, 1), (1, 0)]:
            p0 = (ax[i] + 36, ay[i]); p1 = (px[j] - 132, py[j])
            x = lerp(p0[0], p1[0], pr); y = lerp(p0[1], p1[1], pr)
            col = lerp_color(VIOLET, GREEN, pr)
            line(d, p0, (x, y), col, width=6, alpha=235)
            soft_dot(img, (x, y), 9, col, alpha=245)
        if pr > 0.5:
            ca = clamp((pr - 0.5) / 0.5)
            chip(img, W / 2 + 40, 430, 150, 46, tint(GREEN, 0.16), "VŒU 1",
                 font("bold", 22), text_col=GREEN, alpha=int(255 * ca))
            chip(img, W / 2 + 40, 760, 150, 46, tint(GREEN, 0.16), "VŒU 1",
                 font("bold", 22), text_col=GREEN, alpha=int(255 * ca))
        cap = clamp((t - 5.0) / 0.6)
        if cap > 0:
            text(d, (W / 2, 900), "… échangent leurs postes : tous les deux gagnants, équité préservée.",
                 font("sans", 32), fill=(*INK, int(255 * cap)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 9 — Comparaison données réelles
def scene9(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 8, TOTAL, "Résultats")
    _kicker(d, "Guadeloupe 2026 · 1 200 enseignants · postes réels", 150,
            alpha=int(255 * ease_out(clamp(t / 0.6))))
    _title(d, "Mesuré sur données réelles", y=222,
           alpha=int(255 * ease_out(clamp((t - 0.15) / 0.7))))

    rows = [
        ("Ancien moteur", 13.6, SLATE, "glouton"),
        ("AFFECTA — acceptation différée", 76.75, PRIMARY, "stable"),
        ("AFFECTA — + échanges de Pareto", 77.1, GREEN, "stable + Pareto"),
    ]
    x_lab = 150
    x_bar0 = 150
    bar_max_w = W - 300
    y0 = 400
    row_h = 176
    maxpct = 100.0
    for i, (name, pct, col, tag) in enumerate(rows):
        ap = ease_out(clamp((t - 0.9 - i * 0.5) / 0.8))
        if ap <= 0:
            continue
        yy = y0 + i * row_h
        text(d, (x_lab, yy - 62), name, font("bold", 32), fill=(*INK, int(255 * ap)), anchor="lm")
        tag_w = text_width(d, tag.upper(), font("bold", 20), 1) + 46
        chip(img, x_bar0 + bar_max_w - tag_w / 2, yy - 62, tag_w, 44,
             tint(col, 0.16), tag.upper(), font("bold", 20), text_col=col, alpha=int(255 * ap))
        d = ImageDraw.Draw(img, "RGBA")
        d.rounded_rectangle([x_bar0, yy - 28, x_bar0 + bar_max_w, yy + 28], radius=28,
                            fill=(*BG2, 255), outline=(*HAIR, 255), width=1)
        w = bar_max_w * (pct / maxpct) * ap
        if w > 60:
            d.rounded_rectangle([x_bar0, yy - 28, x_bar0 + w, yy + 28], radius=28, fill=(*col, 255))
            text(d, (x_bar0 + w - 24, yy), f"{pct:.1f}%", font("bold", 32),
                 fill=(255, 255, 255, int(255 * ap)), anchor="rm")
        elif w > 6:
            d.rounded_rectangle([x_bar0, yy - 28, x_bar0 + w, yy + 28], radius=28, fill=(*col, 255))
            text(d, (x_bar0 + w + 20, yy), f"{pct:.1f}%", font("bold", 32),
                 fill=(*col, int(255 * ap)), anchor="lm")
    cap = clamp((t - 3.2) / 0.8)
    if cap > 0:
        text(d, (W / 2, 900),
             "Part d'enseignants obtenant leur premier vœu — à barème et règles identiques.",
             font("sans", 30), fill=(*SUB, int(255 * cap)), anchor="mm")
        text(d, (W / 2, 946),
             "Vœux synthétiques ; postes extraits des documents officiels du mouvement.",
             font("sans", 24), fill=(*MUTE, int(255 * cap)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 10 — Performance + Robustesse
def scene10(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    header(img, 9, TOTAL, "À l'échelle")
    _title(d, "Rapide, et éprouvé", y=200, alpha=int(255 * ease_out(clamp(t / 0.7))))

    ca = clamp((t - 0.5) / 3.5)
    val = int(ease_out(ca) * 100_000_000)
    text(d, (W / 2, 330), f"{val:,}".replace(",", " "), font("mono_bold", 132),
         fill=(*PRIMARY, 255), anchor="mm")
    text(d, (W / 2, 428), "agents appariés — cœur natif C, 2 cœurs", font("sans", 32),
         fill=(*MUTE, 255), anchor="mm")

    data = [("1 M", 0.2), ("10 M", 1.9), ("50 M", 9.7), ("100 M", 20.0)]
    maxv = 20.0
    bx0 = 190; by0 = 900; bw = 120; gap = 50; bh_max = 240
    la0 = ease_out(clamp((t - 4.0) / 0.5))
    if la0 > 0:
        text(d, (bx0, 540), "Passage à l'échelle", font("bold", 30),
             fill=(*INK, int(255 * la0)), anchor="lm")
    for i, (lab, sec) in enumerate(data):
        ap = ease_out(clamp((t - 4.3 - i * 0.3) / 0.6))
        if ap <= 0:
            continue
        h = int(bh_max * (sec / maxv) * ap)
        bx = bx0 + i * (bw + gap)
        col = lerp_color(PRIMARY, VIOLET, i / 3)
        d.rounded_rectangle([bx, by0 - h, bx + bw, by0], radius=12, fill=(*col, 255))
        text(d, (bx + bw / 2, by0 - h - 26), f"{sec:g}s", font("bold", 26),
             fill=(*INK, int(255 * ap)), anchor="mm")
        text(d, (bx + bw / 2, by0 + 30), lab, font("bold", 24), fill=(*MUTE, int(255 * ap)), anchor="mm")

    pan = (1120, 540, 1760, 940)
    pa = ease_out(clamp((t - 4.3) / 0.6))
    if pa > 0:
        card(img, pan, radius=22, accent=GREEN, alpha=int(255 * pa))
        dd = ImageDraw.Draw(img, "RGBA")
        text(dd, (1170, 600), "Robustesse", font("bold", 32), fill=(*INK, int(255 * pa)), anchor="lm")
        lines = [
            "88 / 88 tests réussis",
            "0 envie justifiée (300 instances)",
            "ASan · UBSan · TSan · LSan : clean",
            "C ↔ Python : identique au bit près",
        ]
        for i, s in enumerate(lines):
            la = clamp((t - 5.0 - i * 0.4) / 0.5)
            if la <= 0:
                continue
            yy = 686 + i * 58
            check(dd, (1178, yy), GREEN, s=12, alpha=int(255 * la), width=5)
            text(dd, (1216, yy), s, font("mono", 24), fill=(*INK, int(255 * la)), anchor="lm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur)
    return img


# ============================================================ Scene 11 — Outro
def scene11(t, dur, idx):
    img = new_frame()
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = W / 2, H / 2 - 40
    a = ease_out(clamp(t / 0.9))
    C.logo_mark(d, img, cx - 424, cy - 6, scale=1.6, alpha=int(255 * a))
    text(d, (cx + 34, cy - 6), "AFFECTA", font("bold", 126), fill=(*INK, int(255 * a)),
         anchor="mm", tracking=int(8 * a))
    sw = ease_out(clamp((t - 0.7) / 0.8))
    lw = 520 * sw
    d.rounded_rectangle([cx - lw / 2, cy + 74, cx + lw / 2, cy + 80], radius=3,
                        fill=(*PRIMARY, int(255 * sw)))
    tg = clamp((t - 1.2) / 0.9)
    if tg > 0:
        text(d, (cx, cy + 140), "Plus juste. Plus rapide. Entièrement auditable.",
             font("sans", 38), fill=(*SUB, int(255 * ease_out(tg))), anchor="mm")
    ch = clamp((t - 2.0) / 0.9)
    if ch > 0:
        labels = [("RAPIDE", PRIMARY), ("JUSTE", GREEN), ("AUDITABLE", VIOLET)]
        for i, (w, col) in enumerate(labels):
            aa = ease_out(clamp((t - 2.0 - i * 0.16) / 0.6))
            if aa <= 0:
                continue
            chip(img, cx + (i - 1) * 300, cy + 232, 240, 58, tint(col, 0.12), w,
                 font("bold", 26), text_col=col, alpha=int(255 * aa))
    rp = clamp((t - 3.0) / 0.9)
    if rp > 0:
        text(d, (cx, cy + 330), "github.com/MaxLananas/AFFECTA", font("mono", 30),
             fill=(*MUTE, int(255 * rp)), anchor="mm")
    progress(img, idx, TOTAL)
    fade_edges(img, t, dur, fin=0.5, fout=1.0)
    return img


SCENES = [scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8, scene9, scene10, scene11]
DURATIONS = [9.5, 11.0, 12.0, 12.5, 17.5, 13.0, 13.5, 13.0, 12.5, 13.5, 10.0]
