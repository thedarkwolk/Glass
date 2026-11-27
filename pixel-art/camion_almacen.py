"""Pixel art: camión con remolque largo llegando a un almacén al atardecer.

Genera:
  camion_almacen.gif  (animación: llega, frena, se abre el muelle)
  camion_almacen.png  (fotograma final a 4x)

Uso: python3 camion_almacen.py
"""
import math
import os
import random

import numpy as np
from PIL import Image

W, H = 384, 216
OUT = os.path.dirname(os.path.abspath(__file__))


def C(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


# ---------------------------------------------------------------- primitivas
class Canvas:
    def __init__(self, img=None):
        self.a = np.zeros((H, W, 3), np.float32) if img is None else img.copy()

    def copy(self):
        return Canvas(self.a)

    def rect(self, x0, y0, x1, y1, c):
        x0, x1 = max(0, int(x0)), min(W, int(x1))
        y0, y1 = max(0, int(y0)), min(H, int(y1))
        if x0 < x1 and y0 < y1:
            self.a[y0:y1, x0:x1] = C(c) if isinstance(c, str) else c

    def px(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = C(c) if isinstance(c, str) else c

    def blend_rect(self, x0, y0, x1, y1, c, a):
        x0, x1 = max(0, int(x0)), min(W, int(x1))
        y0, y1 = max(0, int(y0)), min(H, int(y1))
        if x0 < x1 and y0 < y1:
            self.a[y0:y1, x0:x1] = self.a[y0:y1, x0:x1] * (1 - a) + C(c) * a

    def blend_px(self, x, y, c, a):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.a[y, x] = self.a[y, x] * (1 - a) + C(c) * a

    def circle(self, cx, cy, r, c, blend=None):
        for y in range(int(cy - r - 1), int(cy + r + 2)):
            for x in range(int(cx - r - 1), int(cx + r + 2)):
                dx, dy = x + 0.5 - cx, y + 0.5 - cy
                if dx * dx + dy * dy <= r * r:
                    if blend is None:
                        self.px(x, y, c)
                    else:
                        self.blend_px(x, y, c, blend)

    def span_poly(self, rows, c, a=None):
        """rows: lista de (y, x0, x1)."""
        for y, x0, x1 in rows:
            if a is None:
                self.rect(x0, y, x1, y + 1, c)
            else:
                self.blend_rect(x0, y, x1, y + 1, c, a)

    def text(self, x, y, s, c, scale=1):
        for ch in s:
            g = FONT.get(ch, FONT[" "])
            for gy, row in enumerate(g):
                for gx, v in enumerate(row):
                    if v == "#":
                        self.rect(x + gx * scale, y + gy * scale,
                                  x + (gx + 1) * scale, y + (gy + 1) * scale, c)
            if ch == "É":  # tilde aguda
                self.rect(x + 2 * scale, y - 3 * scale, x + 3 * scale, y - 2 * scale, c)
                self.rect(x + 1 * scale, y - 2 * scale, x + 2 * scale, y - 1 * scale, c)
            x += (len(g[0]) + 1) * scale


FONT = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "E": ["###", "#..", "##.", "#..", "###"],
    "É": ["###", "#..", "##.", "#..", "###"],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    "N": ["#..#", "##.#", "#.##", "#..#", "#..#"],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"],
    " ": ["..", "..", "..", "..", ".."],
}


def text_width(s, scale=1):
    return sum((len(FONT[ch][0]) + 1) * scale for ch in s) - scale


# ---------------------------------------------------------------- fondo
def draw_background():
    cv = Canvas()
    rnd = random.Random(7)

    # Cielo de atardecer en bandas con tramado entre ellas
    bands = [(0, "#2a2d6e"), (18, "#3d3a86"), (34, "#5a4598"), (50, "#7f4f9e"),
             (64, "#a85a99"), (77, "#d06c8c"), (89, "#ec8a7c"), (100, "#f7a970"),
             (110, "#fbc77e"), (140, "#fbc77e")]
    for (ya, ca), (yb, _) in zip(bands, bands[1:]):
        cv.rect(0, ya, W, yb, ca)
    for (ya, ca), (yb, cb) in zip(bands, bands[1:]):
        for x in range(W):          # dos filas de tramado en cada frontera
            if x % 2 == 0:
                cv.px(x, yb - 1, cb)
            if x % 2 == 1:
                cv.px(x, yb, ca)
            if x % 4 == 0:
                cv.px(x, yb - 2, cb)
    # Estrellas
    for _ in range(40):
        x, y = rnd.randrange(W), rnd.randrange(0, 40)
        cv.px(x, y, "#fff6d8" if rnd.random() < .4 else "#b9b4e6")
    for x, y in [(40, 10), (300, 16), (210, 6)]:
        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            cv.px(x + dx, y + dy, "#fff6d8")

    # Sol poniente con franjas retro
    cv.circle(70, 112, 26, "#ffd98f", blend=0.18)
    cv.circle(70, 112, 20, "#ffd98f", blend=0.25)
    cv.circle(70, 112, 15, "#ffe7a8")
    for y, h in [(103, 1), (107, 1), (110, 2), (114, 2)]:
        for x in range(50, 90):
            if np.allclose(cv.a[y, x], C("#ffe7a8")):
                cv.rect(x, y, x + 1, y + h, "#fbc77e")

    # Nubes
    def cloud(x, y, w):
        cv.rect(x + 4, y, x + w - 6, y + 2, "#ffd3c0")
        cv.rect(x, y + 2, x + w, y + 5, "#f3a2a6")
        cv.rect(x + 2, y + 2, x + w - 8, y + 3, "#ffd3c0")
        cv.rect(x + 3, y + 5, x + w - 2, y + 6, "#c77a98")
        cv.rect(x + w // 3, y - 2, x + w // 3 + 8, y, "#ffd3c0")
    cloud(120, 46, 34); cloud(160, 56, 22); cloud(250, 34, 40); cloud(20, 68, 26)
    cloud(330, 52, 30)

    # Colinas (dos capas) y pinos
    for x in range(W):
        y1 = int(110 + 5 * math.sin(x * 0.031) + 3 * math.sin(x * 0.077 + 2))
        cv.rect(x, y1, x + 1, 136, "#8a5c95")
        cv.px(x, y1, "#a8709f")
    for x in range(W):
        y2 = int(119 + 4 * math.sin(x * 0.045 + 1) + 2 * math.sin(x * 0.11))
        cv.rect(x, y2, x + 1, 136, "#4e3f73")
        cv.px(x, y2, "#64508a")
    for tx in [8, 18, 96, 108, 116, 170, 182, 228, 240]:
        base = int(119 + 4 * math.sin(tx * 0.045 + 1) + 2 * math.sin(tx * 0.11)) + 1
        h = 10 + (tx * 7) % 6
        for i in range(h):
            half = (i * 4) // h + (1 if i > h // 2 else 0)
            cv.rect(tx - half, base - h + i, tx + half + 1, base - h + i + 1, "#33294f")
        cv.rect(tx, base, tx + 1, base + 2, "#2a2038")

    # Franja de césped y valla metálica
    cv.rect(0, 128, W, 137, "#3c5a4e")
    cv.rect(0, 128, W, 129, "#58806a")
    for x in range(0, 270):
        for y in range(118, 134):
            if (x + y) % 4 == 0 or (x - y) % 4 == 0:
                cv.blend_px(x, y, "#9aa3bd", 0.45)
    cv.rect(0, 118, 270, 119, "#7c8399")
    for x in range(4, 270, 22):
        cv.rect(x, 116, x + 2, 135, "#5a6075")
        cv.px(x, 116, "#9aa3bd")

    # Patio de asfalto con textura
    cv.rect(0, 136, W, H, "#3b3d4c")
    cv.rect(0, 136, W, 137, "#8e8c9c")
    cv.rect(0, 137, W, 138, "#5b5b6c")
    for _ in range(1400):
        x, y = rnd.randrange(W), rnd.randrange(138, H)
        cv.px(x, y, "#454757" if rnd.random() < .6 else "#34353f")
    for x in range(0, W, 18):        # línea discontinua
        cv.rect(x, 202, x + 10, 204, "#d8d2bd")
        cv.rect(x, 204, x + 10, 205, "#9f9a8b")

    # Farolas
    for lx in (34, 196):
        cv.rect(lx, 98, lx + 2, 137, "#353a4d")
        cv.rect(lx, 98, lx + 9, 100, "#353a4d")
        cv.rect(lx + 6, 100, lx + 11, 102, "#2a2d3a")
        cv.rect(lx + 7, 102, lx + 10, 103, "#fff4bf")
        rows = [(y, lx + 8 - (y - 103) // 3, lx + 10 + (y - 103) // 3) for y in range(103, 137)]
        cv.span_poly(rows, "#ffe9a0", 0.10)
        for y in range(137, 146):    # charco de luz en el suelo
            hw = int(18 * math.sqrt(max(0, 1 - ((y - 140) / 6) ** 2)))
            cv.blend_rect(lx + 9 - hw, y, lx + 9 + hw, y + 1, "#ffe9a0", 0.12)

    draw_warehouse(cv)
    return cv


# ---------------------------------------------------------------- almacén
WX = 266                    # borde izquierdo del almacén
DOORS = [(284, 312), (330, 358)]
DOOR_Y0, DOOR_Y1 = 112, 150


def draw_warehouse(cv):
    # Pared de chapa ondulada
    pal = ["#9aa7bf", "#8795ae", "#76839c"]
    for x in range(WX, W):
        cv.rect(x, 66, x + 1, 152, pal[(x - WX) % 3])
    cv.blend_rect(WX, 66, W, 74, "#1b1f33", 0.35)      # sombra del alero
    cv.rect(WX, 66, WX + 2, 152, "#5f6b84")            # arista
    # Peto y cubierta
    cv.rect(WX - 2, 58, W, 66, "#59637c")
    cv.rect(WX - 2, 58, W, 59, "#b7c2d6")
    cv.rect(WX - 2, 65, W, 66, "#3e465b")
    # Bajante
    cv.rect(WX + 5, 66, WX + 7, 152, "#c9d0de")
    cv.rect(WX + 6, 66, WX + 7, 152, "#8b94a8")
    cv.rect(WX + 3, 150, WX + 9, 152, "#c9d0de")

    # Rótulo
    label = "ALMACÉN"
    tw = text_width(label, 2)
    sx0, sx1 = 292, 292 + tw + 12
    cv.rect(sx0 - 1, 71, sx1 + 1, 94, "#e9eef7")
    cv.rect(sx0, 72, sx1, 93, "#21305c")
    cv.rect(sx0, 72, sx1, 73, "#34457a")
    cv.text(sx0 + 6, 80, label, "#f6f1e2", 2)
    for bx in (sx0 + 8, sx1 - 10):                     # focos del rótulo
        cv.rect(bx, 68, bx + 3, 70, "#2a2d3a")
        cv.span_poly([(y, bx - (y - 70) // 2, bx + 3 + (y - 70) // 2) for y in range(70, 76)],
                     "#fff2b5", 0.18)

    # Ventanas altas iluminadas
    for i, x in enumerate(range(WX + 12, W - 4, 13)):
        lit = (i * 5) % 7 not in (2, 5)
        cv.rect(x - 1, 95, x + 8, 102, "#3a4258")
        cv.rect(x, 96, x + 7, 101, "#ffd77a" if lit else "#2b3350")
        if lit:
            cv.rect(x, 96, x + 7, 97, "#fff0b8")
            cv.blend_rect(x - 2, 102, x + 9, 105, "#ffd77a", 0.12)

    # Muelle de carga de hormigón
    cv.rect(WX, 150, W, 168, "#9a958c")
    cv.rect(WX, 150, W, 151, "#cfc8b8")
    cv.rect(WX, 166, W, 168, "#6e6a63")
    for x in range(WX + 20, W, 24):
        cv.rect(x, 151, x + 1, 166, "#857f76")
    cv.blend_rect(WX - 4, 168, W, 172, "#141420", 0.35)   # sombra al patio

    for n, (d0, d1) in enumerate(DOORS):
        # Marquesina, marco, topes y número
        cv.rect(d0 - 4, 106, d1 + 4, 110, "#2f3547")
        cv.rect(d0 - 4, 110, d1 + 4, 111, "#1f2433")
        cv.rect(d0 - 2, DOOR_Y0 - 1, d1 + 2, DOOR_Y1, "#4b546a")
        for bx in (d0 - 4, d1 + 1):
            cv.rect(bx, 152, bx + 3, 160, "#1c1c22")
            cv.rect(bx, 152, bx + 3, 153, "#3a3a44")
        cv.rect(d1 + 5, 114, d1 + 11, 122, "#21305c")
        cv.text(d1 + 7, 116, str(n + 1), "#f6f1e2")
        # Lámpara de muelle
        lx = (d0 + d1) // 2
        cv.rect(lx - 2, 102, lx + 2, 105, "#2a2d3a")
        cv.rect(lx - 1, 105, lx + 1, 106, "#fff4bf")
        cv.span_poly([(y, lx - 2 - (y - 106) // 2, lx + 2 + (y - 106) // 2)
                      for y in range(111, 168)], "#ffe9a0", 0.07)

    # Palés con cajas sobre el muelle
    def boxes(x, y):
        cv.rect(x, y + 8, x + 16, y + 10, "#8a6a42")
        cv.rect(x + 1, y + 10, x + 3, y + 11, "#5e472c")
        cv.rect(x + 13, y + 10, x + 15, y + 11, "#5e472c")
        for bx, by, bw, bh in [(x, y, 8, 8), (x + 8, y + 1, 8, 7), (x + 3, y - 6, 8, 6)]:
            cv.rect(bx, by, bx + bw, by + bh, "#c99a5c")
            cv.rect(bx, by, bx + bw, by + 1, "#e3b97a")
            cv.rect(bx + bw - 1, by, bx + bw, by + bh, "#a07842")
            cv.rect(bx + bw // 2, by, bx + bw // 2 + 1, by + 3, "#e8dcc0")
    boxes(364, 139)


def draw_door(cv, f):
    """f = 0 cerrada, 1 abierta. Sólo la puerta 1 se abre."""
    for n, (d0, d1) in enumerate(DOORS):
        fo = f if n == 0 else 0.0
        h = DOOR_Y1 - DOOR_Y0
        # Interior cálido
        cv.rect(d0, DOOR_Y0, d1, DOOR_Y1, "#2a2230")
        cv.rect(d0, DOOR_Y1 - 6, d1, DOOR_Y1, "#4a3a36")
        cv.rect(d0 + 3, DOOR_Y1 - 16, d0 + 11, DOOR_Y1 - 6, "#7a5a3a")
        cv.rect(d0 + 12, DOOR_Y1 - 12, d0 + 18, DOOR_Y1 - 6, "#6a4e34")
        cv.rect(d0 + 3, DOOR_Y1 - 16, d0 + 11, DOOR_Y1 - 15, "#9a7650")
        cv.blend_rect(d0, DOOR_Y0, d1, DOOR_Y1, "#ffcf80", 0.12)
        # Persiana enrollable
        vis = int(round(h * (1 - fo)))
        for y in range(DOOR_Y0, DOOR_Y0 + vis):
            k = (y - DOOR_Y0) % 3
            cv.rect(d0, y, d1, y + 1, ["#cfd4de", "#bcc2ce", "#959cab"][k])
        if vis > 2:
            cv.rect(d0, DOOR_Y0 + vis - 2, d1, DOOR_Y0 + vis, "#5b6274")
            cv.rect((d0 + d1) // 2 - 2, DOOR_Y0 + vis - 4, (d0 + d1) // 2 + 2,
                    DOOR_Y0 + vis - 3, "#3b4050")
        if fo > 0.3:   # luz que sale del muelle abierto
            a = 0.14 * min(1, (fo - 0.3) / 0.5)
            cv.span_poly([(y, d0 - (y - 150) // 2, d1 + (y - 150) // 2) for y in range(150, 168)],
                         "#ffcf80", a)


def draw_worker(cv, x, y, frame, waving):
    """Operario sobre el muelle (pies en y)."""
    cv.rect(x, y - 4, x + 1, y, "#24305a"); cv.rect(x + 2, y - 4, x + 3, y, "#24305a")
    cv.rect(x - 1, y - 9, x + 4, y - 4, "#ff7a1a")
    cv.rect(x - 1, y - 7, x + 4, y - 6, "#e9f06a")
    cv.rect(x, y - 12, x + 3, y - 9, "#f0b98a")
    cv.rect(x - 1, y - 13, x + 4, y - 11, "#ffcc33")
    if waving and (frame // 3) % 2 == 0:
        cv.rect(x + 4, y - 14, x + 5, y - 8, "#ff7a1a"); cv.rect(x + 4, y - 15, x + 5, y - 14, "#f0b98a")
    elif waving:
        cv.rect(x + 4, y - 12, x + 6, y - 11, "#ff7a1a"); cv.rect(x + 5, y - 16, x + 6, y - 12, "#ff7a1a")
        cv.rect(x + 5, y - 17, x + 6, y - 16, "#f0b98a")
    else:
        cv.rect(x + 4, y - 9, x + 5, y - 5, "#ff7a1a")
    cv.rect(x - 2, y - 9, x - 1, y - 5, "#ff7a1a")


# ---------------------------------------------------------------- camión
RED, RED_HI, RED_LO, RED_DK = "#c8343c", "#ea5a5e", "#8f2230", "#4a1822"
CHROME, CHROME_HI, CHROME_LO = "#c3c9d6", "#f2f5fa", "#7d8597"
WHITE, WHITE_SH, WHITE_LO = "#ecebe6", "#cfccc4", "#a9a59c"
NAVY = "#23315e"
GROUND = 186
WR = 7


def draw_wheel(cv, cx, cy, angle):
    cv.circle(cx, cy, WR + 0.4, "#18181e")
    cv.circle(cx - 0.6, cy - 0.6, WR - 0.6, "#2c2c35")
    cv.circle(cx, cy, WR - 1.4, "#1f1f26")
    cv.circle(cx, cy, 4.4, CHROME_LO)
    cv.circle(cx - 0.4, cy - 0.4, 3.8, CHROME)
    cv.circle(cx, cy, 1.6, CHROME_HI)
    for k in range(5):
        a = angle + k * 2 * math.pi / 5
        cv.px(round(cx - 0.5 + 2.8 * math.cos(a)), round(cy - 0.5 + 2.8 * math.sin(a)), "#5b6274")


def draw_truck(cv, x0, dist, braking):
    x0 = int(round(x0))
    wy = GROUND - WR
    # Sombra
    for y in range(GROUND - 2, GROUND + 3):
        cv.blend_rect(x0 - 2, y, x0 + 218, y + 1, "#0e0e16", 0.30 if y < GROUND + 1 else 0.15)

    # ---- Remolque
    tx0, tx1, ty0, ty1 = x0, x0 + 150, 126, 170
    cv.rect(tx0, ty0, tx1, ty1, WHITE)
    cv.rect(tx0, ty0, tx1, ty0 + 1, "#ffffff")
    cv.rect(tx0, ty0 + 1, tx1, ty0 + 3, WHITE_SH)
    cv.rect(tx0, ty1 - 3, tx1, ty1, WHITE_LO)
    for x in range(tx0 + 10, tx1 - 2, 14):                # costillas / remaches
        cv.rect(x, ty0 + 3, x + 1, ty1 - 3, WHITE_SH)
        for y in range(ty0 + 5, ty1 - 4, 6):
            cv.px(x + 1, y, "#ffffff")
    cv.rect(tx0, ty0, tx0 + 3, ty1, "#b9b5ac")           # puertas traseras
    cv.rect(tx0 + 3, ty0, tx0 + 4, ty1, "#8f8a80")
    cv.rect(tx1 - 2, ty0, tx1, ty1, "#d9d6ce")
    for x in range(tx0 + 6, tx1 - 4, 22):                # luces de gálibo
        cv.px(x, ty0 + 1, "#ffb030")
    # Rotulación
    label = "CARGA EXPRESS"
    lw = text_width(label, 2)
    lx = tx0 + (150 - lw) // 2
    cv.text(lx + 1, 139, label, "#b9c2dd", 2)               # sombra suave
    cv.text(lx, 138, label, NAVY, 2)
    cv.rect(tx0 + 4, 154, tx1 - 2, 158, RED)
    cv.rect(tx0 + 4, 154, tx1 - 2, 155, RED_HI)
    cv.rect(tx0 + 4, 159, tx1 - 2, 160, NAVY)
    # Bastidor, parachoques trasero, patas de apoyo, guardabarros
    cv.rect(tx0 + 2, ty1, tx1 - 4, ty1 + 3, "#26262f")
    cv.rect(tx0 + 3, ty1 + 3, tx0 + 6, ty1 + 10, "#3a3a44")
    cv.rect(tx0 + 1, ty1 + 9, tx0 + 12, ty1 + 11, "#3a3a44")
    cv.rect(tx0 + 106, ty1 + 3, tx0 + 108, GROUND - 4, "#7d8597")
    cv.rect(tx0 + 110, ty1 + 3, tx0 + 112, GROUND - 4, "#5b6274")
    cv.rect(tx0 + 104, GROUND - 4, tx0 + 114, GROUND - 3, "#3a3a44")
    cv.rect(tx0 + 104, ty1 + 6, tx0 + 114, ty1 + 7, "#5b6274")
    cv.rect(tx0 + 12, ty1 + 2, tx0 + 14, GROUND - 2, "#141418")
    # Pilotos (freno)
    tail = "#ff3030" if braking else "#a01c24"
    cv.rect(tx0, 163, tx0 + 2, 167, tail)
    if braking:
        cv.circle(tx0, 165, 6, "#ff3030", blend=0.25)
        cv.circle(tx0, 165, 3, "#ff6a5a", blend=0.35)

    # ---- Mangueras entre remolque y cabina
    for i, col in enumerate(("#d23a3a", "#3a6ad2")):
        for x in range(x0 + 150, x0 + 157):
            cv.px(x, 146 + i * 3 + (1 if 152 < x - x0 < 155 else 0), col)

    # ---- Chasis de la tractora
    cv.rect(x0 + 124, 170, x0 + 210, 174, "#26262f")
    cv.rect(x0 + 140, 168, x0 + 154, 170, "#3a3a44")       # quinta rueda

    # ---- Cabina dormitorio + deflector
    cx0 = x0 + 156
    rows = []
    for y in range(127, 172):
        xe = x0 + 170 if y < 131 else x0 + 170 + int((y - 131) * 20 / 10) if y < 141 else x0 + 192
        rows.append((y, cx0, min(xe, x0 + 192)))
    cv.span_poly(rows, RED)
    for y in range(127, 141):                             # luz en el deflector
        xe = x0 + 170 if y < 131 else x0 + 170 + int((y - 131) * 2)
        cv.px(xe - 1, y, RED_HI)
        cv.px(xe - 2, y, RED_HI)
    cv.rect(cx0, 127, x0 + 170, 128, RED_HI)
    cv.rect(cx0, 127, cx0 + 2, 172, RED_LO)
    cv.rect(cx0 + 2, 133, cx0 + 3, 168, RED_HI)
    # Franja decorativa
    cv.rect(cx0, 160, x0 + 214, 162, "#f2f0e8")
    cv.rect(cx0, 162, x0 + 214, 163, NAVY)
    # Ventana dormitorio y puerta
    cv.rect(x0 + 160, 142, x0 + 166, 146, "#3a2a40")
    cv.rect(x0 + 160, 142, x0 + 166, 143, "#6a5a7a")
    cv.rect(x0 + 173, 142, x0 + 174, 171, RED_DK)          # junta de puerta
    cv.rect(x0 + 173, 171, x0 + 190, 172, RED_DK)
    cv.rect(x0 + 184, 156, x0 + 187, 157, CHROME)          # tirador
    # Ventanilla (refleja el atardecer)
    win = [(y, x0 + 176, x0 + 190) for y in range(144, 154)]
    cv.span_poly(win, "#5f86b8")
    for y in range(144, 154):
        cv.px(x0 + 176 + (y - 144), y, "#f7b98a")
        cv.px(x0 + 177 + (y - 144), y, "#f7b98a")
    cv.rect(x0 + 176, 144, x0 + 190, 145, "#9fc0e0")
    cv.rect(x0 + 175, 143, x0 + 191, 144, RED_DK)
    # Techo de cabina, luces ámbar
    for x in range(x0 + 184, x0 + 191, 2):
        cv.px(x, 139, "#ffb030")
    # Capó
    cv.rect(x0 + 190, 150, x0 + 212, 172, RED)
    cv.rect(x0 + 190, 150, x0 + 210, 151, RED_HI)
    cv.rect(x0 + 210, 151, x0 + 212, 152, RED_HI)
    cv.rect(x0 + 190, 151, x0 + 191, 172, RED_LO)
    cv.rect(x0 + 192, 154, x0 + 208, 155, RED_LO)          # rejilla lateral
    cv.rect(x0 + 192, 156, x0 + 208, 157, RED_LO)
    # Calandra, faro, parachoques
    cv.rect(x0 + 212, 151, x0 + 215, 170, CHROME)
    for y in range(152, 169, 2):
        cv.rect(x0 + 212, y, x0 + 215, y + 1, CHROME_LO)
    cv.rect(x0 + 210, 157, x0 + 214, 160, "#fff6c8")
    cv.rect(x0 + 208, 170, x0 + 217, 175, CHROME)
    cv.rect(x0 + 208, 170, x0 + 217, 171, CHROME_HI)
    cv.rect(x0 + 208, 174, x0 + 217, 175, CHROME_LO)
    # Retrovisor
    cv.rect(x0 + 191, 145, x0 + 195, 146, "#26262f")
    cv.rect(x0 + 194, 141, x0 + 196, 150, "#26262f")
    # Pasos de rueda (arcos)
    for wx in (x0 + 199,):
        for y in range(wy - 9, 172):
            for x in range(wx - 10, wx + 11):
                dx, dy = x + .5 - wx, y + .5 - wy
                if dx * dx + dy * dy <= 9.6 ** 2:
                    cv.px(x, y, "#1a1a20")
    # Depósito de combustible
    cv.rect(x0 + 160, 172, x0 + 178, 181, CHROME)
    cv.rect(x0 + 160, 173, x0 + 178, 174, CHROME_HI)
    cv.rect(x0 + 160, 179, x0 + 178, 181, CHROME_LO)
    cv.rect(x0 + 163, 172, x0 + 164, 181, CHROME_LO)
    cv.rect(x0 + 174, 172, x0 + 175, 181, CHROME_LO)
    # Escape vertical
    cv.rect(x0 + 177, 116, x0 + 180, 152, CHROME)
    cv.rect(x0 + 177, 116, x0 + 178, 152, CHROME_HI)
    cv.rect(x0 + 179, 116, x0 + 180, 152, CHROME_LO)
    cv.rect(x0 + 176, 115, x0 + 181, 117, "#2a2a32")
    for y in range(124, 146, 3):
        cv.rect(x0 + 177, y, x0 + 180, y + 1, CHROME_LO)

    # ---- Ruedas
    ang = dist / WR
    for wx in (x0 + 22, x0 + 38, x0 + 136, x0 + 152, x0 + 199):
        draw_wheel(cv, wx, wy, ang)
    # Guardabarros tractora
    cv.rect(x0 + 128, 170, x0 + 160, 172, "#26262f")
    cv.rect(x0 + 160, 182, x0 + 162, GROUND - 2, "#141418")


def draw_headlight(cv, x0):
    x0 = int(round(x0))
    sx = x0 + 214
    rows = []
    for y in range(146, GROUND + 6):
        d = abs(y - 158.5)
        start = sx + int(d * 1.6)
        rows.append((y, start, sx + 70))
    for y, a, b in rows:
        for x in range(a, min(b, W)):
            t = (x - sx) / 70
            cv.blend_px(x, y, "#fff3b8", 0.20 * (1 - t))


# ---------------------------------------------------------------- animación
def ease_out(t):
    return 1 - (1 - t) ** 3


def main():
    bg = draw_background()
    X_START, X_END = -230, 46
    DRIVE, DOOR_START, DOOR_FRAMES, TOTAL = 52, 58, 16, 92
    smoke = []
    rnd = random.Random(3)
    frames = []
    prev_x = X_START
    for f in range(TOTAL):
        t = min(1, f / DRIVE)
        x = X_START + (X_END - X_START) * ease_out(t)
        v = x - prev_x
        prev_x = x
        dist = x - X_START
        braking = DRIVE - 18 <= f
        door = min(1, max(0, (f - DOOR_START) / DOOR_FRAMES))

        cv = bg.copy()
        draw_door(cv, door)
        draw_worker(cv, 320, 150, f, waving=f >= DRIVE - 6)

        # Humo del escape
        if f % 2 == 0:
            smoke.append([x + 178, 113, -0.3 + rnd.uniform(-.1, .1), -0.7, 1.0, 0])
        for p in smoke:
            # el humo se queda un poco atrás respecto al escape, sin dejar una estela larga
            p[0] += p[2] + v * 0.8
            p[1] += p[3]
            p[3] *= 0.96
            p[4] += 0.22
            p[5] += 1
        smoke = [p for p in smoke if p[5] < 14]
        draw_truck(cv, x, dist, braking)
        for sx, sy, _, _, r, age in smoke:
            a = 0.55 * (1 - age / 14)
            cv.circle(sx, sy, r, "#8c8897", blend=a)
            cv.circle(sx - r * 0.3, sy - r * 0.3, r * 0.5, "#b9b4c4", blend=a * 0.8)
        draw_headlight(cv, x)
        frames.append(np.clip(cv.a, 0, 255).astype(np.uint8))

    # Paleta global (evita parpadeo de colores entre fotogramas)
    sample = Image.fromarray(np.concatenate(frames[::6] + [frames[-1]], axis=0))
    pal_img = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    gif_frames = []
    for fr in frames:
        im = Image.fromarray(fr).resize((W * 3, H * 3), Image.NEAREST)
        gif_frames.append(im.quantize(palette=pal_img, dither=Image.Dither.NONE))
    durations = [70] * TOTAL
    durations[-1] = 1800
    gif_frames[0].save(os.path.join(OUT, "camion_almacen.gif"), save_all=True,
                       append_images=gif_frames[1:], duration=durations, loop=0,
                       optimize=True, disposal=1)
    Image.fromarray(frames[-1]).resize((W * 4, H * 4), Image.NEAREST).save(
        os.path.join(OUT, "camion_almacen.png"))
    print("ok", len(frames), "frames")


if __name__ == "__main__":
    main()
