"""
Shivgatha: daily Hindi story Reels about Chhatrapati Shivaji Maharaj and Chhatrapati Sambhaji Maharaj.
Parchment look (1600s feel), deep heavy Indian narrator voice, safe-history rules, never repeats a topic, long stories become parts.

Standalone module: it only borrows call_gemini, upload_video, publish and ig_recent_captions from core.py.

    python story.py                   # make + post one Reel
    python story.py --dry-run         # make video + caption only (nothing is posted)
    python story.py --topic "..."     # force a topic
    python story.py --sample          # render the built-in sample (no AI, no voice) to test the look
"""
import argparse
import asyncio
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

VERSION = "shivgatha v1 (parchment theme, Hindi deep voice, safe-history rules, 1600s visuals)"
BASE = Path(__file__).parent
OUT_DIR = BASE / "output"
HANDLE = (os.getenv("IG_HANDLE") or "shivgatha").lstrip("@")
BRAND = os.getenv("BRAND_NAME") or "शिवगाथा"
VOICE = os.getenv("EXPLAIN_VOICE") or "hi-IN-MadhurNeural"       # edge-tts fallback (male Hindi)
VOICE_BACKUP = ["hi-IN-SwaraNeural"]
VOICE_RATE = os.getenv("EXPLAIN_RATE") or "-10%"
VOICE_PITCH = os.getenv("EXPLAIN_PITCH") or "-18Hz"              # deeper for the edge-tts fallback
VOICE_TEXT = "devanagari"
W, H, FPS = 720, 1280, 30

if not features.check("raqm"):
    print("WARNING: Pillow has no raqm text engine; Hindi conjuncts will look broken. Install libfribidi0 and a recent Pillow.", file=sys.stderr)

# ------------------------------------------------------------------ topics (all well documented, neutral)
SEEDS = [
    "शिवनेरी किले में शिवाजी महाराज का जन्म",
    "जिजाऊ माँसाहेब ने शिवाजी को कैसे गढ़ा",
    "तोरणा किले की जीत: स्वराज्य की पहली सीढ़ी",
    "राजगड: स्वराज्य की पहली राजधानी",
    "प्रतापगड की लड़ाई की रणनीति",
    "पावनखिंड: बाजीप्रभु देशपांडे का बलिदान",
    "लाल महल और शाहिस्ता खान की कहानी",
    "सूरत अभियान की योजना",
    "पुरंदर की संधि क्या थी",
    "आगरा से शिवाजी महाराज की सुरक्षित वापसी",
    "सिंहगड की लड़ाई और तानाजी मालुसरे",
    "रायगड पर राज्याभिषेक की कहानी",
    "अष्टप्रधान मंडल: स्वराज्य का प्रशासन",
    "शिवाजी महाराज की नौसेना और सिंधुदुर्ग",
    "कान्होजी आंग्रे और मराठा नौसेना की परंपरा",
    "गनिमी कावा: छापामार युद्ध नीति",
    "शिवाजी महाराज के किलों की बनावट",
    "प्रतापराव गुजर और बहलोल खान की घटना",
    "शिवराई: स्वराज्य का अपना सिक्का",
    "राज्यव्यवहार कोश: अपनी भाषा की पहल",
    "संभाजी महाराज का जन्म और बचपन",
    "संभाजी महाराज की विद्वत्ता और बुधभूषण ग्रंथ",
    "संभाजी महाराज का राज्याभिषेक",
    "संभाजी महाराज और पुर्तगालियों का संघर्ष",
    "संभाजी महाराज और जंजीरा की मुहिम",
    "औरंगज़ेब का दक्कन अभियान और संभाजी महाराज का प्रतिरोध",
    "संभाजी महाराज की अंतिम घटनाएँ, सम्मान के साथ",
    "रायगड किले की रचना और हिरकणी की कहानी",
    "शिवाजी महाराज के साथी: येसाजी कंक और नेताजी पालकर",
    "महाराज की न्यायप्रियता: प्रजा की रक्षा के नियम",
]

CATEGORIES = ["शिवाजी महाराज का बचपन और जिजाऊ के संस्कार", "किले और दुर्ग", "प्रसिद्ध लड़ाइयाँ और रणनीति",
              "स्वराज्य का प्रशासन और न्याय", "मराठा नौसेना और सागरी किले", "संभाजी महाराज: शिक्षा, साहित्य और पराक्रम",
              "वीर साथी और सरदार", "राज्याभिषेक और छत्रपति की उपाधि", "संभाजी महाराज का शासनकाल",
              "महाराज के जीवन से सीख"]

SAFETY_RULES = """SAFETY RULES (very important, the page must never create controversy):
 - Use ONLY well-documented, widely accepted history (mainstream Indian historians, Shiv Charitra, Sabhasad Bakhar, contemporary records).
   If a date or detail is disputed or only folklore, either skip it or say "इतिहासकारों के अनुसार" / "कहा जाता है" / "लगभग".
   NEVER invent dialogue, numbers, dates, names or quotes. When unsure, leave the detail out.
 - Talk about conflicts only as political and military events between states (स्वराज्य, आदिलशाही, मुगल सल्तनत, पुर्तगाली, सिद्दी, अंग्रेज़).
   NEVER frame anything as a religion against religion, caste against caste, or community against community.
   Do NOT use the words हिंदू, मुस्लिम, मुसलमान, इस्लाम, धर्म, जाति, ब्राह्मण, दलित, आरक्षण, जिहाद, काफ़िर, गद्दार, धर्मांतरण, कब्र.
   No politics, no political parties, no modern leaders, no comparison with today's events, no statements that insult any person or group.
 - Be respectful: always "छत्रपति शिवाजी महाराज" / "संभाजी महाराज" / "महाराज". Praise through facts (planning, courage, justice, care for people), not through attacking others.
 - Avoid contested topics: caste status debates, guru/teacher disputes, tomb or temple disputes, the exact cause of Shivaji Maharaj's death,
   and graphic violence. Where history is painful (for example the last days of Sambhaji Maharaj) tell it with dignity: courage and sacrifice, no graphic detail, no blame on any community.
 - Do not show or describe any painting or face of the Maharajas. Visuals are only maps, forts, flags, timelines, scrolls and names.
"""

PROMPT = """You write the script of a 45-75 second Instagram Reel in HINDI (Devanagari) about Chhatrapati Shivaji Maharaj / Chhatrapati Sambhaji Maharaj
and the Maratha Swarajya. It is narrated by a deep, heavy, powerful voice, so the writing must sound like a grand, calm storyteller.

TOPIC: {topic}
{series}
{safety}
STORY SHAPE: a strong hook (a year, a place, a question) -> background -> the turning point -> what happened -> why it matters / the lesson -> outro.
 - Short sentences (6-14 words). Calm, dramatic, respectful. No English words. Write years and numbers in HINDI WORDS inside "say" (e.g. सोलह सौ चौहत्तर), digits are fine in "sub" and visuals.
 - Total narration (all "say" together) between 105 and 165 words. 11-14 scenes, one idea per scene, 5-14 words per scene.
 - "sub" = the on-screen subtitle in Devanagari, same meaning as "say", at most 85 characters.
 - "head" = a short Devanagari headline for the scene (max 34 characters). Put 1-2 key words inside **double stars**.
 - Scene 1 is a "title" visual (hook). The last scene is an "outro" visual. Do not use "outro" anywhere else.
 - Vary the visuals: use at least 4 different types.
 - "sfx" = a background sound for the scene, one of: "horse" (riding, marching, travel), "birds" (calm morning, forest, fort at dawn, peace),
   "landslide" (mountain pass, ambush, collapse, chaos), "whisper" (secret plans, spies, tension, night), "sword" (battle, clash), "none".
   Use a sound on 4-7 scenes where it truly fits the story; use "none" on the rest, on the title scene and on the outro.

VISUAL TYPES (fill exactly these fields, all text in Devanagari):
 {{"type":"title","kicker":"सन 1659","big":"प्रतापगड की लड़ाई","place":"सातारा के पास"}}            kicker/big/place are short
 {{"type":"fort","name":"प्रतापगड","year":"1656","note":"जावळी का घना जंगल"}}                       year and note optional
 {{"type":"map","places":["पुणे","राजगड","रायगड"]}}                                                  2 to 5 real place names in travel order
 {{"type":"timeline","items":[{{"y":"1630","t":"शिवनेरी में जन्म"}},{{"y":"1645","t":"तोरणा की जीत"}}]}}   3 to 5 items, only certain years
 {{"type":"stat","big":"1674","label":"राज्याभिषेक का वर्ष"}}                                          one big number or word + label
 {{"type":"points","items":["पहला बिंदु","दूसरा बिंदु","तीसरा बिंदु"]}}                              2 to 4 short items (max 30 characters each)
 {{"type":"people","items":[{{"n":"जिजाऊ माँसाहेब","r":"माता और पहली गुरु"}}]}}                       1 to 3 real people, role max 28 characters
 {{"type":"scroll","lines":["स्वराज्य","न्याय","प्रजा का हित"]}}                                         2 to 4 short lines (lesson or summary)
 {{"type":"outro","next":"भाग 2: ..."}}                                                              "next" only when this video is not the last part

Return ONLY JSON:
{{"title":"<Hindi title, max 28 characters>","tag":"<1-2 Hindi words, e.g. किला>","caption":"<Hindi caption, 2-3 sentences, no hashtags>",
 "comment_q":"<one respectful Hindi question for the audience>","hashtags":["#छत्रपतिशिवाजीमहाराज","#..."],
 "scenes":[{{"say":"...","sub":"...","head":"...","sfx":"none","visual":{{...}}}}]}}

Recent captions (do not repeat their stories): {recent}
"""

