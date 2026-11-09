"""
Paper-craft theme: every scene is a layered paper diorama (sky, sun, puffy clouds, folded mountains, fort, trees, sea, ships) that
unfolds like a pop-up book and drifts with parallax, on a blurred copy of itself; headline in cream type, info on paper cards,
subtitles as terracotta paper word-chips. Everything is drawn in code (no images, no AI image/video tools, no cost).
"""
import math
import random
import re
import zlib
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 720, 1280
CW, CH = 640, 400            # diorama card
LW = CW + 140                # world width of a layer (room for parallax)
CX = W // 2
BASE = Path(__file__).parent
CFG = {"brand": "शिवगाथा", "handle": "shivgatha"}

CREAM = (248, 237, 216)
CREAM2 = (236, 219, 188)
TERRA = (198, 106, 74)
TERRA_D = (156, 72, 48)
INKP = (62, 40, 26)
SAFF = (224, 104, 28)
GOLDY = (255, 206, 92)
SHADOW = (44, 24, 14)

# ------------------------------------------------------------------ fonts + text helpers
_NOTO = "/usr/share/fonts/truetype/noto/"
_FD = {
    "serifb": ["fonts/NotoSerifDevanagari-Bold.ttf", _NOTO + "NotoSerifDevanagari-Bold.ttf"],
    "serif": ["fonts/NotoSerifDevanagari-Regular.ttf", _NOTO + "NotoSerifDevanagari-Regular.ttf"],
    "sansb": ["fonts/NotoSansDevanagari-Bold.ttf", _NOTO + "NotoSansDevanagari-Bold.ttf"],
    "sans": ["fonts/NotoSansDevanagari-Regular.ttf", _NOTO + "NotoSansDevanagari-Regular.ttf"],
    "latin": ["fonts/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


@lru_cache(maxsize=None)
def font(kind, size):
    for p in _FD[kind] + ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        pp = Path(p) if p.startswith("/") else BASE / p
        if pp.exists():
            try:
                return ImageFont.truetype(str(pp), size)
            except Exception:
                continue
    return ImageFont.load_default()


_MD = ImageDraw.Draw(Image.new("L", (4, 4)))


def tw(s, f):
    return _MD.textlength(s, font=f)


def wrap(s, f, max_w):
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if tw(t, f) <= max_w or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def fit_lines(s, kind, size, max_w, max_lines, min_size=18):
    while size > min_size:
        f = font(kind, size)
        ls = wrap(s, f, max_w)
        if len(ls) <= max_lines:
            return f, ls
        size -= 2
    f = font(kind, min_size)
    return f, wrap(s, f, max_w)[:max_lines]


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def back(x):
    """overshoot ease (pop-up feel)"""
    x = max(0.0, min(1.0, x))
    c = 1.4
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def reveal(t, i, persist, step=0.35, dur=0.5, start=0.3):
    if persist:
        return 1.0, 0
    e = ease((t - start - i * step) / dur)
    return e, int((1 - e) * 22)


# ------------------------------------------------------------------ paper material
_GR = {}


def grain(w, h, k):
    key = (w, h, round(k, 2))
    if key not in _GR:
        if "big" not in _GR:
            _GR["big"] = Image.effect_noise((1100, 1500), 46)
        g = _GR["big"].crop((0, 0, w, h)) if w <= 1100 and h <= 1500 else _GR["big"].resize((w, h))
        _GR[key] = g.point(lambda v: int(128 + (v - 128) * k)).convert("RGB")
    return _GR[key]


def lighten(c, a=1.14, b=8):
    return tuple(min(255, int(v * a + b)) for v in c)


def darken(c, a=0.78):
    return tuple(int(v * a) for v in c)


def _tint_img(im, fn):
    return im.point(fn)


def paperize(mask, rgb, shadow=9, blur=6, shade=120, grain_k=0.30, edges=True):
    """mask (L) + colour (tuple or RGB image) -> RGBA paper cut-out: fibre grain, light top edge, dark bottom edge, soft drop shadow"""
    w, h = mask.size
    base = rgb.copy() if isinstance(rgb, Image.Image) else Image.new("RGB", (w, h), rgb)
    base = ImageChops.add(base, grain(w, h, grain_k), 1, -128)
    if edges:
        up = Image.new("L", (w, h), 0)
        up.paste(mask, (0, 3))
        top = ImageChops.subtract(mask, up)
        dn = Image.new("L", (w, h), 0)
        dn.paste(mask, (0, -3))
        bot = ImageChops.subtract(mask, dn)
        base = Image.composite(_tint_img(base, lambda v: min(255, int(v * 1.18 + 10))), base, top)
        base = Image.composite(_tint_img(base, lambda v: int(v * 0.74)), base, bot)
    sh = mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * shade / 255))
    sh_img = Image.new("L", (w, h), 0)
    sh_img.paste(sh, (0, shadow))
    out = Image.new("RGBA", (w, h), SHADOW + (0,))
    out.putalpha(sh_img)
    shape = base.convert("RGBA")
    shape.putalpha(mask)
    return Image.alpha_composite(out, shape)


def new_mask(w, h):
    m = Image.new("L", (w, h), 0)
    return m, ImageDraw.Draw(m)


# ------------------------------------------------------------------ palettes
PALETTES = {
    "sunset": dict(sky=[(222, 128, 112), (242, 164, 104), (252, 216, 146)], far=(126, 150, 140), mid=(96, 136, 84), fort=(222, 190, 140), fg=(70, 116, 70), sun=True),
    "dawn": dict(sky=[(172, 192, 218), (238, 206, 186), (252, 232, 188)], far=(136, 158, 160), mid=(112, 150, 104), fort=(226, 198, 154), fg=(78, 124, 80), sun=True),
    "night": dict(sky=[(18, 24, 58), (44, 44, 90), (92, 70, 112)], far=(52, 64, 98), mid=(36, 54, 78), fort=(120, 100, 96), fg=(24, 40, 54), sun=False),
    "forest": dict(sky=[(150, 178, 156), (200, 214, 176), (240, 232, 190)], far=(110, 146, 120), mid=(70, 112, 76), fort=(206, 178, 132), fg=(44, 88, 56), sun=False),
    "sea": dict(sky=[(128, 172, 208), (206, 214, 206), (252, 226, 184)], far=(122, 152, 150), mid=(92, 134, 96), fort=(222, 190, 140), fg=(60, 120, 150), sun=True),
}
KIND_PALETTE = {"fort": "sunset", "ridge": "sunset", "sea": "sea", "forest": "forest", "night": "night", "dawn": "dawn"}
KINDS = tuple(KIND_PALETTE)


def sky_img(stops):
    im = Image.new("RGB", (CW, CH))
    px = ImageDraw.Draw(im)
    for y in range(CH):
        f = y / (CH * 0.78)
        f = min(1.0, f)
        a, b = (0, 1) if f < 0.5 else (1, 2)
        ff = f * 2 if f < 0.5 else (f - 0.5) * 2
        c = tuple(int(stops[a][i] + (stops[b][i] - stops[a][i]) * ff) for i in range(3))
        px.line((0, y, CW, y), fill=c)
    return ImageChops.add(im, grain(CW, CH, 0.22), 1, -128)


