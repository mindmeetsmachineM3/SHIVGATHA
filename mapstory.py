"""
Shivgatha 'on a map' theme (THEME=map): dark 3-D style map of India, states rise in saffron as Swarajya grows, forts pop up, routes glow,
date + place labels, a short callout per scene and word-by-word highlighted Hinglish subtitles. Voice = Hindi (Devanagari script is sent to the TTS),
subtitles = Hinglish (Roman). Facts come from a web-searched FACT SHEET; the script may use only those facts.
Map data: Natural Earth (public domain), assets/india_states.json. Modern state outlines are used only as a backdrop.
"""
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).parent
W, H = 720, 1280
BG = (11, 15, 27)
OFF_TOP, OFF_SIDE = (33, 41, 61), (20, 26, 42)
ON_TOP, ON_SIDE = (222, 118, 32), (142, 66, 18)
ORANGE, WHITE, DIM, GREY = (255, 156, 56), (244, 244, 248), (112, 120, 140), (150, 158, 176)
BRAND = os.getenv("BRAND_NAME_MAP") or "SHIVGATHA ON A MAP"

_STATES = None


def states():
    global _STATES
    if _STATES is None:
        d = json.loads((BASE / "assets" / "india_states.json").read_text(encoding="utf-8"))
        _STATES = {k: [[tuple(p) for p in r] for r in v] for k, v in d.items()}
        for k, v in _STATES.items():
            la = [p[1] for r in v for p in r]
            lo = [p[0] for r in v for p in r]
            _STATES[k] = {"rings": v, "bbox": (min(lo), min(la), max(lo), max(la)), "lat": sum(la) / len(la)}
    return _STATES


# ------------------------------------------------------------------ gazetteer (the AI may only use these places, so coordinates are always right)
GAZ = {
    "raigad": ("RAIGAD", 18.2347, 73.4403, "Maharashtra"), "rajgad": ("RAJGAD", 18.2465, 73.6823, "Maharashtra"), "torna": ("TORNA", 18.2760, 73.6226, "Maharashtra"),
    "sinhagad": ("SINHAGAD", 18.3664, 73.7556, "Maharashtra"), "purandar": ("PURANDAR", 18.2822, 73.9754, "Maharashtra"), "pune": ("PUNE", 18.5204, 73.8567, "Maharashtra"),
    "shivneri": ("SHIVNERI", 19.1998, 73.8607, "Maharashtra"), "lohagad": ("LOHAGAD", 18.7106, 73.4764, "Maharashtra"), "pratapgad": ("PRATAPGAD", 17.9362, 73.5775, "Maharashtra"),
    "panhala": ("PANHALA", 16.8118, 74.1103, "Maharashtra"), "vishalgad": ("VISHALGAD", 16.9065, 73.7135, "Maharashtra"), "kolhapur": ("KOLHAPUR", 16.7050, 74.2433, "Maharashtra"),
    "satara": ("SATARA", 17.6805, 74.0183, "Maharashtra"), "sindhudurg": ("SINDHUDURG", 16.0427, 73.4605, "Maharashtra"), "janjira": ("MURUD-JANJIRA", 18.2993, 72.9648, "Maharashtra"),
    "suvarnadurg": ("SUVARNADURG", 17.8157, 73.0969, "Maharashtra"), "vijaydurg": ("VIJAYDURG", 16.5639, 73.3306, "Maharashtra"), "kalyan": ("KALYAN", 19.2437, 73.1355, "Maharashtra"),
    "nashik": ("NASHIK", 19.9975, 73.7898, "Maharashtra"), "ahmednagar": ("AHMEDNAGAR", 19.0948, 74.7480, "Maharashtra"), "aurangabad": ("AURANGABAD", 19.8762, 75.3433, "Maharashtra"),
    "ratnagiri": ("RATNAGIRI", 16.9902, 73.3120, "Maharashtra"), "surat": ("SURAT", 21.1702, 72.8311, "Gujarat"), "agra": ("AGRA", 27.1767, 78.0081, "Uttar Pradesh"),
    "delhi": ("DELHI", 28.6139, 77.2090, "Delhi"), "burhanpur": ("BURHANPUR", 21.3100, 76.2300, "Madhya Pradesh"), "bijapur": ("BIJAPUR", 16.8302, 75.7100, "Karnataka"),
    "belgaum": ("BELGAUM", 15.8497, 74.4977, "Karnataka"), "hubli": ("HUBLI", 15.3647, 75.1240, "Karnataka"), "koppal": ("KOPPAL", 15.3500, 76.1550, "Karnataka"),
    "karwar": ("KARWAR", 14.8137, 74.1290, "Karnataka"), "bengaluru": ("BENGALURU", 12.9716, 77.5946, "Karnataka"), "golconda": ("GOLCONDA", 17.3833, 78.4011, "Telangana"),
    "srisailam": ("SRISAILAM", 16.0740, 78.8680, "Andhra Pradesh"), "kurnool": ("KURNOOL", 15.8281, 78.0373, "Andhra Pradesh"), "gingee": ("GINGEE", 12.2530, 79.4170, "Tamil Nadu"),
    "vellore": ("VELLORE", 12.9165, 79.1325, "Tamil Nadu"), "thanjavur": ("THANJAVUR", 10.7870, 79.1378, "Tamil Nadu"), "chennai": ("MADRAS (CHENNAI)", 13.0827, 80.2707, "Tamil Nadu"),
    "goa": ("GOA", 15.4909, 73.8278, "Goa"),
}
GAZ_LIST = ", ".join(f"{k} ({v[0].title()})" for k, v in GAZ.items())
VIEW_SPAN = {"india": 27.0, "wide": 15.0, "mid": 8.5, "close": 3.8}
KINDS = ("fort", "city", "battle", "none")