SAMPLE = {
    "title": "रायगड और राज्याभिषेक", "tag": "राज्याभिषेक",
    "caption": "सन 1674 में रायगड पर छत्रपति शिवाजी महाराज का राज्याभिषेक हुआ। यह स्वराज्य के लिए एक बड़ा क्षण था।",
    "comment_q": "आप रायगड कब गए थे?", "hashtags": ["#रायगड"],
    "scenes": [
        {"say": "सन सोलह सौ चौहत्तर। रायगड किले पर बड़ा दिन।", "sub": "सन 1674। रायगड किले पर बड़ा दिन।", "head": "**सन 1674** का वह दिन", "visual": {"type": "title", "kicker": "सन 1674", "big": "रायगड पर राज्याभिषेक", "place": "रायगड किला"}},
        {"say": "सह्याद्रि की ऊँचाई पर खड़ा रायगड, स्वराज्य की राजधानी बना।", "sub": "सह्याद्रि पर खड़ा रायगड, स्वराज्य की राजधानी।", "head": "स्वराज्य की **राजधानी**", "sfx": "birds", "visual": {"type": "fort", "name": "रायगड", "year": "1656", "note": "स्वराज्य की राजधानी"}},
        {"say": "पुणे से राजगड, और फिर रायगड, यह स्वराज्य का सफ़र था।", "sub": "पुणे से राजगड, फिर रायगड, स्वराज्य का सफ़र।", "head": "स्वराज्य का **सफ़र**", "sfx": "horse", "visual": {"type": "map", "places": ["पुणे", "राजगड", "रायगड"]}},
        {"say": "सोलह सौ छप्पन में रायगड स्वराज्य में आया।", "sub": "1656 में रायगड स्वराज्य में आया।", "head": "सालों का **सफ़र**", "sfx": "whisper", "visual": {"type": "timeline", "items": [{"y": "1656", "t": "रायगड स्वराज्य में शामिल"}, {"y": "1674", "t": "राज्याभिषेक"}, {"y": "1680", "t": "महाराज का निधन"}]}},
        {"say": "इसी वर्ष महाराज छत्रपति कहलाए।", "sub": "इसी वर्ष महाराज छत्रपति कहलाए।", "head": "**छत्रपति** की उपाधि", "sfx": "sword", "visual": {"type": "stat", "big": "1674", "label": "छत्रपति की उपाधि"}},
        {"say": "माता जिजाऊ ने बचपन से यह स्वराज्य का सपना सींचा था।", "sub": "माता जिजाऊ ने बचपन से स्वराज्य का सपना सींचा।", "head": "माता **जिजाऊ**", "sfx": "landslide", "visual": {"type": "people", "items": [{"n": "जिजाऊ माँसाहेब", "r": "माता और प्रेरणा"}]}},
        {"say": "अष्टप्रधान मंडल बना, अपना सिक्का चला।", "sub": "अष्टप्रधान मंडल बना, अपना सिक्का चला।", "head": "नया **शासन**", "visual": {"type": "points", "items": ["अष्टप्रधान मंडल", "शिवराई सिक्का", "राज्यव्यवहार कोश"]}},
        {"say": "अच्छा शासन, न्याय और प्रजा का हित, यही स्वराज्य की सीख है।", "sub": "अच्छा शासन, न्याय, प्रजा का हित: स्वराज्य की सीख।", "head": "आज की **सीख**", "visual": {"type": "scroll", "lines": ["सुशासन", "न्याय", "प्रजा का हित"]}},
        {"say": "ऐसी कहानियों के लिए पेज को फ़ॉलो करें। जय शिवराय।", "sub": "ऐसी कहानियों के लिए फ़ॉलो करें। जय शिवराय।", "head": "कल मिलते हैं", "visual": {"type": "outro", "next": "भाग 2: रायगड का किला"}},
    ],
}

# ------------------------------------------------------------------ look: aged parchment, saffron, sepia ink
PARCH = (237, 222, 190)
PARCH2 = (224, 205, 168)
INK = (52, 32, 14)
BODY = (96, 66, 38)
MUTE = (140, 110, 74)
LINE = (178, 146, 100)
SAFF = (205, 88, 18)
MAROON = (122, 28, 28)
GOLD = (164, 116, 28)
EARTH = (84, 58, 32)
ACCENTS = [SAFF, MAROON, (150, 84, 14)]
ACC = ACCENTS[0]


def mix(c, a, base=PARCH):
    a = max(0.0, min(1.0, a))
    return tuple(int(base[i] + (c[i] - base[i]) * a) for i in range(3))


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