# ------------------------------------------------------------------ paper parts
def mountains(rng, color, base, amp, n, facet=True, w=LW, h=CH):
    pts = [(0, h)]
    xs = sorted([rng.uniform(0, w) for _ in range(n)])
    peaks = []
    x = -20
    top = [(x, base)]
    for i in range(n):
        px = (i + 0.5) * w / n + rng.uniform(-30, 30)
        py = base - rng.uniform(amp * 0.55, amp)
        vx = (i + 1) * w / n + rng.uniform(-25, 25)
        vy = base - rng.uniform(0, amp * 0.18)
        top += [(px, py), (vx, vy)]
        peaks.append((px, py))
    poly = [(0, h)] + top + [(w, base), (w, h)]
    m, d = new_mask(w, h)
    d.polygon(poly, fill=255)
    img = Image.new("RGB", (w, h), color)
    if facet:
        di = ImageDraw.Draw(img)
        for i, (px, py) in enumerate(peaks):
            lx, ly = top[2 * i][0], top[2 * i][1]
            rx, ry = top[2 * i + 2][0], top[2 * i + 2][1]
            di.polygon([(lx, ly), (px, py), (px + (rx - px) * 0.06, h)], fill=lighten(color, 1.10, 6))
            di.polygon([(px, py), (rx, ry), (px + (rx - px) * 0.06, h)], fill=darken(color, 0.86))
    return paperize(m, img, shadow=8, blur=6, shade=95)


def hills(rng, color, base, amp, w=LW, h=CH):
    m, d = new_mask(w, h)
    pts = [(0, h)]
    ph = rng.uniform(0, 6)
    for x in range(0, w + 8, 8):
        pts.append((x, base - amp * (0.55 + 0.45 * math.sin(x / 95 + ph)) - amp * 0.2 * math.sin(x / 41 + ph * 2)))
    pts.append((w, h))
    d.polygon(pts, fill=255)
    img = Image.new("RGB", (w, h), color)
    di = ImageDraw.Draw(img)
    for _ in range(int(w / 26)):                                   # tiny folded-paper foliage flecks
        fx, fy = rng.uniform(0, w), rng.uniform(base - amp, h)
        s = rng.uniform(6, 13)
        di.polygon([(fx, fy), (fx + s, fy + s * 0.5), (fx + s * 0.3, fy + s)], fill=lighten(color, 1.1, 4))
    return paperize(m, img, shadow=9, blur=6, shade=100)


def fort_layer(rng, color, base, scale=1.0, cx=None, w=LW, h=CH):
    """sandstone fort on a hill; returns sprite and the flag position"""
    cx = cx or w * 0.62
    m, d = new_mask(w, h)
    img = Image.new("RGB", (w, h), color)
    di = ImageDraw.Draw(img)
    hill = [(cx - 230 * scale, h)]
    for k in range(0, 11):
        fx = -1 + 2 * k / 10
        hill.append((cx + fx * 230 * scale, base + 14 - (60 + 40 * (1 - abs(fx))) * scale + rng.uniform(-5, 5)))
    hill.append((cx + 230 * scale, h))
    d.polygon(hill, fill=255)
    di.polygon(hill, fill=(118, 98, 70))
    wall_t, wall_b = base - 52 * scale, base + 6
    x0, x1 = cx - 150 * scale, cx + 150 * scale
    d.rectangle((x0, wall_t, x1, wall_b), fill=255)
    di.rectangle((x0, wall_t, x1, wall_b), fill=color)
    di.rectangle((x0, wall_t, x1, wall_t + 10), fill=lighten(color, 1.1, 6))
    x = x0
    while x < x1 - 6:
        d.rectangle((x, wall_t - 9 * scale, x + 11 * scale, wall_t), fill=255)
        di.rectangle((x, wall_t - 9 * scale, x + 11 * scale, wall_t), fill=color)
        x += 20 * scale
    flag_xy = (cx, wall_t)
    for ox, th, tw_ in ((-150, 78, 40), (-50, 100, 36), (50, 130, 44), (150, 84, 40)):
        tx, ty = cx + ox * scale, base - th * scale
        a, b = tx - tw_ * scale / 2, tx + tw_ * scale / 2
        d.rectangle((a, ty, b, wall_b), fill=255)
        di.rectangle((a, ty, tx + 2, wall_b), fill=lighten(color, 1.08, 6))
        di.rectangle((tx + 2, ty, b, wall_b), fill=darken(color, 0.82))
        xx = a
        while xx < b - 4:
            d.rectangle((xx, ty - 8 * scale, xx + 9 * scale, ty), fill=255)
            di.rectangle((xx, ty - 8 * scale, xx + 9 * scale, ty), fill=darken(color, 0.9))
            xx += 16 * scale
        di.rounded_rectangle((tx - 4 * scale, ty + 14 * scale, tx + 4 * scale, ty + 34 * scale), 4, fill=(96, 70, 52))
        if th == 130:
            flag_xy = (tx, ty - 8 * scale)
    gx = cx
    di.rectangle((gx - 16 * scale, wall_b - 28 * scale, gx + 16 * scale, wall_b), fill=(70, 48, 36))
    di.pieslice((gx - 16 * scale, wall_b - 46 * scale, gx + 16 * scale, wall_b - 10 * scale), 180, 360, fill=(70, 48, 36))
    return paperize(m, img, shadow=10, blur=7, shade=115), flag_xy


def trees(rng, color, n, base, size, edge="both", w=LW, h=CH):
    m, d = new_mask(w, h)
    img = Image.new("RGB", (w, h), color)
    di = ImageDraw.Draw(img)
    for i in range(n):
        if edge == "both":
            tx = rng.choice([rng.uniform(10, 170), rng.uniform(w - 190, w - 10)])
        else:
            tx = rng.uniform(20, w - 20)
        s = size * rng.uniform(0.75, 1.15)
        di.rectangle((tx - 5, base - 14, tx + 5, base + 40), fill=(98, 66, 42))
        d.rectangle((tx - 5, base - 14, tx + 5, base + 40), fill=255)
        for k in range(3):
            tier_w = s * (1 - 0.22 * k)
            ty = base - k * s * 0.55
            tri = [(tx - tier_w / 2, ty), (tx, ty - s * 0.95), (tx + tier_w / 2, ty)]
            d.polygon(tri, fill=255)
            di.polygon([tri[0], tri[1], (tx, ty)], fill=lighten(color, 1.12, 6))
            di.polygon([tri[1], tri[2], (tx, ty)], fill=darken(color, 0.82))
    d.rectangle((0, base + 20, w, h), fill=255)
    di.rectangle((0, base + 20, w, h), fill=darken(color, 0.9))
    return paperize(m, img, shadow=10, blur=7, shade=110)


def cloud_sprite(rng, w=170, h=80):
    m, d = new_mask(w, h)
    for _ in range(6):
        r = rng.uniform(20, 31)
        cx, cy = rng.uniform(34, w - 34), rng.uniform(h * 0.5, h - 24)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    d.rectangle((20, h * 0.62, w - 20, h - 18), fill=255)
    return paperize(m, (250, 246, 238), shadow=8, blur=5, shade=85, grain_k=0.2)