# ------------------------------------------------------------------ fonts
_F = {}


def font(kind, size):
    k = (kind, size)
    if k not in _F:
        p = {"b": "Poppins-Bold.ttf", "m": "Poppins-Medium.ttf"}[kind]
        _F[k] = ImageFont.truetype(str(BASE / "fonts" / p), size)
    return _F[k]


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def lerpc(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(3))


# ------------------------------------------------------------------ camera + projection
TILT = 0.66


class Cam:
    def __init__(self, lat, lon, span):
        self.lat, self.lon, self.span = lat, lon, span
        self.s = W / span / 0.95                     # px per degree of longitude
        self.cy = 500

    def xy(self, lon, lat):
        return (W / 2 + (lon - self.lon) * self.s * 0.95, self.cy + (self.lat - lat) * self.s * TILT)


def scene_cam(sc):
    p = GAZ.get(sc.get("place"))
    span = VIEW_SPAN.get(sc.get("view"), 15.0)
    if sc.get("view") == "india" or not p:
        return (21.0, 79.0, VIEW_SPAN["india"]) if sc.get("view") == "india" else (17.5, 76.5, span)
    return (p[1], p[2], span)


def cams(spec):
    if "_cams" not in spec:
        spec["_cams"] = [scene_cam(s) for s in spec["scenes"]]
    return spec["_cams"]


# ------------------------------------------------------------------ the map
_BASE = {"key": None, "img": None}


def draw_map(cam, hl):
    """hl = {state: 0..1 saffron amount}. cached while nothing moves."""
    key = (round(cam.lat, 3), round(cam.lon, 3), round(cam.span, 2), tuple(sorted((k, round(v, 2)) for k, v in hl.items())))
    if _BASE["key"] == key:
        return _BASE["img"].copy()
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")
    px = 1.0 / cam.s
    order = sorted(states().items(), key=lambda kv: -kv[1]["lat"])
    for name, st in order:
        x0, y0, x1, y1 = st["bbox"]
        sx0, sy1 = cam.xy(x0, y0)
        sx1, sy0 = cam.xy(x1, y1)
        if sx1 < -40 or sx0 > W + 40 or sy1 < -60 or sy0 > H + 60:
            continue
        a = hl.get(name, 0.0)
        top, side = lerpc(OFF_TOP, ON_TOP, a), lerpc(OFF_SIDE, ON_SIDE, a)
        depth = int(lerp(3, 9, a) * max(.6, min(1.8, 14 / cam.span + .2)))
        for ring in st["rings"]:
            pts = [cam.xy(lon, lat) for lon, lat in ring]
            for k in range(depth, 0, -1):
                d.polygon([(x, y + k) for x, y in pts], fill=side)
            d.polygon(pts, fill=top, outline=lerpc((60, 72, 100), (255, 176, 90), a), width=1)
    _BASE["key"], _BASE["img"] = key, im
    return im.copy()


# ------------------------------------------------------------------ icons
_ICO = {}