_NOTO = "/usr/share/fonts/truetype/noto/"
_FD = {
    "serifb": ["fonts/NotoSerifDevanagari-Bold.ttf", _NOTO + "NotoSerifDevanagari-Bold.ttf"],
    "serif": ["fonts/NotoSerifDevanagari-Regular.ttf", _NOTO + "NotoSerifDevanagari-Regular.ttf"],
    "sansb": ["fonts/NotoSansDevanagari-Bold.ttf", _NOTO + "NotoSansDevanagari-Bold.ttf"],
    "sans": ["fonts/NotoSansDevanagari-Regular.ttf", _NOTO + "NotoSansDevanagari-Regular.ttf"],
    "latin": ["fonts/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],   # the Devanagari fonts have no Latin letters
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


def tw(d, s, f):
    return d.textlength(s, font=f)


def text_c(d, cx, y, s, f, fill):
    d.text((cx - tw(d, s, f) / 2, y), s, font=f, fill=fill)


def wrap(d, s, f, max_w):
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if tw(d, t, f) <= max_w or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def fit_lines(d, s, kind, size, max_w, max_lines, min_size=18):
    while size > min_size:
        f = font(kind, size)
        ls = wrap(d, s, f, max_w)
        if len(ls) <= max_lines:
            return f, ls
        size -= 2
    f = font(kind, min_size)
    return f, wrap(d, s, f, max_w)[:max_lines]


def rich_words(s):
    out = []
    for p in re.split(r"(\*\*.+?\*\*)", s or ""):
        if not p:
            continue
        hl = p.startswith("**") and p.endswith("**") and len(p) > 4
        for w in (p[2:-2] if hl else p).split():
            out.append((w, hl))
    return out


def draw_rich(d, cx, y, text, size, max_w, a, u, line_gap=1.5):
    """Headline: plain words in sepia, **key** words bold saffron with a gold underline growing in (u 0..1)."""
    fn, fh = font("serif", size), font("serifb", size)
    lines, x = [[]], 0
    sp = tw(d, " ", fn)
    for w, hl in rich_words(text):
        f = fh if hl else fn
        wl = tw(d, w, f)
        if lines[-1] and x + sp + wl > max_w:
            lines.append([])
            x = 0
        if lines[-1]:
            x += sp
        lines[-1].append((w, hl, x, wl))
        x += wl
    for li, ln in enumerate(lines[:3]):
        if not ln:
            continue
        wid = ln[-1][2] + ln[-1][3]
        x0 = cx - wid / 2
        yy = y + li * size * line_gap
        for w, hl, xo, wl in ln:
            d.text((x0 + xo, yy), w, font=fh if hl else fn, fill=mix(ACC if hl else INK, a))
            if hl and u > 0:
                d.rectangle((x0 + xo, yy + size * 1.42, x0 + xo + wl * u, yy + size * 1.42 + 3), fill=mix(GOLD, a))
    return min(3, len(lines))


def reveal(t, i, persist, step=0.35, dur=0.55, start=0.3):
    if persist:
        return 1.0, 0
    e = ease((t - start - i * step) / dur)
    return e, int((1 - e) * 20)


# ------------------------------------------------------------------ drawn art (no photos, no faces: forts, flags, maps, scrolls)
def flag(d, x, y, h, col, t, a=1.0):
    """Swallow-tailed saffron pennant (bhagwa dhwaj) on a pole, waving."""
    d.line((x, y - 6, x, y + h * 2.3), fill=mix(EARTH, a), width=4)
    d.ellipse((x - 5, y - 12, x + 5, y - 2), fill=mix(GOLD, a))
    w = h * 1.5
    pts_top, pts_bot = [], []
    n = 8
    for i in range(n + 1):
        xx = x + w * i / n * 0.98
        off = math.sin(t * 5 - i * 0.7) * 3.5 * (i / n)
        pts_top.append((xx, y + off))
        pts_bot.append((xx, y + h + off))
    notch = (x + w * 0.62, y + h / 2 + math.sin(t * 5 - 5) * 3)
    poly = pts_top[:6] + [(x + w, y + h * 0.17 + math.sin(t * 5 - 6) * 3), notch, (x + w, y + h * 0.83 + math.sin(t * 5 - 6) * 3)] + pts_bot[:6][::-1]
    d.polygon(poly, fill=mix(col, a))


def fort(d, cx, by, w, h, col, a, t, with_flag=True):
    """Hill fort silhouette: sloping hill, curtain wall with battlements, bastion towers, gate."""
    hill = (mix(EARTH, 0.55 * a), mix(col, a))
    r = random.Random(int(w) + int(h))
    pts = [(cx - w * 0.72, by)]
    for k in range(1, 14):
        fx = -0.72 + 1.44 * k / 14
        ht = h * (0.12 + 0.2 * (1 - abs(fx) / 0.72)) + r.uniform(-0.025, 0.025) * h
        pts.append((cx + fx * w, by - ht))
    pts.append((cx + w * 0.72, by))
    d.polygon(pts, fill=hill[0])
    d.polygon([(x, y + h * 0.05) for x, y in pts[:-1]] + [(cx + w * 0.72, by), (cx - w * 0.72, by)], fill=mix(EARTH, 0.8 * a))
    x0, x1 = cx - w * 0.42, cx + w * 0.42
    wt, wb = by - h * 0.44, by - h * 0.2
    d.rectangle((x0, wt, x1, wb), fill=hill[1])
    x = x0
    while x < x1 - 8:
        d.rectangle((x, wt - 11, x + 12, wt), fill=hill[1])
        x += 22
    towers = [(-0.42, 0.62, 56), (-0.14, 0.70, 48), (0.14, 0.92, 62), (0.42, 0.66, 54)]
    top_x = top_y = None
    for ox, th, tw_ in towers:
        tx = cx + w * ox
        ty = by - h * th
        d.rectangle((tx - tw_ / 2, ty, tx + tw_ / 2, wb), fill=hill[1])
        xx = tx - tw_ / 2
        while xx < tx + tw_ / 2 - 6:
            d.rectangle((xx, ty - 10, xx + 10, ty), fill=hill[1])
            xx += 18
        d.rounded_rectangle((tx - 6, ty + 18, tx + 6, ty + 44), 6, fill=mix(PARCH2, 0.9 * a))
        if th > 0.9:
            top_x, top_y = tx, ty - 10
    gx = cx - 6
    d.rectangle((gx - 26, wb - 44, gx + 26, wb), fill=mix(INK, a))
    d.pieslice((gx - 26, wb - 70, gx + 26, wb - 18), 180, 360, fill=mix(INK, a))
    if with_flag and top_x:
        flag(d, top_x, top_y - 66, 34, SAFF, t, a)


def ridge(d, y0, amp, col, seed, a=1.0, x0=0, x1=W):
    r = random.Random(seed)
    pts = [(x0, y0 + 80)]
    x = x0
    while x <= x1:
        pts.append((x, y0 - r.random() * amp))
        x += r.choice([40, 60, 80])
    pts += [(x1, y0 + 80)]
    d.polygon(pts, fill=mix(col, a))


def divider(d, cx, y, w, a):
    d.line((cx - w / 2, y, cx - 14, y), fill=mix(LINE, a), width=2)
    d.line((cx + 14, y, cx + w / 2, y), fill=mix(LINE, a), width=2)
    d.polygon([(cx, y - 7), (cx + 7, y), (cx, y + 7), (cx - 7, y)], fill=mix(GOLD, a))


def seal(d, cx, cy, r, a, ring=GOLD):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(PARCH2, a), outline=mix(ring, a), width=5)
    d.ellipse((cx - r + 12, cy - r + 12, cx + r - 12, cy + r - 12), outline=mix(ring, a), width=2)
    for k in range(24):
        ang = k * math.pi / 12
        d.line((cx + (r - 12) * math.cos(ang), cy + (r - 12) * math.sin(ang), cx + (r - 22) * math.cos(ang), cy + (r - 22) * math.sin(ang)), fill=mix(ring, a * 0.8), width=2)


# ------------------------------------------------------------------ visuals (area y 300..985)
VY0, VY1 = 300, 985
CX = W // 2


def v_title(d, v, t, persist, S):
    a, off = reveal(t, 0, persist)
    d.text((CX - tw(d, v.get("kicker", ""), font("sansb", 34)) / 2, 330 + off), v.get("kicker", ""), font=font("sansb", 34), fill=mix(ACC, a))
    divider(d, CX, 392 + off, 360, a)
    f, ls = fit_lines(d, v.get("big", ""), "serifb", 64, 600, 2, 38)
    for j, s in enumerate(ls):
        text_c(d, CX, 420 + off + j * int(f.size * 1.5), s, f, mix(INK, a))
    y = 420 + len(ls) * int(f.size * 1.5) + 8
    if v.get("place"):
        text_c(d, CX, y + off, v["place"], font("serif", 30), mix(BODY, a))
    a2, _ = reveal(t, 2, persist, 0.3, 0.7, 0.2)
    ridge(d, 880, 90, (150, 116, 76), 3, a2)
    ridge(d, 930, 70, (112, 82, 50), 4, a2)
    fort(d, CX, 985, 470, 330, (60, 38, 18), a2, t)


def v_fort(d, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.7, 0.1)
    fort(d, CX, 800, 560, 400, (62, 40, 20), a, t)
    a2, off2 = reveal(t, 2, persist, 0.3, 0.5, 0.5)
    rrect(d, (110, 830 + off2, W - 110, 940 + off2), 14, fill=mix(PARCH2, a2), outline=mix(GOLD, a2), width=3)
    text_c(d, CX, 842 + off2, v.get("name", ""), font("serifb", 48), mix(INK, a2))
    sub = " — ".join(x for x in (str(v.get("year") or ""), str(v.get("note") or "")) if x)
    if sub:
        f, ls = fit_lines(d, sub, "serif", 28, 440, 1, 20)
        text_c(d, CX, 902 + off2, ls[0], f, mix(BODY, a2))
    ridge(d, 985, 60, (150, 116, 76), 9, a * 0.0 + (0.0 if a < 0.1 else 0.6))


def rrect(d, xy, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, r, fill=fill, outline=outline, width=width)


def v_map(d, v, t, persist, S):
    places = [str(x) for x in (v.get("places") or [])][:5] or ["स्वराज्य"]
    n = len(places)
    ridge(d, 985, 150, (205, 186, 148), 11, 0.9)
    ridge(d, 985, 100, (190, 168, 128), 12, 0.9)
    pts = []
    for i in range(n):
        f = i / max(1, n - 1)
        x = 150 + f * 420 + (math.sin(i * 2.1) * 50 if n > 1 else 200)
        y = 900 - f * 520 + math.sin(i * 1.7) * 30
        pts.append((x if n > 1 else CX, y))
    prog = 1.0 if persist else ease((t - 0.3) / (0.55 * n))
    total = max(1, n - 1) * prog
    for i in range(n - 1):
        seg = max(0.0, min(1.0, total - i))
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        k = 0
        while k * 16 < L * seg:
            px, py = x0 + (x1 - x0) * k * 16 / L, y0 + (y1 - y0) * k * 16 / L
            d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=mix(MAROON, 0.85))
            k += 1
    for i, (x, y) in enumerate(pts):
        a = 1.0 if persist else ease((total - (i - 0.35)) / 0.5)
        if a <= 0:
            continue
        d.ellipse((x - 15, y - 15, x + 15, y + 15), fill=mix(PARCH2, a), outline=mix(ACC, a), width=4)
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=mix(ACC, a))
        f = font("serifb", 34)
        lw = tw(d, places[i], f)
        lx = x + 26 if x + 26 + lw < W - 30 else x - 26 - lw
        rrect(d, (lx - 10, y - 24, lx + lw + 10, y + 26), 10, fill=mix(PARCH, a * 0.9), outline=mix(LINE, a), width=2)
        d.text((lx, y - 22), places[i], font=f, fill=mix(INK, a))
    cx, cy = 110, 400                                   # compass
    d.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), outline=mix(LINE, 1), width=2)
    d.polygon([(cx, cy - 36), (cx + 9, cy), (cx, cy + 36), (cx - 9, cy)], fill=mix(MAROON, 0.8))
    d.polygon([(cx - 36, cy), (cx, cy - 9), (cx + 36, cy), (cx, cy + 9)], fill=mix(GOLD, 0.7))
    text_c(d, cx, cy - 76, "उ", font("serifb", 26), INK)