def sun_sprite(r=60):
    s = r * 2 + 40
    m, d = new_mask(s, s)
    c = s / 2
    pts = []
    for k in range(40):
        a = k * math.pi / 20
        rr = r + 14 if k % 2 == 0 else r + 2
        pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
    d.polygon(pts, fill=255)
    img = Image.new("RGB", (s, s), (246, 196, 70))
    di = ImageDraw.Draw(img)
    di.ellipse((c - r + 6, c - r + 6, c + r - 6, c + r - 6), fill=(250, 214, 96))
    for k in range(5, 0, -1):
        rr = r * k / 6
        di.ellipse((c - rr, c - rr, c + rr, c + rr), outline=(238, 176, 52), width=2)
    return paperize(m, img, shadow=6, blur=5, shade=70, grain_k=0.28)


def moon_sprite(r=36):
    s = r * 2 + 30
    m, d = new_mask(s, s)
    c = s / 2
    d.ellipse((c - r, c - r, c + r, c + r), fill=255)
    img = Image.new("RGB", (s, s), (242, 234, 208))
    di = ImageDraw.Draw(img)
    for (ox, oy, rr) in ((-10, -8, 8), (12, 6, 6), (-4, 14, 5)):
        di.ellipse((c + ox - rr, c + oy - rr, c + ox + rr, c + oy + rr), fill=(220, 210, 184))
    return paperize(m, img, shadow=4, blur=4, shade=60, grain_k=0.18)


def ship_sprite(rng, s=1.0):
    w, h = int(150 * s), int(130 * s)
    m, d = new_mask(w, h)
    img = Image.new("RGB", (w, h), (150, 104, 66))
    di = ImageDraw.Draw(img)
    hull = [(w * 0.1, h * 0.72), (w * 0.9, h * 0.72), (w * 0.76, h * 0.94), (w * 0.24, h * 0.94)]
    d.polygon(hull, fill=255)
    di.polygon(hull, fill=(150, 104, 66))
    d.rectangle((w * 0.49, h * 0.12, w * 0.51, h * 0.72), fill=255)
    di.rectangle((w * 0.49, h * 0.12, w * 0.51, h * 0.72), fill=(96, 66, 44))
    for (a, b, c_) in (((w * 0.5, h * 0.14), (w * 0.5, h * 0.66), (w * 0.82, h * 0.66)), ((w * 0.5, h * 0.2), (w * 0.5, h * 0.66), (w * 0.2, h * 0.66))):
        d.polygon([a, b, c_], fill=255)
    di.polygon([(w * 0.5, h * 0.14), (w * 0.5, h * 0.66), (w * 0.82, h * 0.66)], fill=(246, 238, 220))
    di.polygon([(w * 0.5, h * 0.2), (w * 0.5, h * 0.66), (w * 0.2, h * 0.66)], fill=(226, 212, 186))
    d.polygon([(w * 0.5, h * 0.04), (w * 0.72, h * 0.1), (w * 0.5, h * 0.17)], fill=255)
    di.polygon([(w * 0.5, h * 0.04), (w * 0.72, h * 0.1), (w * 0.5, h * 0.17)], fill=SAFF)
    return paperize(m, img, shadow=6, blur=4, shade=80, grain_k=0.25)


def waves(rng, color, base, amp=8, w=LW, h=CH):
    m, d = new_mask(w, h)
    pts = [(0, h)]
    for x in range(0, w + 6, 6):
        pts.append((x, base + amp * math.sin(x / 15) + amp * 0.5 * math.sin(x / 7.3)))
    pts.append((w, h))
    d.polygon(pts, fill=255)
    img = Image.new("RGB", (w, h), color)
    di = ImageDraw.Draw(img)
    for _ in range(int(w / 40)):
        fx, fy = rng.uniform(0, w), rng.uniform(base + 6, h)
        di.polygon([(fx, fy), (fx + 18, fy - 6), (fx + 36, fy)], fill=lighten(color, 1.16, 8))
    return paperize(m, img, shadow=7, blur=5, shade=80)


def mist(w=LW, h=CH, y=250):
    m, d = new_mask(w, h)
    d.ellipse((-40, y, w + 40, y + 120), fill=120)
    m = m.filter(ImageFilter.GaussianBlur(26))
    out = Image.new("RGBA", (w, h), (250, 246, 236, 0))
    out.putalpha(m)
    return out