def fort_icon(size):
    if size in _ICO:
        return _ICO[size]
    k = 3
    s = size * k
    im = Image.new("RGBA", (s, int(s * 1.25)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (52, 38, 30)
    cx, by = s / 2, s * 1.05
    d.ellipse((cx - s * .5, by - s * .2, cx + s * .5, by + s * .2), fill=(30, 58, 104, 170))                      # moat
    d.polygon([(cx - s * .46, by), (cx - s * .3, by - s * .36), (cx - s * .16, by - s * .3), (cx - s * .06, by - s * .62), (cx + s * .08, by - s * .56), (cx + s * .2, by - s * .42), (cx + s * .34, by - s * .3), (cx + s * .46, by)],
              fill=(156, 124, 96), outline=ink, width=k)                                                       # rocky hill
    d.polygon([(cx - s * .06, by - s * .62), (cx + s * .08, by - s * .56), (cx + s * .2, by - s * .42), (cx + s * .34, by - s * .3), (cx + s * .46, by), (cx + s * .1, by - s * .02), (cx - s * .02, by - s * .3)], fill=(184, 150, 118))
    d.ellipse((cx - s * .44, by - s * .15, cx + s * .44, by + s * .1), outline=(226, 212, 186), width=int(k * 2.4))   # wall ring
    for ang in (200, 250, 290, 340, 20, 70, 110, 160):                                                         # towers on the ring
        tx, ty = cx + math.cos(math.radians(ang)) * s * .44, by - s * .02 + math.sin(math.radians(ang)) * s * .12
        d.rectangle((tx - s * .035, ty - s * .09, tx + s * .035, ty + s * .01), fill=(226, 212, 186), outline=ink, width=k // 2 + 1)
    d.rectangle((cx - s * .1, by - s * .86, cx + s * .1, by - s * .55), fill=(206, 172, 138), outline=ink, width=k)    # keep
    d.rectangle((cx - s * .13, by - s * .9, cx + s * .13, by - s * .84), fill=(226, 212, 186), outline=ink, width=k)
    d.line((cx, by - s * .9, cx, by - s * 1.18), fill=ink, width=k + 1)
    d.polygon([(cx, by - s * 1.18), (cx + s * .32, by - s * 1.07), (cx, by - s * .97)], fill=(255, 122, 18), outline=ink)   # saffron flag
    _ICO[size] = im.resize((size, int(size * 1.25)), Image.LANCZOS)
    return _ICO[size]


def city_icon(size):
    key = ("c", size)
    if key in _ICO:
        return _ICO[key]
    k = 3
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((s * .15, s * .15, s * .85, s * .85), fill=(255, 190, 90), outline=(255, 244, 220), width=k * 2)
    d.ellipse((s * .38, s * .38, s * .62, s * .62), fill=(120, 60, 10))
    _ICO[key] = im.resize((size, size), Image.LANCZOS)
    return _ICO[key]


def battle_icon(size):
    key = ("b", size)
    if key in _ICO:
        return _ICO[key]
    k = 3
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((s * .05, s * .05, s * .95, s * .95), fill=(190, 30, 36, 150))
    d.line((s * .25, s * .25, s * .75, s * .75), fill=(255, 240, 230), width=k * 5)
    d.line((s * .75, s * .25, s * .25, s * .75), fill=(255, 240, 230), width=k * 5)
    _ICO[key] = im.resize((size, size), Image.LANCZOS)
    return _ICO[key]


def put(im, spr, cx, cy, a=1.0):
    if a < 1:
        spr = spr.copy()
        spr.putalpha(spr.getchannel("A").point(lambda v: int(v * a)))
    im.paste(spr, (int(cx - spr.width / 2), int(cy - spr.height)), spr)


def glow(im, cx, cy, r, col, a):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for k in range(5, 0, -1):
        rr = r * (1 + .22 * k)
        d.ellipse((cx - rr, cy - rr * TILT, cx + rr, cy + rr * TILT), outline=col + (int(a * 60 / k),), width=3)
    im.paste(ov, (0, 0), ov)


# ------------------------------------------------------------------ text helpers
def txt_c(d, cx, y, s, f, fill, anchor="mt"):
    d.text((cx, y), s, font=f, fill=fill, anchor=anchor)


def wrap(d, s, f, mw):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= mw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def pill(im, cx, cy, s, f, fill=(10, 13, 24, 225), outline=(255, 176, 90), a=1.0):
    d0 = ImageDraw.Draw(im)
    w = int(d0.textlength(s, font=f)) + 44
    h = f.size + 26
    ov = Image.new("RGBA", (w + 6, h + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle((3, 3, w + 3, h + 3), h // 2, fill=fill, outline=outline + (int(255 * a),), width=2)
    d.text((w / 2 + 3, h / 2 + 3), s, font=f, fill=WHITE + (int(255 * a),), anchor="mm")
    im.paste(ov, (int(cx - w / 2 - 3), int(cy - h / 2 - 3)), ov)


def two_tone(d, cx, y, s, f, c1, c2):
    """'Bhagyanagar · 1677': first part in saffron, rest white (split at the dot)"""
    if "·" in s:
        a, b = [x.strip() for x in s.split("·", 1)]
        wa, wb, wd = d.textlength(a, font=f), d.textlength(b, font=f), d.textlength("  ·  ", font=f)
        x = cx - (wa + wb + wd) / 2
        d.text((x, y), a, font=f, fill=c1, anchor="lt")
        d.text((x + wa, y), "  ·  ", font=f, fill=GREY, anchor="lt")
        d.text((x + wa + wd, y), b, font=f, fill=c2, anchor="lt")
    else:
        d.text((cx, y), s, font=f, fill=c1, anchor="mt")


def subtitle(im, sub, t, dur):
    """whole line shown, words turn white as they are spoken, the current one saffron"""
    words = sub.split()
    if not words:
        return
    d = ImageDraw.Draw(im, "RGBA")
    f = font("b", 33)
    lines = wrap(d, sub, f, 600)
    start, end = 0.2, max(1.0, dur - 0.45)
    wt = [len(w) + 2 for w in words]
    tot = sum(wt)
    acc, marks = 0.0, []
    for w in wt:
        marks.append(start + (end - start) * acc / tot)
        acc += w
    cur = max([i for i, m in enumerate(marks) if t >= m] or [-1])
    lh = 46
    y = 905 - (len(lines) - 2) * lh / 2 if len(lines) > 2 else 920
    idx = 0
    for ln in lines:
        wd = d.textlength(ln, font=f)
        x = W / 2 - wd / 2
        for w in ln.split():
            col = ORANGE if idx == cur else (WHITE if idx < cur else (110, 116, 134))
            d.text((x + 1, y + 2), w, font=f, fill=(0, 0, 0, 160))
            d.text((x, y), w, font=f, fill=col)
            x += d.textlength(w + " ", font=f)
            idx += 1
        y += lh


# ------------------------------------------------------------------ one frame
def highlight_state(spec, i, t):
    """cumulative saffron states; the ones added in this scene fade in"""
    hl = {}
    for j in range(i + 1):
        for s in spec["scenes"][j].get("add", []):
            if s in states():
                hl[s] = 1.0 if j < i else max(hl.get(s, 0), ease((t - .5) / 1.0))
    return hl


def draw_frame(spec, idx, t, gt, total, persist=False):
    sc = spec["scenes"][idx]
    durs = spec.get("_durs") or [6] * len(spec["scenes"])
    dur = durs[idx]
    cs = cams(spec)
    prev = cs[idx - 1] if idx else cs[0]
    k = ease(t / 1.5) if idx else 1.0
    cam = Cam(lerp(prev[0], cs[idx][0], k), lerp(prev[1], cs[idx][1], k), math.exp(lerp(math.log(prev[2]), math.log(cs[idx][2]), k)))
    im = draw_map(cam, highlight_state(spec, idx, t))
    d = ImageDraw.Draw(im, "RGBA")
    # earlier places as small dots, earlier routes dim
    for j in range(idx):
        s = spec["scenes"][j]
        r = s.get("route") or []
        for a, b in zip(r, r[1:]):
            _route(im, cam, a, b, 1.0, dim=True)
        if s.get("place") in GAZ and s.get("kind") in ("fort", "city", "battle"):
            x, y = cam.xy(GAZ[s["place"]][2], GAZ[s["place"]][1])
            if 0 < x < W and 0 < y < H:
                put(im, city_icon(12), x, y + 6, .8)
    # this scene's route
    r = sc.get("route") or []
    if len(r) >= 2:
        legs = len(r) - 1
        p = ease((t - .6) / max(1.5, dur * .6))
        for n, (a, b) in enumerate(zip(r, r[1:])):
            _route(im, cam, a, b, max(0.0, min(1.0, p * legs - n)))
    # this scene's marker
    if sc.get("place") in GAZ and sc.get("kind") in ("fort", "city", "battle"):
        name, lat, lon, _st = GAZ[sc["place"]]
        x, y = cam.xy(lon, lat)
        pop = ease((t - .5) / .6)
        size = int(max(46, min(120, 520 / cam.span * 2.2))) if sc["kind"] == "fort" else int(max(26, min(56, 300 / cam.span * 2)))
        if pop > 0:
            glow(im, x, y, size * .55 * pop, (255, 176, 80), pop)
            icon = {"fort": fort_icon, "city": city_icon, "battle": battle_icon}[sc["kind"]](max(10, int(size * pop)))
            put(im, icon, x, y + (icon.height * .1 if sc["kind"] == "fort" else icon.height / 2))
            d = ImageDraw.Draw(im, "RGBA")
            lab = sc.get("label") or name
            ty = y - (size * 1.35 if sc["kind"] == "fort" else size * .9) - 34
            d.text((x, ty), lab, font=font("b", 20), fill=WHITE + (int(255 * pop),), anchor="mt")
            if sc.get("sublabel"):
                d.text((x, ty + 22), sc["sublabel"], font=font("m", 15), fill=(190, 198, 214, int(255 * pop)), anchor="mt")
    # callout / card / stat
    if sc.get("callout") and t > 1.1:
        pill(im, W / 2, 772, sc["callout"], font("b", 18), a=ease((t - 1.1) / .5))
    if sc.get("card") and t > .9:
        _card(im, sc["card"], ease((t - .9) / .6))
    if sc.get("stat") and t > .6:
        a = ease((t - .6) / .6)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle((90, 610, 630, 760), 22, fill=(10, 13, 24, int(232 * a)), outline=ORANGE + (int(255 * a),), width=2)
        d.text((W / 2, 668), str(sc["stat"].get("value", "")), font=font("b", 66), fill=ORANGE + (int(255 * a),), anchor="mm")
        d.text((W / 2, 729), str(sc["stat"].get("label", "")).upper(), font=font("b", 15), fill=WHITE + (int(255 * a),), anchor="mm")
    # header (dark band so the text stays readable over saffron states)
    band = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for yy in range(150):
        bd.line((0, yy, W, yy), fill=(11, 15, 27, int(215 * (1 - yy / 150) ** 1.2)))
    im.paste(band, (0, 0), band)
    d = ImageDraw.Draw(im, "RGBA")
    if sc.get("type") == "outro":
        _outro(im, spec, t)
    else:
        d.text((W / 2, 20), " ".join(BRAND), font=font("b", 11), fill=(120, 128, 150), anchor="mt")
        head = sc.get("head") or ""
        if idx == 0 and head:
            f = font("b", 36)
            lines = wrap(d, head, f, 640)
            y = 54
            for ln in lines:
                d.text((W / 2, y), ln, font=f, fill=WHITE, anchor="mt")
                y += 46
        elif head:
            two_tone(d, W / 2, 50, head, font("b", 28), ORANGE, WHITE)
    # fade at the bottom for the subtitle
    shade = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for yy in range(420):
        sd.line((0, yy, W, yy), fill=(11, 15, 27, int(235 * (yy / 420) ** 1.3)))
    im.paste(shade, (0, 860), shade)
    d = ImageDraw.Draw(im, "RGBA")
    if sc.get("type") != "outro":
        subtitle(im, sc.get("sub") or sc["say"], t, dur)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((W / 2, 1248), "Modern state outlines shown for reference only", font=font("m", 11), fill=(86, 94, 114), anchor="mt")
    d.rectangle((0, H - 6, W, H), fill=(30, 36, 54))
    d.rectangle((0, H - 6, int(W * (gt) / max(total, 1)), H), fill=ORANGE)
    return im


def _route(im, cam, a, b, p, dim=False):
    if a not in GAZ or b not in GAZ or p <= 0:
        return
    x0, y0 = cam.xy(GAZ[a][2], GAZ[a][1])
    x1, y1 = cam.xy(GAZ[b][2], GAZ[b][1])
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 - abs(x1 - x0) * .12 - abs(y1 - y0) * .05
    pts = []
    n = 40
    for i in range(int(n * p) + 1):
        u = i / n
        pts.append(((1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u * u * x1, (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u * u * y1))
    if len(pts) < 2:
        return
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    col = (255, 190, 90)
    if dim:
        d.line(pts, fill=col + (110,), width=3)
    else:
        d.line(pts, fill=col + (70,), width=11)
        d.line(pts, fill=col + (255,), width=4)
        hx, hy = pts[-1]
        d.ellipse((hx - 8, hy - 8, hx + 8, hy + 8), fill=(255, 244, 210, 255), outline=col + (255,), width=3)
    im.paste(ov, (0, 0), ov)


def _card(im, card, a):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x0, y0, x1, y1 = 60, 540, 660, 720
    d.rounded_rectangle((x0, y0, x1, y1), 12, fill=(238, 224, 190, int(250 * a)), outline=(120, 90, 50, int(255 * a)), width=2)
    d.text((x0 + 24, y0 + 18), str(card.get("label", "")).upper(), font=font("b", 12), fill=(130, 90, 40, int(255 * a)))
    f = font("m", 16)
    lines = wrap(d, str(card.get("text", "")), f, x1 - x0 - 48)[:6]
    y = y0 + 46
    for ln in lines:
        d.text((x0 + 24, y), ln, font=f, fill=(50, 34, 20, int(255 * a)))
        y += 24
    im.paste(ov, (0, 0), ov)


def _outro(im, spec, t):
    d = ImageDraw.Draw(im, "RGBA")
    a = ease(t / .7)
    d.text((W / 2, 110), "SHIVGATHA", font=font("b", 44), fill=ORANGE + (int(255 * a),), anchor="mt")
    pill(im, W / 2, 205, "FOLLOW FOR MORE", font("b", 30), fill=(255, 150, 40, 255), outline=(255, 210, 140), a=a)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((W / 2, 262), "More map stories on our page", font=font("m", 17), fill=GREY + (int(255 * a),), anchor="mt")


# ------------------------------------------------------------------ topics, facts, script
TOPICS = [
    "Dakshin Digvijay 1676-78: Shivaji Maharaj's southern campaign (Bhagyanagar, Gingee, Vellore)",
    "Raigad: from a hill fort to the capital and the coronation of 1674",
    "Shivaji Maharaj's escape from Agra in 1666: the route back to Maharashtra",
    "Treaty of Purandar 1665 and the forts given up",
    "Pratapgad 1659: the geography of the battle",
    "Panhala to Vishalgad 1660: the night run and the Pavankhind stand",
    "Surat 1664: the raid and the route it took",
    "The Maratha navy and the coastal forts: Sindhudurg, Vijaydurg, Suvarnadurg",
    "How Swarajya grew: Torna, Rajgad, Kondana and the first forts (1646-1656)",
    "Sambhaji Maharaj and the Konkan coast campaigns",
    "Gingee after 1689: how Maratha rule survived in the south (Rajaram Maharaj)",
    "Sambhaji Maharaj and Burhanpur 1681",
    "The Maratha forts on the UNESCO World Heritage list (12 forts, 2025)",
    "Shivaji Maharaj's capital moves: Raigad, Rajgad, Panhala",
    "Janjira: why the sea fort was so hard to take",
]

FACT_PROMPT = """Make a FACT SHEET for a short history video about: "{topic}" (Chhatrapati Shivaji Maharaj / Sambhaji Maharaj, Maratha Swarajya).
Search the web and use well-documented mainstream history (Britannica, Archaeological Survey of India, UNESCO, Maharashtra gazetteers, mainstream historians).
Write 12-18 short bullet facts, each with a DATE or YEAR and a PLACE where possible. Mark a fact [disputed] if historians disagree. Do not include folklore as fact.
No religion/caste/politics angles. At the end write a line "SOURCES:" with the names of 2-4 sources you really used. Plain text."""

MAP_PROMPT = """You write one Instagram Reel (70-95 seconds) in the style 'history on a map' for the page Shivgatha. Topic: {topic}
Narration is in HINDI (Devanagari) for the voice AND the same sentence in HINGLISH (Roman letters) for the on-screen subtitles, the way a young Indian history creator talks.

FACT SHEET (the ONLY facts you may use; do not add dates, numbers, names or quotes that are not here):
{facts}

{safety}

PLACES you can point to (use ONLY these keys): {places}

Return ONLY JSON:
{{"title":"short English/Hinglish title","caption":"2-3 lines Hinglish for the caption","comment_q":"one easy Hinglish question for viewers","hashtags":["6 low-competition tags, no #viral"],
 "scenes":[{{
  "say":"one short Hindi sentence, Devanagari only, 6-14 words",
  "sub":"the same sentence in Hinglish, Roman letters (same words as 'say')",
  "head":"on-screen top label: 'Place · Year' (e.g. 'Gingee · May 1677') or a short phrase; scene 1: the opening question in English",
  "type":"story | stat | outro",
  "place":"key from PLACES or '' ",
  "kind":"fort | city | battle | none",
  "label":"UPPERCASE place name on the map",
  "sublabel":"small line under it (e.g. 'Tamil Nadu · May 1677') or ''",
  "view":"india | wide | mid | close",
  "add":["modern Indian states to turn saffron in this scene, exact names like Maharashtra, Karnataka, Tamil Nadu, Telangana, Andhra Pradesh, Goa"],
  "route":["optional list of 2-3 PLACES keys, a route travelled in this scene"],
  "callout":"optional, max 7 words English, a key fact for this scene",
  "stat":{{"value":"optional big number such as 1698","label":"max 6 words"}},
  "card":{{"label":"optional, e.g. 'From a Jesuit letter · 1678 (paraphrased)'","text":"optional, max 30 words, only a paraphrase of a documented source from the FACT SHEET"}},
  "sfx":"none | horse | march | birds | sword"
 }}]}}
RULES
- 14-18 scenes. Total 'say' words 110-170. Scene 1: type story, view wide, head = a curiosity question (example 'How far did Swarajya reach?'), add = ["Maharashtra"], place ''.
- Follow the story in time order; every scene is one clear beat with its place on the map. Give year/month in 'head' only when the FACT SHEET gives it.
- The last scene: type outro, say = a short Hindi line asking to follow Shivgatha for more map stories (sub in Hinglish), view india, add all states Swarajya touched in this story.
- Use [disputed] facts only with 'कहा जाता है' / 'historians say'. Never invent. Respectful tone: 'महाराज'.
- No religion, caste, politics or insulting words anywhere. Visuals are only maps, forts, routes, text. No faces.
"""


def search_facts(topic):
    """Gemini + Google Search -> (fact sheet text, [source names]); ('', []) if search is not available"""
    import requests
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return "", []
    models = [m for m in (os.getenv("GEMINI_MODEL"), "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash") if m]
    for m in dict.fromkeys(models):
        for _ in range(2):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                                  json={"contents": [{"parts": [{"text": FACT_PROMPT.format(topic=topic)}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": .3}}, timeout=90)
                if r.ok:
                    c = r.json()["candidates"][0]
                    text = "".join(p.get("text", "") for p in c["content"]["parts"]).strip()
                    names = []
                    for g in (c.get("groundingMetadata") or {}).get("groundingChunks") or []:
                        w = g.get("web") or {}
                        n = (w.get("title") or "")[:40]
                        if n and n not in names:
                            names.append(n)
                    if len(text) > 200:
                        return text, names[:4]
                print(f"fact search {m}: {r.status_code}", file=sys.stderr)
            except Exception as ex:
                print(f"fact search {m}: {str(ex)[:100]}", file=sys.stderr)
            time.sleep(3)
    return "", []


def _rom_share(s):
    letters = re.findall(r"[A-Za-zऀ-ॿ]", s)
    return (sum(1 for c in letters if c.isascii()) / len(letters)) if letters else 0.0


def validate_map(spec, risky, deva_share, max_words=185):
    sc = spec.get("scenes") or []
    if not 10 <= len(sc) <= 20:
        raise ValueError(f"need 14-18 scenes, got {len(sc)}")
    out = []
    for s in sc:
        if not isinstance(s, dict) or not s.get("say"):
            continue
        s["say"] = re.sub(r"\*\*", "", str(s["say"])).strip()
        s["sub"] = re.sub(r"\*\*", "", str(s.get("sub") or "")).strip()
        if deva_share(s["say"]) < .9:
            raise ValueError('"say" must be Devanagari Hindi only')
        if not s["sub"] or _rom_share(s["sub"]) < .9:
            raise ValueError('"sub" must be the same sentence in Hinglish, Roman letters only')
        s["head"] = str(s.get("head") or "")[:48]
        s["type"] = "outro" if str(s.get("type")) == "outro" else ("stat" if s.get("stat") else "story")
        s["place"] = str(s.get("place") or "").lower().strip()
        if s["place"] and s["place"] not in GAZ:
            raise ValueError(f'place "{s["place"]}" is not in PLACES; use only the listed keys')
        s["kind"] = s.get("kind") if s.get("kind") in KINDS else "none"
        if not s["place"]:
            s["kind"] = "none"
        s["label"] = str(s.get("label") or "").upper()[:22]
        s["sublabel"] = str(s.get("sublabel") or "")[:40]
        s["view"] = s.get("view") if s.get("view") in VIEW_SPAN else "wide"
        s["add"] = [a for a in (s.get("add") or []) if a in states()]
        r = [str(x).lower().strip() for x in (s.get("route") or [])]
        if any(x not in GAZ for x in r):
            raise ValueError("route uses a key that is not in PLACES")
        s["route"] = r[:3] if len(r) >= 2 else []
        s["callout"] = str(s.get("callout") or "")[:60]
        st = s.get("stat") if isinstance(s.get("stat"), dict) else None
        s["stat"] = {"value": str(st.get("value", ""))[:8], "label": str(st.get("label", ""))[:40]} if st and st.get("value") else None
        c = s.get("card") if isinstance(s.get("card"), dict) else None
        s["card"] = {"label": str(c.get("label", ""))[:60], "text": str(c.get("text", ""))[:230]} if c and c.get("text") else None
        s["sfx"] = s.get("sfx") if s.get("sfx") in ("horse", "march", "birds", "sword") else "none"
        if s["route"] and s["sfx"] == "none":
            s["sfx"] = "horse"
        out.append(s)
    if len(out) < 10:
        raise ValueError("too few usable scenes")
    words = sum(len(s["say"].split()) for s in out)
    if words < 90:
        raise ValueError(f"narration too short ({words} words); write 110-170")
    if words > max_words:
        raise ValueError(f"narration too long ({words} words); the limit is {max_words - 15}")
    blob = " ".join(s["say"] + " " + s["sub"] + " " + s["head"] + " " + s["callout"] + " " + json.dumps(s["card"] or {}, ensure_ascii=False) for s in out) \
        + " " + " ".join(str(spec.get(k, "")) for k in ("title", "caption", "comment_q"))
    m = risky.search(blob)
    if m:
        raise ValueError(f'forbidden word "{m.group(0)}": rewrite without religion, caste, politics or insults')
    if out[-1]["type"] != "outro":
        raise ValueError("the last scene must be type outro")
    if out[0]["place"]:
        out[0]["place"], out[0]["kind"] = "", "none"
    spec["scenes"] = out
    spec["title"] = str(spec.get("title") or "Shivgatha")[:60]
    spec["hashtags"] = [h if h.startswith("#") else "#" + h for h in spec.get("hashtags", []) if isinstance(h, str)][:8]
    spec.pop("_cams", None)
    return spec


def gen_spec(topic, story):
    """story = the story.py module (borrows call_gemini, clean_json, RISKY, SAFETY_RULES, _deva_share)"""
    import core as M
    facts, sources = search_facts(topic)
    if not facts:
        print("WARNING: no web-searched fact sheet; the model may use only widely documented facts", file=sys.stderr)
        facts = "(no search result: use ONLY very well-known, widely documented facts, with years only when certain; skip anything doubtful)"
    prompt = MAP_PROMPT.format(topic=topic, facts=facts[:6000], safety=story.SAFETY_RULES, places=GAZ_LIST)
    fb, last = "", None
    for attempt in range(4):
        try:
            spec = validate_map(story.clean_json(M.call_gemini(prompt + fb)), story.RISKY, story._deva_share)
            spec["sources"] = sources
            spec["facts"] = facts[:2500]
            return spec
        except Exception as ex:
            last = ex
            fb = f"\n\nYour previous reply was rejected: {ex}. Return ONLY valid JSON following the schema exactly."
            print(f"bad map script ({ex}); retry {attempt + 1}/4", file=sys.stderr)
    raise RuntimeError(f"AI did not return a usable map script: {last}")


def plan(state, forced=""):
    """-> (topic, category). Never repeats a used topic."""
    if forced:
        return forced, "Manual"
    import story
    used = [u["topic"] for u in state["used"]]
    pool = [t for t in TOPICS if not story.too_similar(t, used)]
    if pool:
        return random.choice(pool), "Map"
    try:
        import core as M
        data = story.clean_json(M.call_gemini('Suggest 6 NEW specific topics for a map-based history video about Chhatrapati Shivaji Maharaj / Sambhaji Maharaj / Maratha Swarajya (campaigns, routes, forts, sea forts). '
                                              'Avoid: ' + "; ".join(used[-60:]) + '. Return ONLY JSON {"topics":["..."]} in English.'))
        for t in data.get("topics", []):
            if not story.too_similar(str(t), used) and not story.RISKY.search(str(t)):
                return str(t), "Map"
    except Exception as ex:
        print("map topic planner failed:", str(ex)[:100], file=sys.stderr)
    return random.choice(TOPICS), "Map"


def build_caption(spec, handle):
    cap = str(spec.get("caption", "")).strip()
    cq = str(spec.get("comment_q") or "").strip()
    parts = [cap]
    if cq:
        parts.append(f"{cq} Comment mein batayein 👇")
    parts.append("🚩 Jai Shivray! Story pasand aayi toh save aur share karein.")
    parts.append(f"Roz ek nayi map story ke liye follow karein @{handle}")
    if spec.get("sources"):
        parts.append("Sources: " + ", ".join(spec["sources"]) + ". Modern state outlines are only a backdrop.")
    else:
        parts.append("Based on widely documented history. Modern state outlines are only a backdrop.")
    tags = [h for h in spec.get("hashtags", []) if h.lower() not in {"#reels", "#viral", "#trending", "#history", "#india", "#fyp"}]
    base = ["#shivajimaharaj", "#jaishivray", "#marathahistory", "#chhatrapatishivajimaharaj", "#historyonamap"]
    parts.append(" ".join(list(dict.fromkeys(tags[:6] + base))[:10]))
    return "\n\n".join(p for p in parts if p)[:2200]


# ------------------------------------------------------------------ built-in sample (look test only, no AI, no facts claimed beyond well-known ones)
SAMPLE = {"title": "Dakshin Digvijay (sample)", "caption": "Sample look", "comment_q": "Agla kaunsa kila?", "hashtags": [], "scenes": [
    dict(say="स्वराज्य की सीमा कहाँ तक पहुँची थी", sub="Swarajya ki seema kahan tak pahunchi thi", head="How far did Swarajya reach?", type="story", place="", kind="none", view="wide", add=["Maharashtra"]),
    dict(say="सन सोलह सौ सतहत्तर में महाराज दक्षिण की ओर चले", sub="San solah sau sattahattar mein Maharaj dakshin ki or chale", head="Dakshin Digvijay · 1677", type="story", place="panhala", kind="fort", label="PANHALA", sublabel="Maharashtra", view="mid", add=["Maharashtra"], route=["panhala", "golconda"], callout="The southern campaign begins"),
    dict(say="हैदराबाद के पास गोलकोंडा के सुलतान से मुलाकात हुई", sub="Hyderabad ke paas Golconda ke sultan se mulakat hui", head="Bhagyanagar · 1677", type="story", place="golconda", kind="fort", label="GOLCONDA", sublabel="Telangana", view="close", add=["Telangana"], callout="Meeting at Bhagyanagar"),
    dict(say="फिर महाराज तमिलनाडु के जिंजी तक पहुँचे", sub="Phir Maharaj Tamil Nadu ke Gingee tak pahunche", head="Gingee · 1677", type="story", place="gingee", kind="fort", label="GINGEE", sublabel="Tamil Nadu", view="close", add=["Tamil Nadu"], route=["golconda", "gingee"]),
    dict(say="वेल्लोर भी बाद में स्वराज्य का हिस्सा बना", sub="Vellore bhi baad mein Swarajya ka hissa bana", head="Vellore · 1678", type="story", place="vellore", kind="fort", label="VELLORE", sublabel="Tamil Nadu", view="close", add=["Tamil Nadu"], stat={"value": "1678", "label": "Vellore joins Swarajya"}),
    dict(say="ऐसी और कहानियों के लिए शिवगाथा को फॉलो करें", sub="Aisi aur kahaniyon ke liye Shivgatha ko follow karein", head="", type="outro", place="", kind="none", view="india", add=["Maharashtra", "Telangana", "Tamil Nadu", "Karnataka", "Andhra Pradesh"]),
]}