def v_timeline(d, v, t, persist, S):
    items = (v.get("items") or [])[:5]
    n = max(1, len(items))
    gap = min(190, 600 // n)
    y0 = VY0 + 50 + (600 - gap * (n - 1)) // 2 - 40
    sp = 170
    d.line((sp, y0, sp, y0 + gap * (n - 1) + 30), fill=mix(LINE, 1), width=4)
    for i, it in enumerate(items):
        a, off = reveal(t, i, persist, 0.55, 0.55, 0.3)
        y = y0 + i * gap + off
        d.ellipse((sp - 13, y - 5, sp + 13, y + 21), fill=mix(ACC, a), outline=mix(PARCH, a), width=4)
        yr = str(it.get("y", ""))
        d.text((sp - 30 - tw(d, yr, font("serifb", 46)), y - 14), yr, font=font("serifb", 46), fill=mix(ACC, a))
        f, ls = fit_lines(d, str(it.get("t", "")), "sansb", 34, W - sp - 70, 3, 24)
        for j, s in enumerate(ls):
            d.text((sp + 34, y - 10 + j * int(f.size * 1.45)), s, font=f, fill=mix(INK, a))


def v_stat(d, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.7, 0.2)
    seal(d, CX, 600, 220 * (0.6 + 0.4 * a), a)
    big = str(v.get("big", ""))
    f, ls = fit_lines(d, big, "serifb", 120, 340, 1, 48)
    text_c(d, CX, 600 - f.size * 0.78 + off, ls[0], f, mix(INK, a))
    a2, off2 = reveal(t, 2, persist, 0.3, 0.6, 0.5)
    f2, ls2 = fit_lines(d, str(v.get("label", "")), "sansb", 34, 560, 2, 24)
    for j, s in enumerate(ls2):
        text_c(d, CX, 850 + off2 + j * int(f2.size * 1.45), s, f2, mix(BODY, a2))


def v_points(d, v, t, persist, S):
    items = [str(x) for x in (v.get("items") or [])][:4]
    n = max(1, len(items))
    h = min(150, 640 // n - 18)
    for i, s in enumerate(items):
        a, off = reveal(t, i, persist, 0.5, 0.55, 0.3)
        y0 = 330 + i * (h + 22) + off
        rrect(d, (50, y0, W - 50, y0 + h), 18, fill=mix(PARCH2, a), outline=mix(LINE, a), width=2)
        d.ellipse((72, y0 + h / 2 - 28, 128, y0 + h / 2 + 28), fill=mix(ACC, a), outline=mix(GOLD, a), width=3)
        text_c(d, 100, y0 + h / 2 - 27, str(i + 1), font("serifb", 36), mix(PARCH, a))
        f, ls = fit_lines(d, s, "sansb", 32, W - 270, 2, 22)
        for j, ln in enumerate(ls):
            d.text((152, y0 + (h - len(ls) * f.size * 1.45) / 2 + j * int(f.size * 1.45) - 4), ln, font=f, fill=mix(INK, a))


def v_people(d, v, t, persist, S):
    items = (v.get("items") or [])[:3]
    n = max(1, len(items))
    gap = 640 // n
    for i, it in enumerate(items):
        a, off = reveal(t, i, persist, 0.6, 0.6, 0.3)
        cy = 330 + i * gap + gap // 2 - 20 + off
        d.ellipse((120 - 62, cy - 62, 120 + 62, cy + 62), fill=mix(PARCH2, a), outline=mix(GOLD, a), width=5)
        d.ellipse((120 - 50, cy - 50, 120 + 50, cy + 50), outline=mix(LINE, a), width=2)
        d.polygon([(120, cy - 28), (120 + 20, cy), (120, cy + 28), (120 - 20, cy)], fill=mix(ACC, a))
        f, ls = fit_lines(d, str(it.get("n", "")), "serifb", 44, W - 260, 2, 28)
        for j, s in enumerate(ls):
            d.text((210, cy - 46 + j * int(f.size * 1.4)), s, font=f, fill=mix(INK, a))
        yy = cy - 46 + len(ls) * int(f.size * 1.4) + 4
        f2, l2 = fit_lines(d, str(it.get("r", "")), "sans", 28, W - 260, 2, 20)
        for j, s in enumerate(l2):
            d.text((210, yy + j * int(f2.size * 1.4)), s, font=f2, fill=mix(BODY, a))


def v_scroll(d, v, t, persist, S):
    lines = [str(x) for x in (v.get("lines") or [])][:4]
    a, off = reveal(t, 0, persist, 0.3, 0.7, 0.1)
    x0, x1, y0, y1 = 90, W - 90, 360, 900
    open_h = (y1 - y0) * a
    yc = (y0 + y1) / 2
    ya, yb = yc - open_h / 2, yc + open_h / 2
    d.rectangle((x0, ya, x1, yb), fill=PARCH2, outline=LINE, width=2)
    for yy in (ya, yb):
        d.rounded_rectangle((x0 - 18, yy - 18, x1 + 18, yy + 18), 18, fill=mix(GOLD, 0.8), outline=EARTH, width=3)
    n = max(1, len(lines))
    for i, s in enumerate(lines):
        a2, off2 = reveal(t, i, persist, 0.5, 0.5, 0.7)
        f, ls = fit_lines(d, s, "serifb", 52, x1 - x0 - 60, 2, 30)
        y = yc - (n * 110) / 2 + i * 110 + 20 + off2
        for j, ln in enumerate(ls):
            text_c(d, CX, y + j * int(f.size * 1.35), ln, f, mix(INK, a2))
        if i < n - 1:
            divider(d, CX, y + 88, 200, a2)


def v_outro(d, v, t, persist, S):
    a, off = reveal(t, 0, persist, 0.3, 0.6, 0.2)
    flag(d, CX - 70, 340 + off, 70, SAFF, t, a)
    text_c(d, CX, 520 + off, BRAND, font("serifb", 68), mix(INK, a))
    divider(d, CX, 620, 340, a)
    text_c(d, CX, 646 + off, "जय शिवराय", font("serifb", 52), mix(ACC, a))
    a2, off2 = reveal(t, 2, persist, 0.3, 0.6, 0.7)
    text_c(d, CX, 742 + off2, f"@{HANDLE}", font("latin", 28), mix(BODY, a2))
    nxt = str(v.get("next") or "").strip()
    if nxt:
        f, ls = fit_lines(d, "अगला: " + nxt, "sansb", 28, 560, 1, 20)
        wd = tw(d, ls[0], f) + 44
        rrect(d, (CX - wd / 2, 800 + off2, CX + wd / 2, 856 + off2), 28, fill=mix(MAROON, a2))
        text_c(d, CX, 806 + off2, ls[0], f, mix((255, 244, 220), a2))
    a3, off3 = reveal(t, 3, persist, 0.3, 0.6, 1.0)
    for k, (s, col) in enumerate((("सेव", INK), ("शेयर", INK), ("फ़ॉलो", ACC))):
        bx0 = 110 + k * 170
        rrect(d, (bx0, 900 + off3, bx0 + 150, 956 + off3), 28, fill=mix(col, a3))
        text_c(d, bx0 + 75, 906 + off3, s, font("sansb", 28), mix((255, 244, 220), a3))


VIS = {"title": v_title, "fort": v_fort, "map": v_map, "timeline": v_timeline, "stat": v_stat,
       "points": v_points, "people": v_people, "scroll": v_scroll, "outro": v_outro}


# ------------------------------------------------------------------ frame
_BGIMG = {}


def background():
    if "bg" not in _BGIMG:
        from PIL import ImageChops, ImageOps
        r = random.Random(7)
        small = Image.effect_noise((W // 3, H // 3), 34).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
        tex = ImageOps.colorize(small, black=(205, 184, 146), white=(246, 234, 208))
        im = Image.blend(Image.new("RGB", (W, H), PARCH), tex, 0.7)
        stains = Image.new("L", (W, H), 0)
        sd = ImageDraw.Draw(stains)
        for _ in range(7):
            x, y, rr = r.randint(0, W), r.randint(0, H), r.randint(60, 180)
            sd.ellipse((x - rr, y - rr, x + rr, y + rr), fill=r.randint(18, 40))
        stains = stains.filter(ImageFilter.GaussianBlur(50))
        im = Image.composite(Image.new("RGB", (W, H), (150, 110, 62)), im, stains)
        grad = Image.radial_gradient("L").resize((W, H), Image.BICUBIC)
        vig = grad.point(lambda v: int(max(0, v - 110) * 1.35))
        im = Image.composite(Image.new("RGB", (W, H), (96, 66, 34)), im, vig)
        d = ImageDraw.Draw(im)
        d.rectangle((16, 16, W - 17, H - 17), outline=mix(GOLD, 0.8), width=3)
        d.rectangle((26, 26, W - 27, H - 27), outline=mix(LINE, 0.9), width=1)
        for cx_, cy_ in ((26, 26), (W - 27, 26), (26, H - 27), (W - 27, H - 27)):
            d.polygon([(cx_, cy_ - 9), (cx_ + 9, cy_), (cx_, cy_ + 9), (cx_ - 9, cy_)], fill=mix(GOLD, 0.9))
        _BGIMG["bg"] = im
    return _BGIMG["bg"].copy()


def vkey(v):
    x = dict(v)
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def zoom(im, z):
    if z <= 1.0005:
        return im
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


def draw_frame(spec, idx, t, gt, total, persist):
    sc = spec["scenes"][idx]
    n = len(spec["scenes"])
    im = background()
    d = ImageDraw.Draw(im)
    v = sc.get("visual") or {}
    fn = VIS.get(v.get("type"))
    if fn:
        fn(d, v, t, persist, sc)
    im = zoom(im, 1.0 + min(t, 9.0) * 0.004)                  # slow cinematic push-in on the art only
    d = ImageDraw.Draw(im)
    # header: small flag + brand, tag, progress
    flag(d, 52, 44, 16, SAFF, gt, 1.0)
    d.text((90, 36), BRAND, font=font("serifb", 28), fill=INK)
    tag = str(spec.get("tag", "")).strip()[:16]
    if spec.get("part"):
        tag = f"भाग {spec['part'][0]}/{spec['part'][1]}"
    f = font("sansb", 24)
    d.text((W - 48 - tw(d, tag, f), 38), tag, font=f, fill=ACC)
    d.line((48, 92, W - 48, 92), fill=LINE, width=2)
    d.line((48, 92, 48 + (W - 96) * min(1.0, gt / max(total, 0.1)), 92), fill=ACC, width=4)
    # headline
    a = ease(t / 0.35)
    u = ease((t - 0.35) / 0.5)
    draw_rich(d, W // 2, 118, sc.get("head", ""), 46, 600, a, u)
    # subtitles on a soft plate
    sub = str(sc.get("sub", "")).strip()
    if sub:
        sa = ease(t / 0.2)
        f, ls = fit_lines(d, sub, "sansb", 36, 580, 3, 26)
        lh = int(f.size * 1.5)
        y = 1060 + (3 - len(ls)) * lh // 2
        pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(pl).rounded_rectangle((44, y - 16, W - 44, y + len(ls) * lh + 8), 20, fill=(236, 218, 180, int(190 * sa)))
        im = Image.alpha_composite(im.convert("RGBA"), pl).convert("RGB")
        d = ImageDraw.Draw(im)
        for j, s in enumerate(ls):
            text_c(d, W // 2, y + j * lh, s, f, mix(INK, sa))
    # footer
    d.line((48, 1226, W - 48, 1226), fill=LINE, width=1)
    d.text((48, 1234), str(spec.get("title", ""))[:26], font=font("serif", 22), fill=BODY)
    pg = f"{idx + 1:02d} / {n:02d}"
    d.text((W - 48 - tw(d, pg, font("sans", 22)), 1236), pg, font=font("sans", 22), fill=MUTE)
    return im


# ------------------------------------------------------------------ script (AI)
def clean_json(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    a, b = raw.find("{"), raw.rfind("}")
    return json.loads(raw[a:b + 1])


# ------------------------------------------------------------------ memory + topic planner (never repeat, long stories become parts)
STATE_FILE = BASE / "state.json"
SERIES_SHARE = float(os.getenv("SERIES_SHARE") or 0.5)      # chance that a big story is made as a 2-3 part series

PLAN_PROMPT = """You plan Hindi Instagram Reels about Chhatrapati Shivaji Maharaj, Chhatrapati Sambhaji Maharaj and the Maratha Swarajya.
Category for the next video: {cat}

Suggest 8 NEW, specific story topics in this category, written in Hindi (Devanagari). Each must be a well-documented, widely accepted event or theme
(no folklore presented as fact, no communal or caste angle, no politics). Avoid anything similar to these ALREADY USED topics: {used}

For each topic decide "parts":
 - 1 = a story that fits a 45-70 second video.
 - 2 or 3 = a big story (for example a long campaign, a famous fort's whole history, the life of a companion). Then give "outline":
   one Hindi line per part. Every part must stand alone and end with a hook for the next part.
Return ONLY JSON:
{{"ideas":[{{"topic":"<short Hindi topic>","parts":1,"outline":["<one line per part>"]}}]}}
"""


def load_state():
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("used", [])
    d.setdefault("pending", None)
    return d


def save_state(d):
    d["used"] = d["used"][-400:]
    STATE_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


_STOP = {"और", "का", "की", "के", "में", "से", "पर", "क्या", "कैसे", "यह", "वह", "को", "ने", "एक", "भाग"}


def _tok(t):
    return set(w for w in re.findall(r"\w{3,}", t.lower()) if w not in _STOP)


def too_similar(topic, used_topics):
    a = _tok(topic)
    for u in used_topics:
        b = _tok(u)
        if a and b and len(a & b) / max(1, min(len(a), len(b))) >= 0.67:
            return True
    return False


def pick_category(state):
    last = {}
    for i, u in enumerate(state["used"]):
        last[u.get("cat")] = i
    return min(CATEGORIES, key=lambda c: (last.get(c, -1), random.random()))


def plan_next(state):
    """-> (topic, part dict or None, category). Continues a pending series, else plans a brand-new topic."""
    pend = state.get("pending")
    if pend:
        age = (time.time() - pend.get("ts", 0)) / 86400
        if age <= 2.5 and pend.get("next", 2) <= pend.get("n", 1):
            return pend["topic"], {"k": pend["next"], "n": pend["n"], "title": pend["title"], "outline": pend["outline"]}, pend.get("cat", "")
        state["pending"] = None
    used_topics = [u["topic"] for u in state["used"]]
    cat = pick_category(state)
    ideas = []
    try:
        import core as M
        data = clean_json(M.call_gemini(PLAN_PROMPT.format(cat=cat, used="; ".join(used_topics[-70:]) or "none")))
        for it in data.get("ideas", []):
            t = str(it.get("topic", "")).strip()
            if t and not too_similar(t, used_topics) and not RISKY.search(t):
                n = it.get("parts", 1)
                n = n if isinstance(n, int) and 1 <= n <= 3 else 1
                outline = [str(x) for x in (it.get("outline") or [])][:n]
                if n > 1 and len(outline) < n:
                    n = 1
                ideas.append({"topic": t, "n": n, "outline": outline})
    except Exception as ex:
        print(f"topic planner failed ({str(ex)[:120]}); using the built-in list", file=sys.stderr)
    if not ideas:
        pool = [x for x in SEEDS if not too_similar(x, used_topics)] or SEEDS
        return random.choice(pool), None, "Built-in"
    multi = [i for i in ideas if i["n"] > 1]
    pick = random.choice(multi) if (multi and random.random() < SERIES_SHARE) else random.choice([i for i in ideas if i["n"] == 1] or ideas)
    if pick["n"] > 1:
        return pick["topic"], {"k": 1, "n": pick["n"], "title": pick["topic"], "outline": pick["outline"]}, cat
    return pick["topic"], None, cat


def record_posted(state, topic, part, cat):
    """Call only after a successful post."""
    day = time.strftime("%Y-%m-%d")
    if part is None:
        state["used"].append({"topic": topic, "cat": cat, "date": day, "parts": 1})
        state["pending"] = None
        return
    if part["k"] == 1:
        state["used"].append({"topic": part["title"], "cat": cat, "date": day, "parts": part["n"]})
    if part["k"] < part["n"]:
        state["pending"] = {"topic": topic, "title": part["title"], "n": part["n"], "next": part["k"] + 1,
                            "outline": part["outline"], "cat": cat, "ts": time.time()}
    else:
        state["pending"] = None


def series_block(part):
    if not part or part["n"] <= 1:
        return "SERIES: none. This is a single, complete video."
    k, n, title = part["k"], part["n"], part["title"]
    outline = "\n".join(f"   भाग {i + 1}: {t}" for i, t in enumerate(part["outline"]))
    s = (f'SERIES: this video is PART {k} of {n} of the series "{title}".\n Series outline:\n{outline}\n'
         f' Cover ONLY part {k}. Keep the TOTAL narration under 150 words for this part.\n'
         f' - Keep "title" = "{title[:28]}" (same in every part).\n')
    if k == 1:
        s += ' - Scene 1: a strong hook for the WHOLE story, then tell only part 1.\n'
    else:
        s += (f' - Scene 1 (title visual): kicker starts with "भाग {k}". The first narration sentence is a one-line recap of the previous part.\n')
    if k < n:
        s += (f' - The last story scene ends with a teaser for part {k + 1} (a question or cliffhanger).\n'
              f' - The outro visual gets "next":"भाग {k + 1}: <short title>" and the narration asks to follow so they do not miss part {k + 1}.\n')
    else:
        s += ' - This is the FINAL part: finish with what the story teaches, then the outro.\n'
    return s


# words and framings the page must never use (religion/caste/politics/abuse). Applied to every script, caption and topic.
RISKY = re.compile(
    r"हिंदू|हिन्दू|मुस्लिम|मुसलमान|इस्लाम|धर्म|धार्मिक|जिहाद|काफ़?िर|कब्र|मंदिर|मस्जिद|जाति|ब्राह्मण|दलित|आरक्षण|गद्दार|धर्मांतर|"
    r"भाजपा|कांग्रेस|शिवसेना|राजनीति|चुनाव|सरकार|मोदी|गांधी|नेहरू|"
    r"कटुआ|कटवे|मुल्ल|हरामी|कमीन|(?<!\S)साला(?!\S)|"
    r"\b(hindu|muslim|islam|religion|caste|jihad|temple|mosque|bjp|congress)\b", re.I)


def _deva_share(s):
    letters = re.findall(r"[A-Za-zऀ-ॿ]", s)
    if not letters:
        return 0.0
    return sum(1 for c in letters if "ऀ" <= c <= "ॿ") / len(letters)


def validate(spec, max_words=190, strict=True):
    if not isinstance(spec, dict) or not isinstance(spec.get("scenes"), list):
        raise ValueError("no scenes")
    out = []
    for sc in spec["scenes"]:
        if not isinstance(sc, dict) or not sc.get("say") or not isinstance(sc.get("visual"), dict):
            continue
        if sc["visual"].get("type") not in VIS:
            continue
        sc["say"] = re.sub(r"\*\*", "", str(sc["say"])).strip()
        sc["sub"] = re.sub(r"\*\*", "", str(sc.get("sub") or sc["say"])).strip()
        sc["head"] = str(sc.get("head") or "")
        sc["sfx"] = str(sc.get("sfx") or "none").lower().strip()
        if sc["sfx"] not in ("horse", "birds", "landslide", "whisper", "sword"):
            sc["sfx"] = "none"
        out.append(sc)
    if len(out) < (10 if strict else 8):
        raise ValueError(f"only {len(out)} usable scenes; use 11-14 scenes with the listed visual types")
    words = sum(len(x["say"].split()) for x in out)
    if strict and words < 100:
        raise ValueError(f"narration too short ({words} words); write 105-165 words")
    if words > max_words:
        raise ValueError(f"narration too long ({words} words); the limit is {max_words - 15}, use fewer and shorter scenes")
    blob = " ".join([x["say"] + " " + x["sub"] + " " + x["head"] + " " + json.dumps(x["visual"], ensure_ascii=False) for x in out]
                    + [str(spec.get(k, "")) for k in ("title", "caption", "comment_q")])
    m = RISKY.search(blob)
    if m:
        raise ValueError(f'the script uses the forbidden word "{m.group(0)}"; rewrite without any religion, caste, politics or insulting words')
    if strict and any(_deva_share(x["say"]) < 0.9 for x in out):
        raise ValueError('"say" must be Devanagari Hindi with no English words')
    if out[0]["visual"]["type"] != "title":
        raise ValueError("first scene must be a title visual")
    mids = [s for s in out[1:-1] if s["visual"]["type"] != "outro"]
    last = out[-1]
    if last["visual"]["type"] != "outro":
        raise ValueError("last scene must be the outro visual")
    spec["scenes"] = [out[0]] + mids + [last]
    spec["title"] = str(spec.get("title") or "शिवगाथा")[:28]
    spec["tag"] = str(spec.get("tag") or "इतिहास")[:16]
    spec["hashtags"] = [h if h.startswith("#") else "#" + h for h in spec.get("hashtags", []) if isinstance(h, str)][:8]
    return spec


def gen_spec(topic, recent, part=None):
    import core as M
    prompt = PROMPT.format(topic=topic, series=series_block(part), safety=SAFETY_RULES, recent="; ".join(r[:70] for r in recent[:12]) or "none")
    limit = 170 if (part and part["n"] > 1) else 190
    fb = ""
    last = None
    for attempt in range(4):
        try:
            raw = M.call_gemini(prompt + fb)
            spec = validate(clean_json(raw), max_words=limit)
            if part and part["n"] > 1:
                spec["part"] = [part["k"], part["n"]]
                spec["title"] = str(part["title"])[:28]
            return spec
        except Exception as ex:
            last = ex
            fb = (f"\n\nYour previous reply was rejected: {ex}. Return ONLY valid JSON following the schema exactly; "
                  f"scene 1 type title, last scene type outro, Hindi Devanagari only, obey the SAFETY RULES.")
            print(f"bad script ({ex}); retry {attempt + 1}/4", file=sys.stderr)
    raise RuntimeError(f"AI did not return a usable script: {last}")


# ------------------------------------------------------------------ voice
def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def audio_len(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def speak(text_dev, text_rom, out):
    """edge-tts fallback: Hindi voice reading Devanagari+English terms; falls back to Roman text / other voices."""
    import edge_tts
    voices = [VOICE] + [v for v in VOICE_BACKUP if v != VOICE]
    texts = [text_dev, text_rom] if VOICE_TEXT == "devanagari" else [text_rom, text_dev]
    for voice in voices:
        for txt in texts:
            if not txt:
                continue
            try:
                asyncio.run(asyncio.wait_for(edge_tts.Communicate(txt, voice, rate=VOICE_RATE, pitch=VOICE_PITCH).save(str(out)), 60))
                if Path(out).exists() and Path(out).stat().st_size > 1500:
                    return voice
            except Exception as ex:
                print(f"voice {voice} failed: {str(ex)[:120]}", file=sys.stderr)
    return None


# ---- Gemini TTS (free tier): far more natural than edge-tts, understands Hindi / Hinglish
TTS = (os.getenv("EXPLAIN_TTS") or "gemini").lower()                 # gemini | edge
GTTS_VOICE = os.getenv("GEMINI_TTS_VOICE") or "Algenib"               # Charon, Kore, Orus, Puck, Fenrir, Aoede, Leda, Zephyr ...
GTTS_MODELS = [m for m in dict.fromkeys([os.getenv("GEMINI_TTS_MODEL") or "", "gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]) if m]
GTTS_LEGACY = ["gemini-2.5-flash-preview-tts"]
GTTS_STYLE = os.getenv("GEMINI_TTS_STYLE") or "a deep, heavy, resonant Indian male narrator speaking Hindi, slow, calm and powerful with great gravitas, like a documentary on Maratha history, with dramatic pauses between sentences"
API = "https://generativelanguage.googleapis.com/v1beta"


def _find_audio(o):
    if isinstance(o, dict):
        if o.get("type") == "audio" and isinstance(o.get("data"), str):
            return o["data"]
        if isinstance(o.get("inlineData"), dict) and isinstance(o["inlineData"].get("data"), str):
            return o["inlineData"]["data"]
        if isinstance(o.get("inline_data"), dict) and isinstance(o["inline_data"].get("data"), str):
            return o["inline_data"]["data"]
        for v in o.values():
            r = _find_audio(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in reversed(o):
            r = _find_audio(v)
            if r:
                return r
    return None


def _save_audio(b64, out):
    import base64
    import wave
    raw = base64.b64decode(b64)
    if raw[:4] == b"RIFF":
        Path(out).write_bytes(raw)
    else:                                   # raw 24 kHz 16-bit mono PCM
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(raw)


def gemini_tts(text, out):
    import requests
    hdr = {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"}
    errs = []
    deadline = time.time() + 300                        # never spend more than ~5 min on the voice
    for model in GTTS_MODELS + GTTS_LEGACY:
        legacy = "2.5" in model
        if legacy:
            text = text.replace("<long pause>", "...")
        for attempt in range(4):
            if time.time() > deadline:
                raise RuntimeError("Gemini TTS: out of time | " + " | ".join(errs[-3:]))
            try:
                if legacy:
                    r = requests.post(f"{API}/models/{model}:generateContent", headers=hdr, timeout=180, json={
                        "contents": [{"parts": [{"text": f"Say in a {GTTS_STYLE} tone: {text}"}]}],
                        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GTTS_VOICE}}}}})
                else:
                    r = requests.post(f"{API}/interactions", headers=hdr, timeout=120, json={
                        "model": model,
                        "input": [{"type": "user_input", "content": [{"type": "text", "text": text,
                                   "annotations": [{"type": "speech_metadata", "style": GTTS_STYLE}]}]}],
                        "response_format": {"type": "audio"},
                        "generation_config": {"speech_config": [{"voice": GTTS_VOICE}]}})
            except requests.RequestException as ex:
                errs.append(f"{model}: network {str(ex)[:80]}")
                time.sleep(5)
                continue
            if r.ok:
                data = None
                try:
                    data = _find_audio(r.json())
                except Exception:
                    pass
                if data:
                    _save_audio(data, out)
                    return f"gemini-tts:{model}:{GTTS_VOICE}"
                errs.append(f"{model}: reply had no audio")
                break
            errs.append(f"{model}: {r.status_code} {r.text[:110]}")
            print(f"Gemini TTS {model}: {r.status_code}", file=sys.stderr)
            if r.status_code == 429:
                if re.search(r"PerDay|per day|daily|limit: 0", r.text, re.I):
                    break                                   # this model's free quota is gone: next model
                time.sleep(min(60, 20 * (attempt + 1)))
                continue
            if r.status_code in (500, 502, 503, 504):
                time.sleep(8)
                continue
            break                                           # 400/403/404: try the next model
    raise RuntimeError("Gemini TTS failed: " + " | ".join(errs[-4:]))


def _silences(path, noise, dur):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise={noise}dB:d={dur}", "-f", "null", "-"],
                       capture_output=True, text=True)
    out, start = [], None
    for ln in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", ln)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", ln)
        if m and start is not None:
            out.append((start, float(m.group(1)), float(m.group(2))))
            start = None
    return out


def _find_cuts(path, spec, total):
    """Times (seconds) where one scene ends and the next begins in the one-piece narration."""
    n = len(spec["scenes"])
    w = [len(sc["say"].split()) + 3 for sc in spec["scenes"]]
    cum, acc = [], 0
    for x in w[:-1]:
        acc += x
        cum.append(acc / sum(w) * total)               # proportional guess (fallback)
    for noise, dur in ((-38, 0.30), (-34, 0.22), (-30, 0.15)):
        sil = _silences(path, noise, dur)
        if len(sil) < n - 1:
            continue
        top = sorted(sorted(sil, key=lambda x: -x[2])[:n - 1])
        cuts = [(a + b) / 2 for a, b, _ in top]
        edges = [0.0] + cuts + [total]
        ok = all(0.4 * (w[i] / sum(w) * total) <= edges[i + 1] - edges[i] <= 2.5 * (w[i] / sum(w) * total) + 1.0 for i in range(n))
        if ok:
            return cuts
    sil = _silences(path, -30, 0.10) or _silences(path, -26, 0.08)
    snapped, used = [], 0
    for c in cum:
        best = min(sil, key=lambda x: abs((x[0] + x[1]) / 2 - c), default=None)
        if best is not None and abs((best[0] + best[1]) / 2 - c) <= 1.3:
            snapped.append((best[0] + best[1]) / 2)
            used += 1
        else:
            snapped.append(c)
    if all(snapped[i] < snapped[i + 1] - 1.0 for i in range(len(snapped) - 1)):
        print(f"scene cuts: word-count estimate snapped to pauses ({used}/{len(cum)})", file=sys.stderr)
        return snapped
    print("scene cuts: using word-count estimate", file=sys.stderr)
    return cum


def _gemini_clips(spec, tmp):
    """ONE request for the whole narration (free tier allows very few requests), then cut it into scenes."""
    n = len(spec["scenes"])
    text = " <long pause> ".join(sc["say"] for sc in spec["scenes"])
    full = tmp / "gemini_full.wav"
    name = gemini_tts(text, full)
    total = audio_len(full)
    cuts = _find_cuts(full, spec, total)
    edges = [0.0] + list(cuts) + [total]
    paths = []
    for i in range(n):
        p = tmp / f"gemini_{i:02d}.wav"
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(full), "-ss", f"{edges[i]:.3f}", "-to", f"{edges[i + 1]:.3f}", "-ar", "44100", "-ac", "1", str(p)])
        paths.append(p)
    return paths, name


def _clips(spec, tmp, provider):
    """One raw clip per scene with the given provider; returns (paths, voice name)."""
    if provider == "gemini":
        return _gemini_clips(spec, tmp)
    paths, name = [], None
    for i, sc in enumerate(spec["scenes"]):
        p = tmp / f"{provider}_{i:02d}.mp3"
        v = speak(sc["say"], sc["sub"], p)
        if not v:
            raise RuntimeError("edge-tts: no voice could be generated")
        name = v
        paths.append(p)
    return paths, name


DEEP = float(os.getenv("EXPLAIN_DEEP") or 0.93)          # <1 = deeper voice (0.93 is about one semitone lower); 1 = off
DEEP_FILTER = ("" if DEEP >= 0.999 else f",aresample=44100,asetrate={int(44100 * DEEP)},aresample=44100,atempo={1 / DEEP:.4f}") + \
    ",equalizer=f=130:t=q:w=1.1:g=4,equalizer=f=3500:t=q:w=1:g=-2,acompressor=threshold=-20dB:ratio=3:attack=8:release=120"
_TRIM = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse,"
         "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse")


def build_audio(spec, tmp, fake=False):
    """One clip per scene -> scene durations; returns (durations, wav path, voice name)."""
    n = len(spec["scenes"])
    used = None
    if fake:
        paths = []
        for i, sc in enumerate(spec["scenes"]):
            p = tmp / f"fake_{i:02d}.wav"
            secs = max(2.4, len(sc["say"].split()) / 2.7)
            _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{secs:.2f}", str(p)])
            paths.append(p)
    else:
        paths, errs = None, []
        for provider in (["gemini", "edge"] if TTS == "gemini" else ["edge"]):
            try:
                paths, used = _clips(spec, tmp, provider)
                break
            except Exception as ex:
                errs.append(str(ex)[:300])
                print(f"voice provider {provider} failed: {ex}", file=sys.stderr)
        if not paths:
            raise RuntimeError("no voice could be generated: " + " || ".join(errs))
    speed = float(os.getenv("EXPLAIN_SPEED") or 1.0)
    durs, wavs = [], []
    for i, p in enumerate(paths):
        t1, wav = tmp / f"t{i:02d}.wav", tmp / f"s{i:02d}.wav"
        flt = _TRIM + DEEP_FILTER + (f",atempo={speed}" if abs(speed - 1.0) > 0.01 else "")
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-af", flt, "-ar", "44100", "-ac", "1", str(t1)])
        dur = max(2.6, audio_len(t1) + 0.2 + 0.55)
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(t1), "-af", "adelay=150|150,apad", "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "1", str(wav)])
        durs.append(dur)
        wavs.append(wav)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{w}'\n" for w in wavs))
    full = tmp / "voice.wav"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", str(full)])
    if os.getenv("EXPLAIN_SFX", "on").lower() not in ("off", "0", "no"):
        try:
            full = mix_sound(spec, durs, full, tmp)
        except Exception as ex:
            print(f"sound design skipped ({str(ex)[:160]}); narration only", file=sys.stderr)
    return durs, full, used


# ------------------------------------------------------------------ BGM + scene sounds (sfx.py), ducked under the narration
def mix_sound(spec, durs, voice_wav, tmp):
    import sfx
    bed = tmp / "bed.wav"
    sfx.mix_bed(durs, [sc.get("sfx", "none") for sc in spec["scenes"]], bed,
                bgm_level=float(os.getenv("BGM_LEVEL") or 0.5), sfx_level=float(os.getenv("SFX_LEVEL") or 0.9), seed=int(time.time()) % 1000)
    out = tmp / "voice_mix.wav"
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(voice_wav), "-i", str(bed), "-filter_complex",
          "[1:a]volume=1.0[b];[b][0:a]sidechaincompress=threshold=0.03:ratio=4:attack=25:release=500:makeup=1[duck];"
          "[0:a][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97", "-ar", "44100", "-ac", "1", str(out)])
    return out


# ------------------------------------------------------------------ render
def render(spec, durs, audio, out_path, preview_dir=None):
    total = sum(durs)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out_path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    gt = 0.0
    prev_key = None
    nframes = 0
    for i, sc in enumerate(spec["scenes"]):
        key = vkey(sc["visual"])
        persist = (key == prev_key)
        prev_key = key
        nf = int(round(durs[i] * FPS))
        for f in range(nf):
            t = f / FPS
            im = draw_frame(spec, i, t + (0.45 if i == 0 else 0.0), gt + t, total, persist)   # scene 1 never starts blank
            p.stdin.write(im.tobytes())
            nframes += 1
            if preview_dir and f in (int(1.6 * FPS), nf - 2):
                im.save(Path(preview_dir) / f"scene{i:02d}_{'a' if f != nf - 2 else 'b'}.png")
        gt += durs[i]
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg failed while rendering the explainer")
    return total


# ------------------------------------------------------------------ caption + run
def build_caption(spec):
    cap = str(spec.get("caption", "")).strip()
    cq = str(spec.get("comment_q") or "").strip()
    pt = spec.get("part")
    if pt:
        cap = f"(भाग {pt[0]}/{pt[1]}) " + cap
    parts = [cap]
    if cq:
        parts.append(f"{cq} कमेंट में बताइए 👇")
    if pt and pt[0] < pt[1]:
        parts.append(f"भाग {pt[0] + 1} जल्द आ रहा है 🚩 फ़ॉलो करें ताकि छूट न जाए।")
    parts.append("🚩 जय शिवराय! कहानी पसंद आई तो सेव और शेयर करें।")
    parts.append(f"रोज़ एक नई कहानी के लिए फ़ॉलो करें @{HANDLE}")
    parts.append("ऐतिहासिक स्रोतों पर आधारित जानकारी।")
    tags = spec.get("hashtags") or []
    base = ["#छत्रपतिशिवाजीमहाराज", "#छत्रपतिसंभाजीमहाराज", "#जयशिवराय", "#मराठा", "#इतिहास", "#shivajimaharaj",
            "#sambhajimaharaj", "#maratha", "#maharashtra", "#history", "#reels"]
    parts.append(" ".join(list(dict.fromkeys(tags + base))[:14]))
    text = "\n\n".join(p for p in parts if p)[:2200]
    m = RISKY.search(text)
    if m:                                                   # last safety net: strip the offending line from the caption
        text = "\n\n".join(p for p in parts if p and not RISKY.search(p))[:2200]
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--topic", default="")
    ap.add_argument("--sample", action="store_true", help="render the built-in sample (no AI, silent) to check the look")
    ap.add_argument("--previews", action="store_true", help="also save a few PNG frames")
    args = ap.parse_args()
    global ACC
    ACC = random.choice(ACCENTS)
    _BGIMG.clear()
    print(VERSION, file=sys.stderr)
    OUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M")
    if args.sample:
        spec = validate(json.loads(json.dumps(SAMPLE)), strict=False)
    else:
        import core as M
        state = load_state()
        recent = [u["topic"] for u in state["used"][-40:]] + [c.split("\n")[0][:80] for c in M.ig_recent_captions(25)]
        if args.topic:
            topic, part, cat = args.topic, None, "Manual"
        else:
            topic, part, cat = plan_next(state)
        print(f"TOPIC: {topic} | category: {cat} | part: {part and (str(part['k']) + '/' + str(part['n']))}", file=sys.stderr)
        spec = gen_spec(topic, recent, part)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        durs, audio, voice = build_audio(spec, tmp, fake=args.sample)
        out = OUT_DIR / f"{stamp}_story.mp4"
        prev = None
        if args.previews or args.sample:
            prev = OUT_DIR / "previews"
            prev.mkdir(exist_ok=True)
        secs = render(spec, durs, audio, out, prev)
    cap = build_caption(spec)
    (OUT_DIR / f"{stamp}_story.txt").write_text(cap, encoding="utf-8")
    print(f"video: {out} ({secs:.0f}s, voice {voice})", file=sys.stderr)
    print(cap)
    if args.dry_run or args.sample:
        return
    import core as M
    try:
        url = M.upload_video(str(out))
        mid = M.publish(url, cap, reel=True)
    except Exception as ex:
        msg = str(ex)
        print(f"POST FAILED: {msg[:400]}", file=sys.stderr)
        if "190" in msg or "OAuth" in msg or "access token" in msg.lower():
            print("-> The Instagram token is not valid. Check the secrets IG_ACCESS_TOKEN (long text starting with IGAA...) "
                  "and IG_USER_ID (digits only). Generate a new token in the Meta dashboard and paste it again.", file=sys.stderr)
        sys.exit(3)                       # 3 = do not retry (the video itself is fine)
    print(f"POSTED Reel: {mid}", file=sys.stderr)
    if not args.topic:
        record_posted(state, topic, part, cat)
        save_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        sys.exit(1)