# ------------------------------------------------------------------ the diorama (built once per scene, drawn every frame)
class Art:
    def __init__(self, kind, seed):
        self.kind = kind if kind in KINDS else "fort"
        rng = random.Random(seed)
        pal = PALETTES[KIND_PALETTE[self.kind]]
        self.pal = pal
        self.sky = sky_img(pal["sky"])
        self.layers = []                              # (sprite, depth, y_offset, wave_speed)
        self.flag = None
        self.stars = [(rng.uniform(8, CW - 8), rng.uniform(8, CH * 0.5), rng.uniform(0, 6)) for _ in range(34)] if self.kind == "night" else []
        self.sun = sun_sprite() if pal["sun"] else (moon_sprite() if self.kind == "night" else None)
        self.sun_xy = (rng.uniform(CW * 0.22, CW * 0.7), CH * 0.34) if self.sun else None
        self.clouds = [(cloud_sprite(rng), rng.uniform(0, CW + 200), rng.uniform(26, 120), rng.uniform(5, 11), rng.uniform(0, 6)) for _ in range(3 if self.kind != "night" else 1)]
        self.ships = []
        far = mountains(rng, pal["far"], CH * 0.66, 150, 5)
        self.layers.append((far, 0.12, 0, 0.0))
        if self.kind == "sea":
            self.layers.append((waves(rng, (96, 150, 186), CH * 0.70), 0.25, 0, 7.0))
            fl, fx = fort_layer(rng, pal["fort"], CH * 0.74, scale=0.75, cx=LW * 0.3)
            self.layers.append((fl, 0.4, 0, 0.0))
            self.flag = (fx[0], fx[1], 0.4)
            self.ships = [(ship_sprite(rng, 1.0), LW * 0.62, CH * 0.64, 0.6), (ship_sprite(rng, 0.7), LW * 0.42, CH * 0.62, 0.45)]
            self.layers.append((waves(rng, (70, 128, 168), CH * 0.80, 9), 0.8, 0, -9.0))
            self.layers.append((waves(rng, (52, 108, 150), CH * 0.90, 10), 1.0, 0, 12.0))
        elif self.kind == "forest":
            self.layers.append((hills(rng, pal["mid"], CH * 0.74, 70), 0.3, 0, 0.0))
            self.layers.append((trees(rng, (62, 108, 70), 9, CH * 0.78, 100, "any"), 0.55, 0, 0.0))
            self.layers.append((mist(), 0.7, 0, 0.0))
            self.layers.append((trees(rng, pal["fg"], 6, CH * 0.92, 140), 1.0, 0, 0.0))
        else:
            self.layers.append((hills(rng, pal["mid"], CH * 0.74, 70), 0.3, 0, 0.0))
            sc = 1.0 if self.kind != "ridge" else 0.7
            fl, fx = fort_layer(rng, pal["fort"], CH * 0.78, scale=sc, cx=LW * (0.62 if self.kind != "ridge" else 0.48))
            self.layers.append((fl, 0.5, 0, 0.0))
            self.flag = (fx[0], fx[1], 0.5)
            self.layers.append((trees(rng, pal["fg"], 6, CH * 0.93, 130), 1.0, 0, 0.0))
        if self.kind == "night":
            self.flame = [(LW * 0.62 + o, CH * 0.78 - 52 + 6) for o in (-150, -50, 50, 150)]
        else:
            self.flame = []

    cast = "none"

    def render(self, t, persist=False):
        cam = math.sin(t * 0.42 + 0.6)                       # -1..1 slow pan
        im = self.sky.copy()
        d = ImageDraw.Draw(im)
        for (sx, sy, ph) in self.stars:                       # twinkling paper stars
            a = 0.55 + 0.45 * math.sin(t * 3 + ph)
            r = 2.2 * a + 0.6
            d.polygon([(sx, sy - r * 1.6), (sx + r * 0.5, sy), (sx, sy + r * 1.6), (sx - r * 0.5, sy)], fill=(255, 246, 214))
        if self.sun:
            sp = ease((t - 0.15) / 0.8) if not persist else 1.0
            s = self.sun.rotate(t * 6, resample=Image.BICUBIC) if self.kind != "night" else self.sun
            sx, sy = self.sun_xy
            im.paste(s, (int(sx - s.width / 2 + cam * -6), int(sy - s.height / 2 + (1 - sp) * 70)), s)
        for (cs, cx0, cy0, sp_, ph) in self.clouds:
            x = (cx0 - t * sp_) % (CW + 260) - 130
            im.paste(cs, (int(x), int(cy0 + 4 * math.sin(t * 0.9 + ph))), cs)
        order = 0
        for li, (spr, depth, yo, wv) in enumerate(self.layers):
            if li == len(self.layers) - 1 and self.cast != "none" and self.kind != "sea":
                draw_cast(im, self.cast, t, persist)
            pop = 1.0 if persist else back((t - 0.1 - order * 0.11) / 0.55)
            order += 1
            if pop <= 0.001:
                continue
            x = int(-70 - cam * 55 * depth + (math.sin(t * 0.8) * wv if wv else 0))
            y = int(yo + (1 - pop) * CH * 0.45)
            if (1 - pop) > 0.02 and pop < 1:
                tmp = spr
            else:
                tmp = spr
            im.paste(tmp, (x, y), tmp)
            if spr is self.layers[2][0] and self.ships:
                for (ss, sx2, sy2, dd) in self.ships:
                    bob = 4 * math.sin(t * 1.6 + sx2)
                    im.paste(ss, (int(sx2 - 70 - cam * 55 * dd + (1 - pop) * 0), int(sy2 + bob + (1 - pop) * CH * 0.4)), ss)
            if self.flag and abs(depth - self.flag[2]) < 1e-6 and spr is self.layers[2][0] if self.kind != "sea" else (self.flag and spr is self.layers[2][0]):
                fx, fy = self.flag[0], self.flag[1]
                self._flag(d, x + fx, y + fy, t)
        for (fx, fy) in self.flame:
            fl = 4 + 2 * math.sin(t * 9 + fx)
            ox = -70 - cam * 55 * 0.5
            d.polygon([(ox + fx, fy - 12 - fl), (ox + fx + 4, fy - 4), (ox + fx - 4, fy - 4)], fill=(255, 168, 56))
        return im

    @staticmethod
    def _flag(d, x, y, t):
        d.line((x, y - 4, x, y - 44), fill=(88, 60, 40), width=3)
        pts = []
        for i in range(0, 6):
            pts.append((x + i * 6, y - 44 + 1.8 * math.sin(t * 6 - i * 0.8) * (i / 5)))
        pts2 = [(p[0], p[1] + 20) for p in reversed(pts)]
        d.polygon(pts + [(x + 38, y - 33 + 1.5 * math.sin(t * 6 - 5))] + pts2, fill=SAFF)


_ART = {}


def get_art(kind, seed):
    key = (kind, seed)
    if key not in _ART:
        if len(_ART) > 24:
            _ART.clear()
        _ART[key] = Art(kind, seed)
    return _ART[key]


# ------------------------------------------------------------------ paper cards, chips, pins
@lru_cache(maxsize=512)
def card_sprite(w, h, fill=CREAM, rot=0.0, jitter=1, shade=105):
    rng = random.Random(w * 7 + h * 13 + jitter)
    pad = 26
    m, d = new_mask(w + pad * 2, h + pad * 2)
    pts = []
    for x in range(0, w + 1, 18):
        pts.append((pad + x, pad + rng.uniform(-1.3, 1.3)))
    for y in range(0, h + 1, 18):
        pts.append((pad + w + rng.uniform(-1.3, 1.3), pad + y))
    for x in range(w, -1, -18):
        pts.append((pad + x, pad + h + rng.uniform(-1.3, 1.3)))
    for y in range(h, -1, -18):
        pts.append((pad + rng.uniform(-1.3, 1.3), pad + y))
    d.polygon(pts, fill=255)
    spr = paperize(m, fill, shadow=7, blur=6, shade=shade, grain_k=0.22)
    if rot:
        spr = spr.rotate(rot, resample=Image.BICUBIC, expand=True)
    return spr


def put(im, spr, cx, cy, alpha=1.0, dy=0):
    x, y = int(cx - spr.width / 2), int(cy - spr.height / 2 + dy)
    if alpha >= 0.99:
        im.paste(spr, (x, y), spr)
    elif alpha > 0.02:
        a = spr.getchannel("A").point(lambda v: int(v * alpha))
        im.paste(spr, (x, y), a)


@lru_cache(maxsize=1024)
def text_sprite(s, kind, size, color, shadow=True):
    f = font(kind, size)
    w = int(tw(s, f)) + 16
    h = int(size * 1.7) + 8
    spr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(spr)
    if shadow:
        d.text((10, 6), s, font=f, fill=SHADOW + (120,))
    d.text((8, 4), s, font=f, fill=color)
    return spr


def text_c(im, cx, y, s, kind, size, color, alpha=1.0, shadow=False):
    spr = text_sprite(s, kind, size, color, shadow)
    put(im, spr, cx, y + spr.height / 2, alpha)


@lru_cache(maxsize=512)
def chip_sprite(word, size=44, rot=0.0, variant=0):
    f = font("serifb", size)
    w, h = int(tw(word, f)) + 36, int(size * 1.62)
    rng = random.Random(zlib.crc32(word.encode()) % 1000 + variant)
    col = tuple(max(0, min(255, c + rng.randint(-8, 8))) for c in TERRA)
    spr = card_sprite(w, h, col, 0.0, variant + 1, 120)
    d = ImageDraw.Draw(spr)
    d.text((spr.width / 2 - tw(word, f) / 2 + 1, spr.height / 2 - size * 0.84 + 3), word, font=f, fill=TERRA_D)
    d.text((spr.width / 2 - tw(word, f) / 2, spr.height / 2 - size * 0.84 + 1), word, font=f, fill=CREAM)
    return spr.rotate(rot, resample=Image.BICUBIC, expand=True) if rot else spr


