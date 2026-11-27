"""Pixel art acogedor: camión con remolque largo llegando a un almacén
en una tarde de otoño.

Genera:
  camion_almacen.gif  (animación: llega, frena, saluda, se abre el muelle)
  camion_almacen.png  (fotograma final a 4x)

Uso: python3 camion_almacen.py
"""
import math
import os
import random

import numpy as np
from PIL import Image

W, H = 480, 270
OUT = os.path.dirname(os.path.abspath(__file__))
_cache = {}


def C(h):
    if h not in _cache:
        s = h.lstrip("#")
        _cache[h] = np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.float32)
    return _cache[h]


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


# =================================================================== lienzo
class Canvas:
    def __init__(self, track=False):
        self.a = np.zeros((H, W, 3), np.float32)
        self.m = np.zeros((H, W), bool) if track else None

    def copy(self):
        c = Canvas()
        c.a = self.a.copy()
        return c

    @staticmethod
    def _clip(x0, y0, x1, y1):
        return max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))

    def rect(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = self._clip(x0, y0, x1, y1)
        if x0 < x1 and y0 < y1:
            self.a[y0:y1, x0:x1] = C(c)
            if self.m is not None:
                self.m[y0:y1, x0:x1] = True

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = C(c)
            if self.m is not None:
                self.m[y, x] = True

    def blend_rect(self, x0, y0, x1, y1, c, a):
        x0, y0, x1, y1 = self._clip(x0, y0, x1, y1)
        if x0 < x1 and y0 < y1:
            self.a[y0:y1, x0:x1] = self.a[y0:y1, x0:x1] * (1 - a) + C(c) * a

    def blend_px(self, x, y, c, a):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = self.a[y, x] * (1 - a) + C(c) * a

    def _disk(self, cx, cy, rx, ry=None):
        ry = rx if ry is None else ry
        x0, y0, x1, y1 = self._clip(cx - rx - 1, cy - ry - 1, cx + rx + 2, cy + ry + 2)
        if x0 >= x1 or y0 >= y1:
            return None
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = ((xx + .5 - cx) / max(rx, .01)) ** 2 + ((yy + .5 - cy) / max(ry, .01)) ** 2
        return (slice(y0, y1), slice(x0, x1)), d, yy, xx

    def ellipse(self, cx, cy, rx, ry, c, a=None, ymax=None, ymin=None):
        r = self._disk(cx, cy, rx, ry)
        if r is None:
            return
        sl, d, yy, _ = r
        m = d <= 1
        if ymax is not None:
            m &= yy < ymax
        if ymin is not None:
            m &= yy >= ymin
        if a is None:
            self.a[sl][m] = C(c)
            if self.m is not None:
                self.m[sl][m] = True
        else:
            self.a[sl][m] = self.a[sl][m] * (1 - a) + C(c) * a

    def circle(self, cx, cy, r, c, a=None, ymax=None, ymin=None):
        self.ellipse(cx, cy, r, r, c, a, ymax, ymin)

    def glow(self, cx, cy, r, c, s, clip=None):
        """Luz aditiva con caída suave (opcionalmente recortada a un rectángulo)."""
        res = self._disk(cx, cy, r)
        if res is None:
            return
        sl, d, yy, xx = res
        k = np.clip(1 - np.sqrt(d), 0, 1) ** 2 * s
        if clip is not None:
            k = k * ((xx >= clip[0]) & (xx < clip[2]) & (yy >= clip[1]) & (yy < clip[3]))
        self.a[sl] += k[..., None] * C(c)

    def spans(self, rows, c, a=None):
        for y, x0, x1 in rows:
            if a is None:
                self.rect(x0, y, x1, y + 1, c)
            else:
                self.blend_rect(x0, y, x1, y + 1, c, a)

    def line(self, x0, y0, x1, y1, c):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n):
            t = i / max(n - 1, 1)
            self.px(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), c)

    def sprite(self, x, y, rows, pal):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != ".":
                    self.px(x + i, y + j, pal[ch])

    def text(self, x, y, s, c, font, scale=1, spacing=1):
        for ch in s:
            g = font.get(ch, font[" "])
            for gy, row in enumerate(g):
                for gx, v in enumerate(row):
                    if v == "#":
                        self.rect(x + gx * scale, y + gy * scale,
                                  x + (gx + 1) * scale, y + (gy + 1) * scale, c)
            if ch == "É":
                self.rect(x + 3 * scale, y - 3 * scale, x + 4 * scale, y - 2 * scale, c)
                self.rect(x + 2 * scale, y - 2 * scale, x + 3 * scale, y - 1 * scale, c)
            x += (len(g[0]) + spacing) * scale


def composite(dst, spr, outline="#1d1626"):
    """Pega un sprite con contorno oscuro de 1 px (estilo pixel art)."""
    m = spr.m
    dil = m.copy()
    dil[1:] |= m[:-1]; dil[:-1] |= m[1:]; dil[:, 1:] |= m[:, :-1]; dil[:, :-1] |= m[:, 1:]
    dst.a[dil & ~m] = C(outline)
    dst.a[m] = spr.a[m]


# =================================================================== fuentes
F5 = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "É": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "1": [".#.", "##.", ".#.", ".#.", ".#.", ".#.", "###"],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    " ": ["...", "...", "...", "...", "...", "...", "..."],
}
F3 = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "I": ["#", "#", "#", "#", "#"],
    "E": ["###", "#..", "##.", "#..", "###"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    " ": ["..", "..", "..", "..", ".."],
}


def text_w(s, font, scale=1, spacing=1):
    return sum((len(font[ch][0]) + spacing) * scale for ch in s) - spacing * scale


# =================================================================== escena fija
WALL_X0, WALL_X1 = 320, 468
DOCK_Y = 180
D1 = (336, 370)
D2 = (390, 424)
DOOR_TOP = 139
TREES = [(150, 134, 18), (300, 116, 26), (22, 128, 16)]