def blurred_bg(art):
    im = art.render(1.5, True).resize((int(CW * H / CH * 0.62), int(H * 0.62)), Image.BILINEAR)
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s) + 2, int(im.height * s) + 2), Image.BILINEAR)
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((x0, y0, x0 + W, y0 + H)).filter(ImageFilter.GaussianBlur(26))
    dark = Image.new("RGB", (W, H), (30, 18, 12))
    return Image.blend(im, dark, 0.42)


# ------------------------------------------------------------------ info visuals (y 700 .. 940)
IY0, IY1 = 700, 945


def i_title(im, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.6, 0.2)
    kk = str(v.get("kicker", ""))
    big = str(v.get("big", ""))
    f, ls = fit_lines(big, "serifb", 54, 540, 2, 34)
    h = 80 + len(ls) * int(f.size * 1.5) + (36 if v.get("place") else 0)
    spr = card_sprite(580, h, CREAM, -1.2)
    cy = IY0 + h / 2 + 6
    put(im, spr, CX, cy, a, off)
    text_c(im, CX, cy - h / 2 + 28 + off, kk, "sansb", 28, TERRA + (255,), a)
    for j, s in enumerate(ls):
        text_c(im, CX, cy - h / 2 + 64 + j * int(f.size * 1.5) + off, s, "serifb", f.size, INKP + (255,), a)
    if v.get("place"):
        text_c(im, CX, cy + h / 2 - 50 + off, str(v["place"]), "serif", 26, (110, 80, 56, 255), a)


def i_fort(im, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.6, 0.2)
    spr = card_sprite(520, 150, CREAM, 1.0)
    cy = IY0 + 90
    put(im, spr, CX, cy, a, off)
    text_c(im, CX, cy - 62 + off, str(v.get("name", "")), "serifb", 56, INKP + (255,), a)
    sub = " — ".join(x for x in (str(v.get("year") or ""), str(v.get("note") or "")) if x)
    if sub:
        f, ls = fit_lines(sub, "sans", 28, 460, 1, 20)
        text_c(im, CX, cy + 22 + off, ls[0], "sans", f.size, (110, 80, 56, 255), a)
    d = ImageDraw.Draw(im)
    d.ellipse((CX - 9, int(cy - 82 + off), CX + 9, int(cy - 64 + off)), fill=(206, 58, 48), outline=(120, 30, 24))


def i_map(im, v, t, persist, S):
    places = [str(x) for x in (v.get("places") or [])][:5] or ["स्वराज्य"]
    d = ImageDraw.Draw(im)
    f = font("serifb", 36)
    ws = [int(tw(p, f)) + 40 for p in places]
    arrow = 38
    total = sum(ws) + arrow * (len(ws) - 1)
    scale = min(1.0, 630 / max(total, 1))
    x = CX - total * scale / 2
    y = IY0 + 70
    for i, p in enumerate(places):
        a, off = reveal(t, i, persist, 0.55, 0.45, 0.5)
        spr = chip_sprite(p, int(36 * scale), 0.0, i)
        put(im, spr, x + spr.width / 2, y, a, off)
        x += spr.width
        if i < len(places) - 1:
            ax = x + arrow * scale / 2
            d.polygon([(ax - 10, y - 11), (ax + 10, y), (ax - 10, y + 11)], fill=tuple(int(c * a + 40 * (1 - a)) for c in CREAM))
            x += arrow * scale


def i_timeline(im, v, t, persist, S):
    items = (v.get("items") or [])[:5]
    n = max(1, len(items))
    hh = min(64, 236 // n - 6)
    for i, it in enumerate(items):
        a, off = reveal(t, i, persist, 0.55, 0.5, 0.35)
        cy = IY0 + hh / 2 + 4 + i * (hh + 8)
        spr = card_sprite(590, hh, CREAM, (-0.6 if i % 2 else 0.6))
        put(im, spr, CX, cy, a, off)
        tab = card_sprite(120, hh - 8, TERRA, 0.0, 3)
        put(im, tab, CX - 295 + 78, cy, a, off)
        text_c(im, CX - 295 + 78, cy - hh * 0.36 + off, str(it.get("y", "")), "serifb", int(hh * 0.55), CREAM + (255,), a)
        f, ls = fit_lines(str(it.get("t", "")), "sansb", int(hh * 0.5), 400, 1, 18)
        text_c(im, CX + 80, cy - f.size * 0.82 + off, ls[0] if ls else "", "sansb", f.size, INKP + (255,), a)


def i_stat(im, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.7, 0.2)
    cy = IY0 + 100
    r = 98
    m, d = new_mask(2 * r + 40, 2 * r + 40)
    d.ellipse((20, 20, 20 + 2 * r, 20 + 2 * r), fill=255)
    img = Image.new("RGB", m.size, CREAM)
    di = ImageDraw.Draw(img)
    di.ellipse((20, 20, 20 + 2 * r, 20 + 2 * r), outline=TERRA, width=7)
    di.ellipse((34, 34, 6 + 2 * r, 6 + 2 * r), outline=(214, 178, 130), width=2)
    disc = paperize(m, img, shadow=8, blur=7, shade=115)
    put(im, disc, CX, cy, a, off)
    big = str(v.get("big", ""))
    f, ls = fit_lines(big, "serifb", 82, 170, 1, 30)
    text_c(im, CX, cy - f.size * 0.86 + off, ls[0], "serifb", f.size, INKP + (255,), a)
    a2, off2 = reveal(t, 2, persist, 0.3, 0.5, 0.5)
    lab = str(v.get("label", ""))
    f2, l2 = fit_lines(lab, "sansb", 30, 520, 1, 20)
    put(im, chip_sprite(l2[0], f2.size, 0.0, 5), CX, cy + r + 34, a2, off2)


def i_points(im, v, t, persist, S):
    items = [str(x) for x in (v.get("items") or [])][:4]
    n = max(1, len(items))
    hh = min(66, 236 // n - 8)
    d = ImageDraw.Draw(im)
    for i, s in enumerate(items):
        a, off = reveal(t, i, persist, 0.5, 0.5, 0.35)
        cy = IY0 + hh / 2 + 4 + i * (hh + 10)
        spr = card_sprite(580, hh, CREAM, (0.7 if i % 2 else -0.7), i + 1)
        put(im, spr, CX, cy, a, off)
        tab = card_sprite(hh - 6, hh - 6, TERRA, 0.0, 4)
        put(im, tab, CX - 290 + hh * 0.7, cy, a, off)
        text_c(im, CX - 290 + hh * 0.7, cy - hh * 0.38 + off, str(i + 1), "serifb", int(hh * 0.58), CREAM + (255,), a)
        f, ls = fit_lines(s, "sansb", int(hh * 0.5), 440, 1, 18)
        text_c(im, CX + 40, cy - f.size * 0.82 + off, ls[0], "sansb", f.size, INKP + (255,), a)


def i_people(im, v, t, persist, S):
    items = (v.get("items") or [])[:3]
    n = max(1, len(items))
    hh = min(112, 236 // n - 8)
    for i, it in enumerate(items):
        a, off = reveal(t, i, persist, 0.6, 0.5, 0.3)
        cy = IY0 + hh / 2 + 4 + i * (hh + 10)
        put(im, card_sprite(590, hh, CREAM, (0.6 if i % 2 else -0.6), i + 7), CX, cy, a, off)
        r = int(hh * 0.36)
        m, d = new_mask(2 * r + 20, 2 * r + 20)
        d.ellipse((10, 10, 10 + 2 * r, 10 + 2 * r), fill=255)
        img = Image.new("RGB", m.size, TERRA)
        di = ImageDraw.Draw(img)
        di.polygon([(r + 10, 10 + r * 0.45), (10 + r * 1.5, r + 10), (r + 10, 10 + r * 1.55), (10 + r * 0.5, r + 10)], fill=CREAM)
        put(im, paperize(m, img, shadow=4, blur=4, shade=90), CX - 295 + 20 + r + 20, cy, a, off)
        fx = CX - 295 + 20 + 2 * r + 46
        f, ls = fit_lines(str(it.get("n", "")), "serifb", int(hh * 0.4), 590 - (fx - (CX - 295)) - 20, 1, 20)
        text_c(im, fx + (590 - (fx - (CX - 295)) - 20) / 2 - 0, cy - hh * 0.38 + off + 0, ls[0], "serifb", f.size, INKP + (255,), a)
        f2, l2 = fit_lines(str(it.get("r", "")), "sans", int(hh * 0.27), 590 - (fx - (CX - 295)) - 20, 1, 16)
        text_c(im, fx + (590 - (fx - (CX - 295)) - 20) / 2, cy + hh * 0.06 + off, l2[0] if l2 else "", "sans", f2.size, (110, 80, 56, 255), a)


def i_scroll(im, v, t, persist, S):
    lines = [str(x) for x in (v.get("lines") or [])][:4]
    a, off = reveal(t, 0, persist, 0.3, 0.7, 0.2)
    n = max(1, len(lines))
    hh = 70 + n * 52
    spr = card_sprite(540, hh, CREAM, 0.0)
    cy = IY0 + hh / 2 + 6
    d = ImageDraw.Draw(im)
    open_h = max(8, hh * a)
    put(im, spr, CX, cy, a, 0)
    for yy in (cy - open_h / 2 + 8, cy + open_h / 2 - 8):
        rod = card_sprite(580, 22, (186, 132, 62), 0.0, 9, 120)
        put(im, rod, CX, yy, min(1.0, a * 2))
    for i, s in enumerate(lines):
        a2, off2 = reveal(t, i, persist, 0.5, 0.45, 0.7)
        text_c(im, CX, cy - n * 26 + i * 52 + 4 + off2 - 8, s, "serifb", 40, INKP + (255,), a2)


def i_outro(im, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.6, 0.2)
    put(im, card_sprite(560, 150, CREAM, -1.0), CX, IY0 + 78, a, off)
    text_c(im, CX, IY0 + 22 + off, CFG["brand"], "serifb", 60, INKP + (255,), a)
    text_c(im, CX, IY0 + 92 + off, "जय शिवराय", "serifb", 44, TERRA + (255,), a)
    a2, off2 = reveal(t, 2, persist, 0.3, 0.5, 0.6)
    nxt = str(v.get("next") or "").strip()
    y2 = IY0 + 200
    if nxt:
        f, ls = fit_lines("अगला: " + nxt, "sansb", 28, 560, 1, 20)
        put(im, chip_sprite(ls[0], 30, 0.0, 2), CX, y2, a2, off2)
        y2 += 62
    a3, off3 = reveal(t, 3, persist, 0.3, 0.5, 0.9)
    for k, s in enumerate(("सेव", "शेयर", "फ़ॉलो")):
        put(im, chip_sprite(s, 30, 0.0, 10 + k), CX + (k - 1) * 170, y2 - (0 if nxt else 8), a3, off3)


INFO = {"title": i_title, "fort": i_fort, "map": i_map, "timeline": i_timeline, "stat": i_stat,
        "points": i_points, "people": i_people, "scroll": i_scroll, "outro": i_outro}

DEFAULT_KIND = {"title": "fort", "fort": "fort", "map": "ridge", "timeline": "dawn", "stat": "dawn", "points": "fort",
                "people": "dawn", "scroll": "sea", "outro": "fort"}
SFX_KIND = {"sword": "ridge", "whisper": "night", "landslide": "forest", "birds": "dawn", "horse": "ridge"}


def scene_kind(sc):
    k = str(sc.get("scene") or "").lower()
    if k in KINDS:
        return k
    if sc.get("sfx") in SFX_KIND:
        return SFX_KIND[sc["sfx"]]
    return DEFAULT_KIND.get((sc.get("visual") or {}).get("type"), "fort")


# ------------------------------------------------------------------ word chips (appear phrase by phrase while the narrator speaks)
def chunk_words(text, per=3, max_chars=22):
    words, out, cur = text.split(), [], []
    for w in words:
        if cur and (len(cur) >= per or len(" ".join(cur + [w])) > max_chars):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def draw_chips(im, sub, t, dur, a_in=1.0):
    ch = chunk_words(sub)
    if not ch:
        return
    t0, t1 = 0.2, max(1.0, dur - 0.55)
    weights = [sum(len(w) + 1 for w in c) for c in ch]
    tot = float(sum(weights))
    acc, start = 0.0, []
    for w in weights:
        start.append(t0 + (t1 - t0) * acc / tot)
        acc += w
    idx = max(i for i, s in enumerate(start) if t >= s - 0.0001) if t >= start[0] else 0
    if t < start[0]:
        return
    s0 = start[idx]
    words = ch[idx]
    size = 44
    f = font("serifb", size)
    ws = [int(tw(w, f)) + 36 for w in words]
    rows, row, rw = [], [], 0
    for w, wd in zip(words, ws):
        if row and rw + wd + 10 > 640:
            rows.append(row)
            row, rw = [], 0
        row.append((w, wd))
        rw += wd + 10
    rows.append(row)
    y = 1010 - (len(rows) - 1) * 40
    k = 0
    for r in rows:
        total = sum(wd for _, wd in r) + 10 * (len(r) - 1)
        x = CX - total / 2
        for (w, wd) in r:
            e = back((t - s0 - k * 0.07) / 0.28)
            rot = random.Random(zlib.crc32(w.encode()) % 997).uniform(-3.2, 3.2)
            spr = chip_sprite(w, size, rot, k % 3)
            put(im, spr, x + wd / 2, y, min(1.0, e * 1.2), (1 - e) * 26)
            x += wd + 10
            k += 1
        y += 84


# ------------------------------------------------------------------ the frame
_BG = {}
_SHADOW = {}


def _card_shadow():
    if "s" not in _SHADOW:
        m = Image.new("L", (CW + 80, CH + 80), 0)
        ImageDraw.Draw(m).rounded_rectangle((40, 50, 40 + CW, 50 + CH), 26, fill=150)
        m = m.filter(ImageFilter.GaussianBlur(14))
        spr = Image.new("RGBA", m.size, SHADOW + (0,))
        spr.putalpha(m)
        _SHADOW["s"] = spr
        rm = Image.new("L", (CW, CH), 0)
        ImageDraw.Draw(rm).rounded_rectangle((0, 0, CW - 1, CH - 1), 24, fill=255)
        _SHADOW["mask"] = rm
    return _SHADOW["s"], _SHADOW["mask"]


def _draw_pins(card, v, t, persist):
    places = [str(x) for x in (v.get("places") or [])][:5]
    n = len(places)
    if not n:
        return
    d = ImageDraw.Draw(card)
    pts = []
    for i in range(n):
        f = i / max(1, n - 1)
        pts.append((70 + f * 500, 330 - f * 150 + math.sin(i * 2.0) * 36))
    prog = 1.0 if persist else ease((t - 0.5) / (0.6 * n))
    total = max(1, n - 1) * prog
    for i in range(n - 1):
        seg = max(0.0, min(1.0, total - i))
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        k = 0
        while k * 14 < L * seg:
            px, py = x0 + (x1 - x0) * k * 14 / L, y0 + (y1 - y0) * k * 14 / L
            d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(255, 244, 222))
            k += 1
    for i, (x, y) in enumerate(pts):
        a = 1.0 if persist else ease((total - (i - 0.3)) / 0.4)
        if a <= 0.05:
            continue
        r = 13
        yy = y - 12 * (1 - a) - 0
        d.line((x, yy, x, yy + 22), fill=(80, 54, 36), width=3)
        d.ellipse((x - r, yy - r - 10, x + r, yy + r - 10), fill=(214, 60, 48), outline=(120, 30, 24), width=2)
        tx = str(i + 1)
        d.text((x - tw(tx, font("sansb", 18)) / 2, yy - r - 10 + 1), tx, font=font("sansb", 18), fill=CREAM)


def draw_frame(spec, idx, t, gt, total, persist):
    sc = spec["scenes"][idx]
    n = len(spec["scenes"])
    dur = (spec.get("_durs") or [8.0] * n)[idx]
    kind = scene_kind(sc)
    seed = (zlib.crc32(str(spec.get("title", "")).encode()) % 997) * 31 + idx * 7
    art = get_art(kind, seed % 100000)
    art.cast = cast_kind(sc)
    bkey = (kind, seed % 100000)
    if bkey not in _BG:
        if len(_BG) > 24:
            _BG.clear()
        _BG[bkey] = blurred_bg(art)
    im = _BG[bkey].copy()
    # header
    d = ImageDraw.Draw(im)
    d.text((40, 36), CFG["brand"], font=font("serifb", 30), fill=CREAM)
    tag = str(spec.get("tag", "")).strip()[:16]
    if spec.get("part"):
        tag = f"भाग {spec['part'][0]}/{spec['part'][1]}"
    f = font("sansb", 24)
    if tag:
        wd = tw(tag, f) + 34
        put(im, chip_sprite(tag, 24, 0.0, 6), W - 40 - wd / 2 + 8, 52)
    d.line((40, 100, W - 40, 100), fill=(255, 244, 222, 60), width=2)
    d.line((40, 100, 40 + (W - 80) * min(1.0, gt / max(total, 0.1)), 100), fill=GOLDY, width=4)
    # diorama card
    sh, mask = _card_shadow()
    cx0, cy0 = (W - CW) // 2, 126
    slide = ease(t / 0.5) if not persist else 1.0
    im.paste(sh, (cx0 - 40, cy0 - 40 + int((1 - slide) * 30)), sh)
    card = art.render(t, persist).convert("RGBA")
    v = sc.get("visual") or {}
    if v.get("type") == "map":
        _draw_pins(card, v, t, persist)
    border = ImageDraw.Draw(card)
    rounded = Image.new("RGB", (CW, CH))
    rounded.paste(card.convert("RGB"))
    im.paste(rounded, (cx0, cy0 + int((1 - slide) * 30)), mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((cx0, cy0 + int((1 - slide) * 30), cx0 + CW - 1, cy0 + CH - 1 + int((1 - slide) * 30)), 24, outline=CREAM, width=5)
    # headline
    a = ease(t / 0.35)
    head = str(sc.get("head", ""))
    words = []
    for p in re.split(r"(\*\*.+?\*\*)", head):
        if not p:
            continue
        hl = p.startswith("**") and p.endswith("**") and len(p) > 4
        for w in (p[2:-2] if hl else p).split():
            words.append((w, hl))
    fh = font("serifb", 52)
    lines, cur, cw_ = [], [], 0
    sp = tw(" ", fh)
    for w, hl in words:
        wl = tw(w, fh)
        if cur and cw_ + sp + wl > 620:
            lines.append(cur)
            cur, cw_ = [], 0
        cw_ += (sp if cur else 0) + wl
        cur.append((w, hl, wl))
    if cur:
        lines.append(cur)
    y = 545 + (0 if len(lines) > 1 else 22)
    for ln in lines[:2]:
        wid = sum(x[2] for x in ln) + sp * (len(ln) - 1)
        x = CX - wid / 2
        for w, hl, wl in ln:
            spr = text_sprite(w, "serifb", 52, (GOLDY if hl else CREAM) + (255,), True)
            put(im, spr, x + wl / 2, y + spr.height / 2 - 2, a, (1 - a) * 18)
            x += wl + sp
        y += 80
    # info + chips
    fn = INFO.get(v.get("type"))
    if fn:
        fn(im, v, t, persist, sc)
    sub = str(sc.get("sub", "")).strip()
    if sub and v.get("type") != "outro":
        draw_chips(im, sub, t, dur)
    return im


# ------------------------------------------------------------------ characters: Maharaj on horseback, mavle marching with bhagwa flags
class Dual:
    """draw one shape on both the cut-out mask and the colour layer"""
    def __init__(self, w, h):
        self.m, self.dm = new_mask(w, h)
        self.img = Image.new("RGB", (w, h), (0, 0, 0))
        self.di = ImageDraw.Draw(self.img)

    def poly(self, pts, c):
        self.dm.polygon(pts, fill=255)
        self.di.polygon(pts, fill=c)

    def ell(self, box, c):
        self.dm.ellipse(box, fill=255)
        self.di.ellipse(box, fill=c)

    def line(self, pts, c, w):
        self.dm.line(pts, fill=255, width=w, joint="curve")
        self.di.line(pts, fill=c, width=w, joint="curve")
        for p in (pts[0], pts[-1]):
            self.ell((p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2), c)

    def done(self, **kw):
        return paperize(self.m, self.img, **kw)


HORSE = (112, 70, 48)
HORSE_D = (82, 50, 34)
JAMA = (244, 232, 206)
TURB = (170, 46, 40)
POLE = (92, 62, 40)
GRASS_SH = (60, 96, 60)


def _flag(dd, px, py, ph, size=1.0):
    """bhagwa jhenda: swallow-tailed saffron pennant fluttering to the left of the pole"""
    L = 46 * size
    top = [(px, py)]
    n = 6
    for i in range(1, n + 1):
        top.append((px - L * i / n, py + 3 * math.sin(ph * 2 * math.pi * 2 - i * 0.9) * (i / n) + 2 * i / n))
    bot = [(px - L * i / n, py + 20 * size + 3 * math.sin(ph * 2 * math.pi * 2 - i * 0.9) * (i / n) + 2 * i / n) for i in range(n, 0, -1)]
    notch = (px - L * 0.72, py + 10 * size + 3 * math.sin(ph * 12.5))
    dd.poly(top + [(px - L, py + 10 * size)] + bot[:1] + [notch] + bot[1:] + [(px, py + 20 * size)], SAFF)


@lru_cache(maxsize=64)
def rider_sprite(bucket, nb=16):
    ph = bucket / nb
    w, h = 270, 250
    dd = Dual(w, h)
    ang = ph * 2 * math.pi
    oy = 78
    # legs (walk gait: diagonal pairs)
    for hx, off in ((78, 0.0), (92, math.pi), (150, math.pi * 0.5), (164, math.pi * 1.5)):
        sw = math.sin(ang + off)
        lift = max(0.0, math.cos(ang + off))
        hip = (hx, oy + 120)
        knee = (hx + 12 * sw, oy + 148 - 8 * lift)
        foot = (hx + 20 * sw - 4 * lift, oy + 176 - 14 * lift)
        dd.line([hip, knee, foot], HORSE_D, 8)
        dd.ell((foot[0] - 6, foot[1] - 3, foot[0] + 6, foot[1] + 4), (50, 32, 22))
    # tail
    ts = 6 * math.sin(ang * 2)
    dd.poly([(64, oy + 96), (36 + ts, oy + 120), (24 + ts * 1.5, oy + 160), (44 + ts, oy + 150), (60, oy + 120)], HORSE_D)
    # body, neck, head
    dd.ell((58, oy + 86, 186, oy + 140), HORSE)
    dd.poly([(168, oy + 100), (190, oy + 48), (214, oy + 38), (222, oy + 52), (200, oy + 110)], HORSE)
    bob = 2 * math.sin(ang * 2)
    dd.poly([(204, oy + 38 + bob), (246, oy + 66 + bob), (240, oy + 82 + bob), (212, oy + 68 + bob), (200, oy + 58 + bob)], HORSE)
    dd.poly([(206, oy + 38 + bob), (210, oy + 22 + bob), (216, oy + 40 + bob)], HORSE_D)
    dd.poly([(190, oy + 50), (180, oy + 62), (196, oy + 80), (204, oy + 62)], HORSE_D)       # mane
    dd.poly([(110, oy + 84), (150, oy + 84), (146, oy + 96), (114, oy + 96)], (170, 40, 36))   # saddle cloth
    # rider
    rb = 1.6 * math.sin(ang * 2 + 0.6)
    dd.poly([(116, oy + 90), (150, oy + 90), (146, oy + 34 + rb), (122, oy + 34 + rb)], JAMA)  # jama
    dd.line([(128, oy + 90), (140, oy + 112)], JAMA, 10)                                         # leg
    dd.ell((126, oy + 8 + rb, 146, oy + 32 + rb), (206, 156, 112))                             # face (no features)
    dd.ell((120, oy - 4 + rb, 152, oy + 18 + rb), TURB)                                         # turban
    dd.poly([(122, oy + 6 + rb), (104, oy + 14 + rb), (108, oy + 24 + rb), (124, oy + 16 + rb)], TURB)
    dd.line([(144, oy + 46 + rb), (164, oy + 20 + rb)], JAMA, 8)                                # raised arm
    px = 166
    dd.line([(px, oy + 96), (px, oy - 70)], POLE, 4)                                            # pole
    _flag(dd, px, oy - 70, ph, 1.3)
    return dd.done(shadow=7, blur=5, shade=100, grain_k=0.22)


@lru_cache(maxsize=64)
def mavla_sprite(bucket, nb=16, flagged=True, i=0):
    ph = (bucket / nb + i * 0.31) % 1.0
    ang = ph * 2 * math.pi
    w, h = 90, 190
    dd = Dual(w, h)
    cx, gy = 44, 172
    bob = 2 * abs(math.sin(ang))
    for off in (0.0, math.pi):
        sw = math.sin(ang + off)
        lift = max(0.0, math.cos(ang + off))
        hip = (cx + (3 if off else -3), gy - 62 - bob)
        foot = (hip[0] + 16 * sw, gy - 3 - 7 * lift)
        dd.line([hip, ((hip[0] + foot[0]) / 2, gy - 30 - 3 * lift), foot], (232, 218, 190), 8)
    dd.poly([(cx - 15, gy - 62 - bob), (cx + 15, gy - 62 - bob), (cx + 12, gy - 112 - bob), (cx - 12, gy - 112 - bob)], (236, 150, 60) if i % 2 else (206, 96, 64))
    dd.ell((cx - 9, gy - 134 - bob, cx + 9, gy - 112 - bob), (206, 156, 112))
    dd.ell((cx - 11, gy - 142 - bob, cx + 11, gy - 124 - bob), SAFF if i % 2 else TURB)
    dd.line([(cx + 8, gy - 104 - bob), (cx + 20, gy - 82 - bob)], (236, 150, 60), 7)
    px = cx + 22
    if flagged:
        dd.line([(px, gy - 6), (px, 20)], POLE, 3)
        _flag(dd, px, 20, ph, 0.85)
    else:
        dd.line([(px, gy - 6), (px, 40)], POLE, 3)
        dd.poly([(px - 4, 42), (px + 4, 42), (px, 20)], (190, 196, 204))
    return dd.done(shadow=5, blur=4, shade=90, grain_k=0.2)


def cast_kind(sc):
    c = str(sc.get("cast") or "").lower()
    if c in ("rider", "mavle", "none"):
        return c
    if sc.get("sfx") == "horse":
        return "rider"
    if sc.get("sfx") in ("sword", "march"):
        return "mavle"
    return "none"


RIDER_T, MARCH_T = 1.55, 0.9


def draw_cast(im, cast, t, persist):
    gy = int(CH * 0.90)
    if cast == "rider":
        b = int((t % RIDER_T) / RIDER_T * 16) % 16
        spr = rider_sprite(b)
        prog = (0.18 + t * 0.14) % 1.0
        x = int(-spr.width + prog * (CW + spr.width + 40))
        im.paste(spr, (x, gy - spr.height + 14 + int(2 * math.sin(t * 4.05 * 2))), spr)
    elif cast == "mavle":
        b = int((t % MARCH_T) / MARCH_T * 16) % 16
        prog = (0.2 + t * 0.1) % 1.0
        base = -300 + prog * (CW + 360)
        for k in range(5):
            spr = mavla_sprite(b, 16, k % 2 == 0, k)
            im.paste(spr, (int(base + k * 62 + (k % 2) * 9), gy - spr.height + 12 + (k % 2) * 6), spr)