def autumn_tree(cv, x, y, r, rnd):
    # Tronco y ramas
    cv.rect(x - 2, y + r // 2, x + 2, 172, "#5a3a2c")
    cv.rect(x - 2, y + r // 2, x - 1, 172, "#7a5038")
    cv.line(x, y + r // 2, x - r // 2, y, "#5a3a2c")
    cv.line(x, y + r // 2 + 2, x + r // 2, y + 2, "#5a3a2c")
    blobs = [(x + rnd.uniform(-r * .7, r * .7), y + rnd.uniform(-r * .5, r * .4),
              rnd.uniform(r * .38, r * .6)) for _ in range(9)]
    for bx, by, br in blobs:
        cv.circle(bx + 1.5, by + 1.5, br, "#8e3a2a")
    for bx, by, br in blobs:
        cv.circle(bx, by, br - .5, "#c9522e")
    for bx, by, br in blobs:
        cv.circle(bx - 1, by - 1.5, br - 2.5, "#e57f35")
    for bx, by, br in blobs:
        cv.circle(bx - 2, by - 3, br - 5, "#f6b04a")
    for _ in range(int(r * 2.5)):        # hojas sueltas para textura
        a, d = rnd.uniform(0, 6.28), rnd.uniform(0, r)
        cv.px(x + math.cos(a) * d, y + math.sin(a) * d * .8,
              rnd.choice(["#ffd27a", "#b8452a", "#f39a3c"]))
    # luz de atardecer por la izquierda
    for bx, by, br in blobs:
        cv.circle(bx - br * .55, by - br * .3, 1.6, "#ffe2a0")


def draw_background():
    cv = Canvas()
    rnd = random.Random(11)

    # ---- Cielo con tramado ordenado (Bayer)
    bands = ["#2b2a5e", "#383575", "#4a3f88", "#5f4893", "#7a5099", "#985a9b", "#b7659a",
             "#d27492", "#e88a86", "#f4a37c", "#f9bc7c", "#fdd38a", "#ffe3a2"]
    sky_h = 158
    for y in range(sky_h):
        t = y / sky_h * (len(bands) - 1)
        i = min(int(t), len(bands) - 2)
        f = np.clip((t - i - 0.45) / 0.55, 0, 1)
        row = np.where(f > BAYER[y % 4][np.arange(W) % 4], 1, 0)
        cv.a[y] = np.where(row[:, None] == 1, C(bands[i + 1]), C(bands[i]))
    for _ in range(55):
        x, y = rnd.randrange(W), rnd.randrange(0, 48)
        cv.px(x, y, "#fff6d8" if rnd.random() < .35 else "#a9a3dc")
    for x, y in [(52, 12), (226, 8), (412, 18), (330, 30)]:
        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            cv.px(x + dx, y + dy, "#fff6d8")

    # ---- Sol
    cv.glow(96, 146, 90, "#ff9a5a", .35)
    cv.glow(96, 146, 40, "#ffd48a", .45)
    cv.circle(96, 146, 19, "#ffe7a8")
    cv.circle(95, 145, 16, "#fff3c8")

    # ---- Nubes esponjosas iluminadas desde abajo-izquierda
    def cloud(x, y, w):
        r2 = random.Random(x * 7 + y)
        blobs = []
        for i in range(max(3, w // 9)):
            bx = x + (i + .5) * w / max(3, w // 9) + r2.uniform(-3, 3)
            br = r2.uniform(5, 9) * (1 - abs(i / max(3, w // 9) - .45))
            blobs.append((bx, y - br * .5, max(br, 3.5)))
        for bx, by, br in blobs:
            cv.circle(bx + 1, by + 2, br, "#a8688f", ymax=y + 3)
        for bx, by, br in blobs:
            cv.circle(bx, by, br, "#e594a0", ymax=y + 2)
        for bx, by, br in blobs:
            cv.circle(bx - 1, by - 1.5, br - 2, "#ffc7b0", ymax=y - 1)
        for bx, by, br in blobs:
            cv.circle(bx - 2, by - 3, br - 4.5, "#ffe8cc", ymax=y - 3)
        cv.rect(x + 2, y + 2, x + w - 2, y + 3, "#c97a98")
    for args in [(140, 62, 62), (212, 46, 42), (292, 34, 74), (24, 88, 48),
                 (376, 70, 52), (250, 100, 30), (420, 40, 40)]:
        cloud(*args)

    # ---- Montañas lejanas, colinas con pueblito y línea de árboles
    for x in range(W):
        y1 = int(124 + 9 * math.sin(x * .013 + 1) + 5 * math.sin(x * .041))
        cv.rect(x, y1, x + 1, 172, "#9b74a6")
        cv.px(x, y1, "#c08fae")
    g = (np.linspace(0, 1, 55) ** 2 * .35)[:, None, None]     # bruma cálida en el horizonte
    cv.a[110:165] = cv.a[110:165] * (1 - g) + C("#ffc89a") * g
    for x in range(W):
        y2 = int(142 + 6 * math.sin(x * .022 + 2) + 3 * math.sin(x * .07))
        cv.rect(x, y2, x + 1, 172, "#6c5088")
        cv.px(x, y2, "#8d6aa0")
    # Pueblo a lo lejos con ventanas encendidas
    for hx in [170, 178, 187, 195, 206, 214, 226, 236]:
        hy = int(142 + 6 * math.sin(hx * .022 + 2) + 3 * math.sin(hx * .07)) + 2
        hh = 4 + (hx * 3) % 3
        cv.rect(hx, hy - hh, hx + 6, hy, "#55406e")
        for k in range(4):
            cv.rect(hx - 1 + k, hy - hh - 1 - (k if k < 2 else 3 - k), hx + 7 - k,
                    hy - hh - (k if k < 2 else 3 - k), "#43325a")
        cv.px(hx + 2, hy - 2, "#ffd77a")
        if hx % 2:
            cv.px(hx + 4, hy - 3, "#ffd77a")
    cv.rect(200, 124, 203, 141, "#55406e")              # campanario
    cv.rect(199, 122, 204, 124, "#43325a")
    cv.px(201, 120, "#43325a"); cv.px(201, 121, "#43325a")
    cv.px(201, 128, "#ffd77a")
    for x in range(W):
        y3 = int(153 + 3 * math.sin(x * .05) + 2 * math.sin(x * .13 + 1))
        cv.rect(x, y3, x + 1, 172, "#4a3a5e")
    for tx in range(4, 320, 9):                          # siluetas de árboles
        base = int(153 + 3 * math.sin(tx * .05) + 2 * math.sin(tx * .13 + 1)) + 1
        if (tx * 13) % 5 < 2:
            h = 9 + (tx * 7) % 5
            for i in range(h):
                hw = (i * 3) // h + (1 if i > h // 2 else 0)
                cv.rect(tx - hw, base - h + i, tx + hw + 1, base - h + i + 1, "#3b2d4c")
            cv.px(tx - 1, base - h + 3, "#c0708a")
        else:
            rr = 4 + (tx * 3) % 3
            cv.circle(tx, base - rr, rr, "#3e2f50")
            cv.circle(tx - 1.5, base - rr - 1.5, rr - 2.5, "#7a4a5e")

    for args in TREES:
        autumn_tree(cv, *args, rnd)

    # ---- Césped con florecitas
    cv.rect(0, 160, W, 173, "#4c6a47")
    for x in range(W):
        cv.px(x, 160 - (1 if (x * 7) % 5 == 0 else 0), "#6f8f5a")
        if (x * 11) % 7 == 0:
            cv.px(x, 161, "#83a463")
    for _ in range(70):
        x, y = rnd.randrange(0, 318), rnd.randrange(162, 172)
        cv.px(x, y, rnd.choice(["#ffd0e0", "#fff3a0", "#ffffff", "#f6a2a2"]))
    for bx in [60, 118, 196, 270]:                       # arbustos
        cv.circle(bx, 166, 7, "#3c5a3c", ymax=172)
        cv.circle(bx - 1, 164.5, 5, "#56804c", ymax=172)
        cv.circle(bx - 2, 163, 2.5, "#79a35e")

    # ---- Valla de madera
    for x in range(0, 318, 18):
        cv.rect(x + 1, 148, x + 4, 172, "#6e452e")
        cv.rect(x + 1, 148, x + 2, 172, "#a06a44")
        cv.rect(x, 146, x + 5, 148, "#5a3826")
        cv.px(x + 2, 146, "#c08a5a")
    for ry in (153, 160):
        cv.rect(0, ry, 318, ry + 3, "#8a5a3a")
        cv.rect(0, ry, 318, ry + 1, "#c08a5a")
        cv.rect(0, ry + 3, 318, ry + 4, "#4d2f20")
        for x in range(5, 318, 18):
            cv.px(x, ry + 1, "#4d2f20")

    # ---- Patio
    for y in range(172, H):
        t = (y - 172) / (H - 172)
        cv.a[y] = C("#4c4552") * (1 - t) + C("#2f2a37") * t
    for _ in range(2200):
        x, y = rnd.randrange(W), rnd.randrange(174, H)
        cv.blend_px(x, y, "#5c5462" if rnd.random() < .55 else "#25212c", .7)
    cv.rect(0, 172, W, 174, "#a99e94")
    cv.rect(0, 174, W, 175, "#6d635f")
    for cx0, cy0 in [(60, 214), (210, 262), (380, 246)]:  # grietas
        x, y = cx0, cy0
        for _ in range(14):
            cv.px(x, y, "#221e29")
            x += rnd.choice([1, 1, 2]); y += rnd.choice([-1, 0, 0, 1])
    for x in range(-6, W, 22):
        cv.rect(x, 253, x + 12, 255, "#e3d8bd")
        cv.rect(x, 255, x + 12, 256, "#8f8678")
    for x in (334, 388, 438):
        for y in range(200, 232):
            cv.px(x + (y - 200) // 8, y, "#d9a940")
    for _ in range(150):                                  # hojas caídas
        x, y = rnd.randrange(W), rnd.randrange(176, H)
        c = rnd.choice(["#e57f35", "#f6b04a", "#c9522e", "#b8452a", "#e8a23c"])
        cv.px(x, y, c); cv.px(x + 1, y, c); cv.px(x + rnd.choice([0, 1]), y + 1, "#6a2e22")

    # ---- Farolas antiguas
    for lx in (34, 252):
        cv.rect(lx, 112, lx + 2, 172, "#2b2836")
        cv.rect(lx - 2, 166, lx + 4, 172, "#2b2836")
        cv.rect(lx - 1, 140, lx + 3, 142, "#2b2836")
        cv.rect(lx - 3, 102, lx + 5, 104, "#2b2836")
        cv.rect(lx - 2, 104, lx + 4, 112, "#ffe7a0")
        cv.rect(lx, 104, lx + 2, 112, "#fff6d2")
        cv.rect(lx - 2, 104, lx - 1, 112, "#2b2836"); cv.rect(lx + 3, 104, lx + 4, 112, "#2b2836")
        cv.rect(lx - 3, 112, lx + 5, 114, "#2b2836")
        cv.rect(lx - 1, 99, lx + 3, 102, "#2b2836"); cv.px(lx + 1, 98, "#2b2836")
        cv.glow(lx + 1, 108, 30, "#ffcf7a", .45)
        cv.ellipse(lx + 1, 178, 30, 5, "#ffd98a", .16)

    draw_warehouse(cv, rnd)

    # Viñeta cálida (se aplica al final de cada fotograma)
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * .45) / (H * .62)) ** 2)
    vign = 1 - .32 * np.clip(d - .55, 0, 1) ** 1.4
    return cv, vign[..., None]


def draw_warehouse(cv, rnd):
    # Tejado a cuatro aguas con tejas
    for y in range(64, 100):
        t = (y - 64) / 36
        x0, x1 = int(346 - 32 * t), int(442 + 32 * t)
        cv.rect(x0, y, x1, y + 1, "#4b4a63")
        row = (y - 64) // 4
        if (y - 64) % 4 == 3:
            cv.rect(x0, y, x1, y + 1, "#34334a")
        elif (y - 64) % 4 == 0:
            cv.rect(x0, y, x1, y + 1, "#6d6884")
            for x in range(x0 + (row % 2) * 3, x1, 6):
                cv.px(x, y + 1, "#34334a"); cv.px(x, y + 2, "#34334a")
        cv.px(x0, y, "#8a6e7e"); cv.px(x0 + 1, y, "#8a6e7e")   # luz poniente en la arista
        k = (.16 * np.clip(1 - (np.arange(x0, x1) - x0) / (x1 - x0) * 1.4, 0, 1))[:, None]
        cv.a[y, x0:x1] = cv.a[y, x0:x1] * (1 - k) + C("#ffb27a") * k   # luz cálida en degradado
    cv.rect(344, 62, 444, 65, "#7a7694")
    cv.rect(344, 62, 444, 63, "#a89cb4")
    # Cúpula con veleta
    cv.rect(386, 50, 402, 63, "#efe2c6")
    cv.rect(386, 50, 388, 63, "#c9b99a")
    for y in range(53, 61, 2):
        cv.rect(389, y, 400, y + 1, "#7a6a5a")
    for i in range(6):
        cv.rect(384 + i, 44 + i, 404 - i, 45 + i, "#3f3e57" if i % 2 else "#55536f")
    cv.rect(393, 30, 394, 44, "#2b2836")
    cv.rect(388, 35, 400, 36, "#2b2836")
    cv.sprite(390, 30, ["..##..", ".###..", "#####.", "..##.#"], {"#": "#2b2836"})
    cv.px(399, 34, "#2b2836"); cv.px(399, 36, "#2b2836"); cv.px(400, 35, "#2b2836")
    # Chimenea de ladrillo
    cv.rect(446, 52, 458, 80, "#9c4433")
    for y in range(54, 80, 3):
        cv.rect(446, y, 458, y + 1, "#6e2f24")
        for x in range(446 + (y // 3 % 2) * 3, 458, 6):
            cv.px(x, y + 1, "#6e2f24"); cv.px(x, y + 2, "#6e2f24")
    cv.rect(444, 49, 460, 52, "#5a5468")
    cv.rect(446, 52, 447, 80, "#c46a4a")

    # Fachada de ladrillo
    tones = ["#a4493a", "#b0523f", "#99412f", "#b85d46", "#8f3d2e", "#a9503c"]
    cv.rect(WALL_X0, 100, WALL_X1, 176, "#7e655a")
    for r, y in enumerate(range(101, 176, 3)):
        off = (r % 2) * 3
        for x in range(WALL_X0 - off, WALL_X1, 7):
            cv.rect(x, y, x + 6, y + 2, rnd.choice(tones))
            cv.px(x, y, "#c4705a")
    cv.rect(WALL_X0, 176, WALL_X1, 180, "#8b8580")       # zócalo de piedra
    cv.rect(WALL_X0, 176, WALL_X1, 177, "#b5aea6")
    for i, y in enumerate(range(101, 176, 6)):           # esquinas de piedra
        for qx, w in ((WALL_X0, 5 if i % 2 else 3), (WALL_X1 - (5 if i % 2 else 3), 5 if i % 2 else 3)):
            cv.rect(qx, y, qx + w, y + 5, "#d8cbb4")
            cv.rect(qx, y + 5, qx + w, y + 6, "#8a7d6a")
    for k in range(12):                                   # sombra del alero
        cv.blend_rect(WALL_X0, 101 + k, WALL_X1, 102 + k, "#1d1626", .45 * (1 - k / 12))
    cv.rect(314, 98, 474, 101, "#efe2c6")                 # alero
    cv.rect(314, 101, 474, 102, "#9a8a72")

    # Hiedra con algunas hojas rojas
    for _ in range(260):
        x = WALL_X0 + 1 + int(abs(rnd.gauss(0, 5)))
        y = rnd.randrange(112, 178)
        if rnd.random() < .5 or y > 140:
            cv.px(x, y, rnd.choice(["#3f7a3a", "#5a9a48", "#2f5a2e", "#3f7a3a", "#b84a32"]))

    # Rótulo de madera
    label = "ALMACÉN"
    tw = text_w(label, F5, 2)
    sx0 = (WALL_X0 + WALL_X1) // 2 - tw // 2 - 6
    sx1 = sx0 + tw + 12
    cv.rect(sx0 - 2, 105, sx1 + 2, 132, "#5a3826")
    cv.rect(sx0 - 2, 105, sx1 + 2, 106, "#9a6a44")
    cv.rect(sx0, 107, sx1, 130, "#2f4f3f")
    for y in (113, 119, 125):
        cv.rect(sx0, y, sx1, y + 1, "#284435")
    for nx, ny in [(sx0 + 1, 108), (sx1 - 2, 108), (sx0 + 1, 128), (sx1 - 2, 128)]:
        cv.px(nx, ny, "#c9b48a")
    cv.text(sx0 + 7, 116, label, "#1a2c23", F5, 2)
    cv.text(sx0 + 6, 115, label, "#f3e6c4", F5, 2)

    # Ventanas con cortinas y jardineras
    for wx in (324, 444):
        x0, x1, y0, y1 = wx, wx + 20, 108, 128
        cv.glow((x0 + x1) / 2, 118, 34, "#ffb35a", .22)
        cv.rect(x0 - 1, y0 + 3, x1 + 1, y1 + 1, "#efe2c6")
        cv.circle((x0 + x1) / 2, y0 + 5, 11, "#efe2c6", ymax=y0 + 5)
        cv.rect(x0 + 1, y0 + 4, x1 - 1, y1 - 1, "#ffcf73")
        cv.circle((x0 + x1) / 2, y0 + 5, 9, "#ffe2a0", ymax=y0 + 5)
        cv.rect(x0 + 1, y0 + 4, x1 - 1, y0 + 8, "#ffe2a0")
        cv.rect((x0 + x1) // 2, y0 - 3, (x0 + x1) // 2 + 1, y1 - 1, "#efe2c6")
        cv.rect(x0 + 1, y0 + 12, x1 - 1, y0 + 13, "#efe2c6")
        for cx, d in ((x0 + 1, 1), (x1 - 2, -1)):          # cortinas recogidas
            for y in range(y0 + 2, y1 - 1):
                w = 3 if abs(y - (y0 + 13)) > 2 else 1
                for k in range(w):
                    cv.px(cx + d * k, y, "#c0504a" if k < 2 else "#8e3430")
        cv.rect(x0 + 8, y1 - 5, x0 + 12, y1 - 1, "#b0603a")  # macetita en el alféizar
        cv.px(x0 + 9, y1 - 7, "#5a9a48"); cv.px(x0 + 10, y1 - 8, "#5a9a48"); cv.px(x0 + 11, y1 - 6, "#5a9a48")
        cv.rect(x0 - 2, y1 + 1, x1 + 2, y1 + 5, "#7a4a2e")    # jardinera
        cv.rect(x0 - 2, y1 + 1, x1 + 2, y1 + 2, "#a06a44")
        for i in range(x0 - 2, x1 + 2):
            cv.px(i, y1, "#4f8a44" if i % 2 else "#3a6a36")
            if i % 3 == 0:
                cv.px(i, y1 - 1, ["#ff8fb1", "#fff3a0", "#ffffff", "#ff6a5a"][i % 4])

    # Toldos de rayas
    for d0, d1 in (D1, D2):
        for x in range(d0 - 3, d1 + 3):
            col = "#f2e6cc" if ((x - d0) // 4) % 2 == 0 else "#3a8f88"
            cv.rect(x, 131, x + 1, 137, col)
            if (x - d0) % 4 in (1, 2):
                cv.px(x, 137, col)
        cv.rect(d0 - 3, 131, d1 + 3, 132, "#1f5a56")
        cv.blend_rect(d0 - 2, 138, d1 + 2, 142, "#1d1626", .35)

    # Raíl de las puertas correderas
    cv.rect(WALL_X0 + 2, 137, 440, 139, "#2b2836")
    for x in range(WALL_X0 + 6, 440, 12):
        cv.px(x, 137, "#6a6478")
    draw_door(cv, D2, 0.0, interior_light=0)

    # Puerta de la oficina, cartel "ABIERTO", farol, macetas
    ax0, ax1 = 445, 459
    cv.rect(ax0 - 2, 146, ax1 + 2, 180, "#efe2c6")
    cv.rect(ax0, 148, ax1, 180, "#7a4a2e")
    for x in range(ax0 + 3, ax1, 4):
        cv.rect(x, 148, x + 1, 180, "#5e3822")
    cv.rect(ax0 + 3, 151, ax1 - 3, 160, "#ffcf73")
    cv.rect(ax0 + 3, 155, ax1 - 3, 156, "#7a4a2e")
    cv.rect(ax0 + 7, 151, ax0 + 8, 160, "#7a4a2e")
    cv.px(ax1 - 3, 166, "#f6d37a")
    cv.rect(ax0 - 1, 180, ax1 + 1, 181, "#b5653a")
    sw = text_w("ABIERTO", F3)
    cv.rect(452 - sw // 2 - 2, 138, 452 + sw // 2 + 3, 145, "#f3e6c4")
    cv.rect(452 - sw // 2 - 2, 145, 452 + sw // 2 + 3, 146, "#9a8a72")
    cv.text(452 - sw // 2, 139, "ABIERTO", "#b23a32", F3)
    cv.glow(452, 156, 22, "#ffb35a", .18)
    for px_ in (437, 461):                                 # macetas
        cv.rect(px_, 173, px_ + 6, 180, "#c46a3a")
        cv.rect(px_ - 1, 172, px_ + 7, 174, "#d98a52")
        cv.rect(px_ + 4, 174, px_ + 5, 180, "#9a4a2a")
        cv.circle(px_ + 3, 168, 4.5, "#3f7a3a")
        cv.circle(px_ + 2, 167, 3, "#5a9a48")
        for fx, fy in ((px_ + 1, 166), (px_ + 4, 165), (px_ + 3, 169), (px_ + 6, 167)):
            cv.px(fx, fy, "#ff8fb1" if px_ < 450 else "#fff3a0")
    # Farol de pared
    cv.rect(429, 143, 433, 145, "#2b2836")
    cv.rect(428, 145, 434, 153, "#ffe7a0")
    cv.rect(430, 145, 432, 153, "#fff6d2")
    cv.rect(428, 145, 429, 153, "#2b2836"); cv.rect(433, 145, 434, 153, "#2b2836")
    cv.rect(427, 153, 435, 155, "#2b2836")
    cv.glow(431, 149, 30, "#ffcf7a", .42)

    # Muelle de hormigón con bandas de seguridad
    cv.rect(316, DOCK_Y, 470, 198, "#9d948a")
    cv.rect(316, DOCK_Y, 470, 182, "#d2c8b6")
    cv.rect(316, 196, 470, 198, "#6e6760")
    for x in range(330, 470, 26):
        cv.rect(x, 183, x + 1, 196, "#857c73")
    for _ in range(60):
        cv.blend_px(rnd.randrange(316, 470), rnd.randrange(183, 196), "#6e6760", .5)
    for d0, d1 in (D1, D2):
        for x in range(d0, d1):
            for y in range(183, 186):
                cv.px(x, y, "#f0c030" if ((x + y) // 3) % 2 else "#2b2836")
        for bx in (d0 - 4, d1):
            cv.rect(bx, 185, bx + 4, 195, "#1f1d24")
            cv.rect(bx, 185, bx + 4, 186, "#45414d")
    for k in range(5):
        cv.blend_rect(312, 198 + k, 472, 199 + k, "#120e18", .45 * (1 - k / 5))
    # Escalera lateral con barandilla
    for i, (sy, sx) in enumerate([(180, 470), (186, 473), (192, 476)]):
        cv.rect(sx - 3, sy, W, sy + 6, "#b0a698")
        cv.rect(sx - 3, sy, W, sy + 1, "#d8cfbf")
    cv.line(470, 166, 479, 186, "#2b2836")
    cv.rect(470, 166, 471, 180, "#2b2836")



def draw_crates(cv):
    """Palé con cajas y saco (delante de la puerta corredera)."""
    def crate(x, y, w, h, tape=True):
        cv.rect(x, y, x + w, y + h, "#c99a5c")
        cv.rect(x, y, x + w, y + 1, "#e8bd80")
        cv.rect(x + w - 1, y, x + w, y + h, "#9a7040")
        if tape:
            cv.rect(x + w // 2, y, x + w // 2 + 1, y + 3, "#efe2c6")
        cv.px(x + 2, y + h - 2, "#7a5432")
    cv.rect(321, 177, 336, 180, "#8a6a42")
    cv.rect(321, 177, 336, 178, "#b08a58")
    for x in (322, 328, 334):
        cv.px(x, 179, "#3e2c1c")
    crate(321, 167, 8, 10); crate(329, 169, 7, 8); crate(323, 159, 9, 8)
    cv.circle(332, 165, 3.5, "#d8c49a", ymax=169)
    cv.px(332, 162, "#a08a62")


def draw_door(cv, door, f, interior_light=1.0):
    """Puerta corredera doble estilo granero; f = 0 cerrada, 1 abierta."""
    d0, d1 = door
    h0, h1 = DOOR_TOP, DOCK_Y
    # Interior: estanterías, cajas, bombilla
    cv.rect(d0, h0, d1, h1, "#4a3022")
    for x in range(d0, d1, 5):
        cv.rect(x, h0, x + 1, h1, "#3e271c")
    for sy in (h0 + 12, h0 + 26):
        cv.rect(d0, sy, d1, sy + 2, "#7a5038")
        for i, bx in enumerate(range(d0 + 2, d1 - 6, 7)):
            bh = 5 + (bx + sy) % 4
            cv.rect(bx, sy - bh, bx + 6, sy, ["#c99a5c", "#b5884e", "#d8b07a"][i % 3])
            cv.rect(bx, sy - bh, bx + 6, sy - bh + 1, "#ecc890")
    cv.rect(d0, h1 - 4, d1, h1, "#8a6a4a")
    cv.rect(d0 + 4, h1 - 12, d0 + 14, h1 - 4, "#c99a5c")
    cv.rect(d0 + 4, h1 - 12, d0 + 14, h1 - 11, "#ecc890")
    mx = (d0 + d1) // 2
    cv.rect(mx, h0, mx + 1, h0 + 5, "#2b2836")
    cv.rect(mx - 1, h0 + 5, mx + 2, h0 + 7, "#fff3c0")
    if interior_light > 0:
        cv.glow(mx, h0 + 6, 26, "#ffb35a", .55 * interior_light, clip=(d0, h0, d1, h1))

    # Hojas correderas
    half = (d1 - d0) // 2
    shift = int(round(half * f))
    for hx0, sgn in ((d0, -1), (d0 + half, 1)):
        x0 = hx0 + sgn * shift
        x1 = x0 + half
        cv.rect(x0, h0, x1, h1, "#3f6b4a")
        for x in range(x0 + 3, x1, 4):
            cv.rect(x, h0, x + 1, h1, "#2f5238")
        cv.rect(x0, h0, x0 + 1, h1, "#5f8f64")
        cv.rect(x0, h0, x1, h0 + 2, "#efe2c6")                # marco blanco
        cv.rect(x0, h1 - 2, x1, h1, "#efe2c6")
        cv.rect(x0, h0, x0 + 2, h1, "#efe2c6")
        cv.rect(x1 - 2, h0, x1, h1, "#efe2c6")
        cv.rect(x0, (h0 + h1) // 2, x1, (h0 + h1) // 2 + 2, "#efe2c6")
        for (ya, yb) in ((h0 + 2, (h0 + h1) // 2), ((h0 + h1) // 2 + 2, h1 - 2)):
            cv.line(x0 + 2, yb - 1, x1 - 3, ya, "#efe2c6")    # cruz de granero
            cv.line(x0 + 2, ya, x1 - 3, yb - 1, "#d8cbb0")
        cv.rect(x0 + 2, h0 - 3, x0 + 4, h0, "#2b2836")       # ruedas del raíl
        cv.rect(x1 - 4, h0 - 3, x1 - 2, h0, "#2b2836")
        hx = x1 - 4 if sgn < 0 else x0 + 3
        cv.rect(hx, (h0 + h1) // 2 - 4, hx + 1, (h0 + h1) // 2 + 6, "#2b2836")


# =================================================================== personajes
WORKER = [
    "...kkkk...",
    "..kYYYYk..",
    ".kYYYYYyk.",
    "kyyyyyyyyk",
    ".kHSSSSHk.",
    ".kSESSESk.",
    ".kSSSSSSk.",
    "..ksMMsk..",
    "...kSSk...",
    ".kVVRRVVk.",
    "kBVVRRVVBk",
    "kBVVVVVVBk",
    "kBRRRRRRBk",
    "kSVVVVVVSk",
    ".kJJJJJJk.",
    ".kJJjjJJk.",
    ".kJJ..JJk.",
    ".kJJ..JJk.",
    ".kKK..KKk.",
    "kKKK..KKKk",
]
WPAL = {"k": "#1d1626", "Y": "#f5c242", "y": "#c99528", "S": "#f1c09a", "s": "#d39a74",
        "H": "#4a2e22", "E": "#1d1626", "M": "#c0645a", "V": "#f07a2a", "R": "#f6f08a",
        "B": "#3d5a8a", "J": "#34497a", "j": "#263660", "K": "#3a2a22"}

CAT = [
    ".k...k..",
    "kOk.kOk.",
    "kOOkOOk.",
    "kOEOEOk.",
    "kOOPOOk.",
    ".kOOOk..",
    ".kOLLOk.",
    "kOOLLOOk",
    "kODOODOk",
    ".kk..kk.",
]
CPAL = {"k": "#2a1a18", "O": "#e08a3a", "D": "#b0602a", "L": "#f6d0a0", "E": "#8fd06a",
        "P": "#ff9aa8"}


def draw_worker(cv, x, y, f, waving):
    cv.sprite(x, y - 20, WORKER, WPAL)
    # Portapapeles en la mano derecha
    cv.rect(x + 9, y - 9, x + 13, y - 3, "#1d1626")
    cv.rect(x + 10, y - 8, x + 12, y - 4, "#f4efe2")
    cv.px(x + 10, y - 7, "#7a7a8a"); cv.px(x + 10, y - 5, "#7a7a8a")
    if waving:
        up = (f // 3) % 2 == 0
        if up:
            cv.rect(x - 2, y - 17, x, y - 10, "#3d5a8a"); cv.rect(x - 2, y - 19, x, y - 17, "#f1c09a")
            cv.px(x - 3, y - 17, "#1d1626")
        else:
            cv.line(x - 1, y - 10, x - 5, y - 15, "#3d5a8a"); cv.line(x - 2, y - 10, x - 6, y - 15, "#3d5a8a")
            cv.rect(x - 7, y - 17, x - 5, y - 15, "#f1c09a")


def draw_cat(cv, x, y, f):
    cv.sprite(x, y - 10, CAT, CPAL)
    ph = math.sin(f * .25)
    tail = [(8, 7), (9, 6), (10, 5 + round(ph)), (10 + round(ph), 4 + round(ph)),
            (10 + round(ph * 1.5), 3)]
    for tx, ty in tail:
        cv.px(x + tx, y - 10 + ty, "#e08a3a")
        cv.px(x + tx, y - 9 + ty, "#2a1a18")
    if (f // 20) % 6 == 5:                                      # parpadeo
        cv.px(x + 2, y - 7, "#2a1a18"); cv.px(x + 4, y - 7, "#2a1a18")


# =================================================================== camión
TEAL, TEAL_HI, TEAL_LO, TEAL_DK = "#2f8f8a", "#5fc2b4", "#1f6566", "#163f45"
CREAM, CREAM_SH, CREAM_LO, CREAM_HI = "#f3e8cf", "#d9caa9", "#b8a785", "#fff8e8"
ORANGE = "#ec8a3c"
CHROME, CHROME_HI, CHROME_LO, CHROME_DK = "#c7ccd8", "#f5f7fb", "#7f8799", "#4f5566"
RIM_LIGHT = "#ffd7a8"
GROUND, WR = 236, 9
WY = GROUND - WR


def draw_wheel(cv, cx, cy, ang):
    res = cv._disk(cx, cy, WR)
    if res is None:
        return
    sl, d, yy, xx = res
    r = np.sqrt(d) * WR
    th = np.arctan2(yy + .5 - cy, xx + .5 - cx) - ang
    img = cv.a[sl]
    msk = cv.m[sl]
    tire = r <= WR
    img[tire] = C("#1d1b22"); msk[tire] = True
    tread = tire & (r > WR - 1.6) & ((np.floor(th * 10 / math.pi) % 2) == 0)
    img[tread] = C("#2e2b35")
    side = tire & (r > 5.6) & (r < WR - 1.6) & (yy + .5 < cy) & (xx + .5 < cx + 2)
    img[side] = C("#383542")
    rim = r <= 5.6
    img[rim] = C("#c9ccd6")
    img[rim & (xx + yy + 1 > cx + cy + 1)] = C("#9298a8")
    img[r <= 2.4] = C(CHROME_HI)
    img[(r > 5.0) & rim] = C("#7f8799")
    frac = (th * 8 / (2 * math.pi)) % 1
    lug = (r > 3.0) & (r < 4.6) & (np.minimum(frac, 1 - frac) < .14)
    img[lug] = C(CHROME_DK)
    cv.px(cx - .5, cy - .5, "#4f5566")


def draw_truck(spr, x0, dist, braking, waving, f):
    x0 = int(round(x0))
    cv = spr

    # ---------------- remolque
    tx0, tx1, ty0, ty1 = x0, x0 + 188, 158, 210
    cv.rect(tx0, ty0, tx1, ty1, CREAM)
    cv.rect(tx0, ty0, tx1, ty0 + 3, "#a89a80")
    cv.rect(tx0, ty0, tx1, ty0 + 1, RIM_LIGHT)
    for x in range(tx0 + 2, tx1, 4):
        cv.px(x, ty0 + 2, "#7f735e")
    cv.rect(tx0, ty1 - 5, tx1, ty1, "#9c8f76")
    for x in range(tx0 + 2, tx1 - 2, 8):                      # cinta reflectante
        cv.rect(x, ty1 - 3, x + 4, ty1 - 1, "#e04a3a")
        cv.rect(x + 4, ty1 - 3, x + 8, ty1 - 1, "#f6f1e6")
    for x in range(tx0 + 14, tx1 - 4, 16):                    # costillas
        cv.rect(x, ty0 + 3, x + 1, ty1 - 5, CREAM_SH)
        cv.rect(x + 1, ty0 + 3, x + 2, ty1 - 5, CREAM_HI)
    for k in range(8):
        cv.blend_rect(tx0, ty1 - 13 + k, tx1, ty1 - 12 + k, CREAM_LO, .04 * k)
    cv.rect(tx0, ty0, tx0 + 4, ty1, CREAM_LO)                 # puertas traseras
    cv.rect(tx0 + 1, ty0 + 6, tx0 + 2, ty1 - 6, CHROME)
    for hy in (ty0 + 8, ty0 + 24, ty0 + 40):
        cv.rect(tx0 + 3, hy, tx0 + 5, hy + 2, CHROME_DK)
    cv.rect(tx0, 188, tx0 + 2, 191, "#ffb24a")
    tail = "#ff3a30" if braking else "#a8221f"
    cv.rect(tx0, 194, tx0 + 2, 200, tail)
    cv.rect(tx1 - 2, ty0 + 3, tx1, ty1 - 5, CREAM_SH)
    for x in range(tx0 + 8, tx1 - 4, 30):
        cv.px(x, ty0 + 1, "#ffb24a")

    # Logotipo: insignia con caja y corazón + "CARGA EXPRESS"
    bx, by = tx0 + 64, 179
    cv.circle(bx, by, 11, CREAM_LO)
    cv.circle(bx, by, 10, TEAL)
    cv.circle(bx - 1, by - 1, 8.5, "#3aa098")
    cv.rect(bx - 5, by - 2, bx + 5, by + 5, CREAM)
    cv.rect(bx - 5, by - 2, bx + 5, by - 1, CREAM_HI)
    cv.rect(bx - 1, by - 2, bx + 1, by + 5, ORANGE)
    cv.rect(bx + 4, by - 1, bx + 5, by + 5, CREAM_SH)
    cv.sprite(bx - 3, by - 8, [".#.#.", "#####", ".###.", "..#.."], {"#": "#ff6a5a"})
    tx = bx + 16
    cv.text(tx + 1, 168, "CARGA", TEAL_DK, F5, 2)
    cv.text(tx, 167, "CARGA", TEAL, F5, 2)
    cv.text(tx + 1, 184, "EXPRESS", ORANGE, F5, 1, 2)
    for i, ly in enumerate((176, 180, 184)):                  # líneas de velocidad
        cv.rect(bx - 28 + i * 3, ly, bx - 15, ly + 1, ORANGE)
    cv.rect(tx0 + 5, 196, tx1 - 1, 200, TEAL)
    cv.rect(tx0 + 5, 196, tx1 - 1, 197, TEAL_HI)
    cv.rect(tx0 + 5, 201, tx1 - 1, 202, ORANGE)

    # Bajos del remolque
    cv.rect(tx0 + 4, ty1, tx1 - 2, ty1 + 3, "#2a2630")
    cv.rect(tx0 + 16, ty1 + 3, tx0 + 62, ty1 + 6, "#33303a")
    for x in range(tx0 + 20, tx1 - 10, 40):
        cv.px(x, ty1 + 1, "#ffb24a")
    cv.rect(tx0 + 2, ty1 + 3, tx0 + 6, ty1 + 12, "#3a3640")   # parachoques trasero
    cv.rect(tx0, ty1 + 10, tx0 + 12, ty1 + 13, "#3a3640")
    for x in range(tx0, tx0 + 12, 4):
        cv.rect(x, ty1 + 10, x + 2, ty1 + 11, "#e04a3a")
    cv.rect(tx0 + 150, ty1 + 3, tx0 + 152, GROUND - 5, CHROME_LO)  # patas de apoyo
    cv.rect(tx0 + 155, ty1 + 3, tx0 + 157, GROUND - 5, CHROME_DK)
    cv.rect(tx0 + 148, GROUND - 5, tx0 + 159, GROUND - 3, "#3a3640")
    cv.rect(tx0 + 148, ty1 + 9, tx0 + 159, ty1 + 10, CHROME_DK)
    cv.rect(tx0 + 158, ty1 + 5, tx0 + 162, ty1 + 6, CHROME_DK)
    cv.rect(tx0 + 9, ty1 + 3, tx0 + 13, GROUND - 2, "#141218")  # faldilla
    cv.rect(tx0 + 10, ty1 + 14, tx0 + 12, ty1 + 16, CHROME)

    # ---------------- mangueras
    for i, col in enumerate(("#d23a3a", "#3a6ad2", "#f0c030")):
        for x in range(tx1, x0 + 199):
            sag = int(2 * math.sin(math.pi * (x - tx1) / (x0 + 199 - tx1)))
            cv.px(x, 182 + i * 3 + sag, col)

    # ---------------- tractora
    cv.rect(x0 + 156, 210, x0 + 278, 215, "#2a2630")           # chasis
    cv.rect(x0 + 164, 207, x0 + 198, 211, "#1f1d24")           # quinta rueda
    cv.rect(x0 + 164, 207, x0 + 198, 208, "#4a4652")
    cv.rect(x0 + 156, 214, x0 + 159, GROUND - 2, "#141218")    # faldilla

    rows = []
    for y in range(158, 213):
        if y < 174:
            xe = x0 + 214 + int((y - 158) * 24 / 16)
        else:
            xe = x0 + 248
        rows.append((y, x0 + 198, xe))
    cv.spans(rows, TEAL)
    for y, xa, xe in rows:                                     # luz en el contorno superior
        if y < 175:
            cv.px(xe - 1, y, TEAL_HI)
    cv.rect(x0 + 198, 158, x0 + 214, 159, RIM_LIGHT)
    cv.rect(x0 + 198, 159, x0 + 214, 160, TEAL_HI)
    cv.rect(x0 + 198, 158, x0 + 200, 213, TEAL_LO)
    cv.rect(x0 + 200, 160, x0 + 201, 208, TEAL_HI)
    cv.rect(x0 + 198, 209, x0 + 248, 213, TEAL_LO)
    # Ventanita del dormitorio con cortina y luz cálida
    cv.rect(x0 + 205, 182, x0 + 216, 191, TEAL_DK)
    cv.rect(x0 + 206, 183, x0 + 215, 190, "#ffcf73")
    cv.rect(x0 + 206, 183, x0 + 209, 190, "#e0703a")
    cv.rect(x0 + 212, 183, x0 + 215, 190, "#e0703a")
    cv.rect(x0 + 206, 183, x0 + 215, 184, "#c0504a")
    # Puerta
    cv.rect(x0 + 225, 177, x0 + 226, 212, TEAL_DK)
    cv.rect(x0 + 225, 211, x0 + 248, 212, TEAL_DK)
    cv.rect(x0 + 240, 203, x0 + 244, 204, CHROME)
    # Ventanilla con conductor
    gx0, gx1, gy0, gy1 = x0 + 229, x0 + 246, 180, 195
    cv.rect(gx0 - 1, gy0 - 1, gx1 + 1, gy1 + 1, TEAL_DK)
    cv.rect(gx0, gy0, gx1, gy1, "#4f7fa8")
    cv.rect(gx0, gy0, gx1, gy0 + 3, "#6f9cc4")
    hx, hy = x0 + 236, 183                                     # conductor de perfil
    cv.sprite(hx, hy, [
        ".rrrrr...",
        "rrrrrrrr.",
        "HHSSSS...",
        "HSSSESS..",
        "HSSSSSSs.",
        ".SSSmS...",
        "..SSS....",
        "ppPPPPp..",
        "pPPpPPPp.",
        "PPpPPpPP.",
        "PPPPPPPP.",
        "pPPpPPpP.",
    ], {"r": "#c23a3a", "H": "#5a3a2a", "S": "#f1c09a", "s": "#d39a74", "E": "#1d1626",
        "m": "#a0524a", "P": "#c0504a", "p": "#7a2a2a"})
    for y in range(gy0, gy1):                                  # reflejo del atardecer
        for k in (0, 1):
            xr = gx0 + 2 + (y - gy0) + k
            if gx0 <= xr < gx1 and (y - gy0) < 9:
                cv.blend_px(xr, y, "#ffb98a", .55)
    cv.rect(x0 + 236, 174, x0 + 252, 176, "#1d2a30")           # visera
    for x in range(x0 + 238, x0 + 248, 2):
        cv.px(x, 173, "#ffb030")
    if waving:                                                 # brazo saludando
        up = (f // 3) % 2 == 0
        cv.rect(gx1 - 3, gy1 - 2, gx1 + 2, gy1, "#c0504a")
        if up:
            cv.rect(gx1 + 1, gy0 + 2, gx1 + 3, gy1 - 1, "#c0504a")
            cv.rect(gx1 + 1, gy0 - 1, gx1 + 4, gy0 + 2, "#f1c09a")
        else:
            cv.line(gx1 + 1, gy1 - 2, gx1 + 5, gy0 + 4, "#c0504a")
            cv.line(gx1 + 2, gy1 - 2, gx1 + 6, gy0 + 4, "#c0504a")
            cv.rect(gx1 + 5, gy0 + 1, gx1 + 8, gy0 + 4, "#f1c09a")
    # Retrovisor
    cv.rect(x0 + 247, 184, x0 + 252, 185, CHROME_DK)
    cv.rect(x0 + 247, 193, x0 + 252, 194, CHROME_DK)
    cv.rect(x0 + 251, 181, x0 + 254, 197, "#1f1d24")
    cv.rect(x0 + 252, 182, x0 + 253, 196, "#6f9cc4")

    # Capó redondeado
    rows = []
    for y in range(188, 215):
        xe = x0 + 279
        if y < 193:
            xe = x0 + 279 - int((193 - y) ** 1.6)
        rows.append((y, x0 + 247, xe))
    cv.spans(rows, TEAL)
    for y, xa, xe in rows[:6]:
        cv.px(xe - 1, y, TEAL_HI)
    cv.rect(x0 + 247, 188, x0 + 270, 189, RIM_LIGHT)
    cv.rect(x0 + 247, 189, x0 + 272, 190, TEAL_HI)
    for vy in (192, 194):                                      # rejillas laterales
        cv.rect(x0 + 252, vy, x0 + 264, vy + 1, TEAL_DK)
    cv.rect(x0 + 247, 188, x0 + 248, 214, TEAL_LO)
    # Franja crema + línea naranja
    cv.rect(x0 + 198, 198, x0 + 279, 201, CREAM)
    cv.rect(x0 + 198, 198, x0 + 279, 199, CREAM_HI)
    cv.rect(x0 + 198, 202, x0 + 279, 203, ORANGE)
    # Paso de rueda delantero
    res = cv._disk(x0 + 260, WY, 12.5)
    if res is not None:
        sl, d, yy, xx = res
        rr = np.sqrt(d) * 12.5
        body = cv.m[sl]
        well = (rr <= 11.5) & body
        lip = (rr > 11.5) & (rr <= 12.5) & body & (yy < WY + 2)
        cv.a[sl][well] = C("#141218")
        cv.a[sl][lip] = C(TEAL_DK)
    # Calandra cromada, faro, parachoques
    cv.rect(x0 + 279, 190, x0 + 283, 212, CHROME)
    for x in range(x0 + 279, x0 + 283, 2):
        cv.rect(x, 192, x + 1, 210, CHROME_DK)
    cv.rect(x0 + 279, 190, x0 + 283, 191, CHROME_HI)
    cv.px(x0 + 281, 191, ORANGE)
    cv.rect(x0 + 273, 203, x0 + 279, 208, CHROME)
    cv.rect(x0 + 274, 204, x0 + 279, 207, "#fff6cc")
    cv.rect(x0 + 274, 209, x0 + 278, 211, "#ffb030")
    cv.rect(x0 + 268, 212, x0 + 287, 219, CHROME)
    cv.rect(x0 + 268, 212, x0 + 287, 213, CHROME_HI)
    cv.rect(x0 + 268, 217, x0 + 287, 219, CHROME_LO)
    # Depósito cromado y estribos
    for y, col in zip(range(212, 227), [CHROME_LO, CHROME, CHROME_HI, CHROME_HI, CHROME, CHROME, CHROME,
                                         CHROME, CHROME, CHROME, CHROME, CHROME_LO, CHROME_LO, CHROME_DK, CHROME_DK]):
        cv.rect(x0 + 204, y, x0 + 226, y + 1, col)
    for sx in (x0 + 208, x0 + 221):
        cv.rect(sx, 212, sx + 2, 227, "#2a2630")
    cv.rect(x0 + 228, 214, x0 + 246, 216, CHROME_DK)
    cv.rect(x0 + 230, 219, x0 + 246, 221, "#2a2630")
    # Escape vertical con protector perforado
    cv.rect(x0 + 217, 140, x0 + 221, 204, CHROME)
    cv.rect(x0 + 217, 140, x0 + 218, 204, CHROME_HI)
    cv.rect(x0 + 220, 140, x0 + 221, 204, CHROME_LO)
    for y in range(160, 192, 2):
        cv.px(x0 + 219, y, CHROME_DK)
    cv.rect(x0 + 216, 158, x0 + 222, 159, CHROME_DK)
    cv.rect(x0 + 216, 192, x0 + 222, 193, CHROME_DK)
    cv.rect(x0 + 218, 137, x0 + 223, 140, CHROME_LO)
    cv.rect(x0 + 221, 136, x0 + 224, 138, "#2a2630")

    # ---------------- ruedas
    ang = dist / WR
    for wx in (x0 + 28, x0 + 50, x0 + 170, x0 + 192, x0 + 260):
        draw_wheel(cv, wx, WY, ang)
    return x0


# =================================================================== animación
def ease_out(t):
    return 1 - (1 - t) ** 3


class Puddle:
    def __init__(self, cx, cy, rx, ry, axis, seed):
        r = random.Random(seed)
        self.pix = []
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx - 3, cx + rx + 4):
                dx, dy = (x - cx) / rx, (y - cy) / ry
                wob = .18 * math.sin(x * .5 + seed) + r.uniform(-.06, .06)
                if dx * dx + dy * dy <= 1 + wob and 0 <= x < W and 0 <= y < H:
                    self.pix.append((x, y))
        self.top = {}
        for x, y in self.pix:
            self.top[x] = min(self.top.get(x, 999), y)
        self.axis = axis

    def apply(self, cv, src, f):
        for x, y in self.pix:
            sy = 2 * self.axis - y
            sx = x + int(round(math.sin(y * 1.3 + f * .35) * .7))
            if 0 <= sy < H and 0 <= sx < W:
                refl = src[sy, sx]
            else:
                refl = C("#4a3f6a")
            cv.a[y, x] = C("#6a5a94") * .38 + refl * .62 * .9
            if self.top[x] == y:
                cv.a[y, x] = C("#a898b8")
            elif (x + f // 2) % 9 == 0 and y == self.top[x] + 1:
                cv.a[y, x] = C("#c9b8d0")


def main():
    bg, vign = draw_background()
    rnd = random.Random(5)
    X_START, X_END = -300, 30
    DRIVE, TOTAL = 70, 132
    DOOR_A, DOOR_B = 84, 106
    puddles = [Puddle(70, 246, 24, 3, GROUND, 1), Puddle(205, 262, 32, 4, GROUND, 2),
               Puddle(318, 246, 18, 3, GROUND, 3), Puddle(420, 214, 26, 3, 198, 4),
               Puddle(128, 190, 16, 2, 173, 5)]

    smoke, chimney, leaves = [], [], []
    for _ in range(14):
        tx, ty, tr = rnd.choice(TREES)
        leaves.append([rnd.uniform(0, W), rnd.uniform(60, 250), rnd.uniform(0, 6.28),
                       rnd.choice(["#e57f35", "#f6b04a", "#c9522e", "#ffd27a"])])
    birds = [[40, 52, 0], [56, 46, 3], [70, 55, 5]]
    frames = []
    prev = X_START
    for f in range(TOTAL):
        t = min(1, f / DRIVE)
        x = X_START + (X_END - X_START) * ease_out(t)
        v = x - prev
        prev = x
        braking = DRIVE - 26 <= f <= DRIVE + 6
        stopped = f >= DRIVE
        door = min(1, max(0, (f - DOOR_A) / (DOOR_B - DOOR_A)))
        door = door * door * (3 - 2 * door)

        cv = bg.copy()
        # Pájaros
        for b in birds:
            b[0] += .6
            flap = (f // 4 + b[2]) % 2
            bx, by = int(b[0]), int(b[1] + math.sin(f * .1 + b[2]) * 1.5)
            if flap:
                cv.px(bx - 2, by - 1, "#2b2340"); cv.px(bx - 1, by, "#2b2340")
                cv.px(bx, by, "#2b2340"); cv.px(bx + 1, by, "#2b2340"); cv.px(bx + 2, by - 1, "#2b2340")
            else:
                cv.px(bx - 2, by + 1, "#2b2340"); cv.px(bx - 1, by, "#2b2340")
                cv.px(bx, by, "#2b2340"); cv.px(bx + 1, by, "#2b2340"); cv.px(bx + 2, by + 1, "#2b2340")
        # Humo de la chimenea
        if f % 5 == 0:
            chimney.append([452, 48, 0])
        for p in chimney:
            p[0] += .25 + p[2] * .01; p[1] -= .35; p[2] += 1
        chimney = [p for p in chimney if p[2] < 60]
        for cx, cy, age in chimney:
            r = 2 + age * .07
            cv.circle(cx, cy, r, "#d9cfe0", a=.45 * (1 - age / 60))

        # Puertas y luz interior
        draw_door(cv, D1, door, interior_light=.4 + .6 * door)
        if door > 0:
            rows = [(y, D1[0] - (y - DOCK_Y) // 2, D1[1] + (y - DOCK_Y) // 2) for y in range(DOCK_Y, 222)]
            for y, a_, b_ in rows:
                cv.blend_rect(a_, y, b_, y + 1, "#ffc37a", .16 * door * (1 - (y - DOCK_Y) / 42))

        # Guirnalda de bombillas bajo el alero
        cols = ["#ffcf6b", "#ff8a5c", "#9fe07a", "#7ab8ff", "#ff6b9a"]
        hooks = list(range(316, 474, 26))
        for h0, h1 in zip(hooks, hooks[1:]):
            for xx in range(h0, h1):
                yy = 102 + 3 * math.sin(math.pi * (xx - h0) / (h1 - h0))
                cv.px(xx, round(yy), "#2b2836")
            for i, xx in enumerate(range(h0 + 3, h1 - 1, 5)):
                yy = round(103 + 3 * math.sin(math.pi * (xx - h0) / (h1 - h0)))
                k = (xx // 5) % len(cols)
                tw = .55 + .45 * math.sin(f * .35 + xx * .7)
                cv.rect(xx, yy, xx + 2, yy + 2, cols[k])
                cv.glow(xx + 1, yy + 1, 6, cols[k], .35 * tw)

        draw_crates(cv)
        src = cv.a.copy()
        for p in puddles[3:]:                         # charcos del fondo (detrás del camión)
            p.apply(cv, src, f)

        draw_cat(cv, 420, DOCK_Y, f)
        draw_worker(cv, 400, DOCK_Y, f, waving=f >= DRIVE - 8)

        # Sombra + camión con contorno
        xi = int(round(x))
        for k, a in enumerate((.35, .3, .2, .1)):
            cv.blend_rect(xi - 2, GROUND - 1 + k, xi + 290, GROUND + k, "#100c16", a)
        spr = Canvas(track=True)
        draw_truck(spr, x, x - X_START, braking, stopped and f < DRIVE + 34, f)
        composite(cv, spr)

        # Humo del escape
        if f % 2 == 0:
            smoke.append([xi + 222, 134, rnd.uniform(-.15, .15), 0])
        for p in smoke:
            p[0] += v * .75 - .35 + p[2]; p[1] -= .55; p[3] += 1
        smoke = [p for p in smoke if p[3] < 16]
        for sx, sy, _, age in smoke:
            a = .5 * (1 - age / 16)
            cv.circle(sx, sy, 1.2 + age * .25, "#8c8897", a=a)
            cv.circle(sx - .5, sy - .5, .6 + age * .12, "#c9c3d4", a=a * .8)

        # Faro y pilotos
        hx = xi + 279
        cv.glow(hx, 205, 12, "#fff2c0", .8)
        for y in range(196, GROUND + 8):
            spread = (y - 205.5)
            for xx in range(hx + 2, min(hx + 90, W)):
                d = xx - hx
                if abs(spread) <= d * .28 + 1:
                    cv.a[y, xx] += C("#fff0b8") * .18 * (1 - d / 90) ** 1.5
        if braking:
            cv.glow(xi + 1, 197, 14, "#ff3a30", .6)
        else:
            cv.glow(xi + 1, 197, 6, "#ff3a30", .25)

        # Hojas que caen
        for L in leaves:
            L[0] += .55 + .5 * math.sin(f * .08 + L[2])
            L[1] += .45 + .2 * math.cos(f * .1 + L[2])
            if L[1] > H or L[0] > W:
                tx, ty, tr = rnd.choice(TREES)
                L[0], L[1] = tx + rnd.uniform(-tr, tr), ty + rnd.uniform(-tr / 2, tr / 2)
            flip = (f // 3 + int(L[2] * 3)) % 3
            lx, ly = int(L[0]), int(L[1])
            if flip == 0:
                cv.px(lx, ly, L[3]); cv.px(lx + 1, ly, L[3]); cv.px(lx + 1, ly + 1, "#8e3a2a")
            elif flip == 1:
                cv.px(lx, ly, L[3]); cv.px(lx, ly + 1, L[3]); cv.px(lx + 1, ly + 1, "#8e3a2a")
            else:
                cv.px(lx, ly, L[3]); cv.px(lx + 1, ly + 1, L[3])

        src = cv.a.copy()
        for p in puddles[:3]:                         # charcos delanteros: reflejan el camión
            p.apply(cv, src, f)

        out = np.clip(cv.a * vign, 0, 255).astype(np.uint8)
        frames.append(out)

    sample = Image.fromarray(np.concatenate(frames[::8] + [frames[-1]], axis=0))
    pal = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    gif = [Image.fromarray(fr).resize((W * 3, H * 3), Image.NEAREST)
           .quantize(palette=pal, dither=Image.Dither.NONE) for fr in frames]
    dur = [70] * TOTAL
    dur[-1] = 2200
    gif[0].save(os.path.join(OUT, "camion_almacen.gif"), save_all=True, append_images=gif[1:],
                duration=dur, loop=0, optimize=True, disposal=1)
    Image.fromarray(frames[-1]).resize((W * 4, H * 4), Image.NEAREST).save(
        os.path.join(OUT, "camion_almacen.png"))
    print("ok", TOTAL, "frames")


if __name__ == "__main__":
    main()
