"""Makes the profile picture and highlight covers (run once: python gen_assets.py)."""
import story as S
from PIL import Image, ImageDraw

S.ACC = S.SAFF


def centered(d, y, text, kind, size, col):
    S.text_c(d, S.W // 2, y, text, S.font(kind, size), col)


# profile picture: parchment circle, seal, flag
bg = S.background().crop((40, 300, 680, 940))
d = ImageDraw.Draw(bg)
S.seal(d, 320, 320, 290, 1.0)
S.flag(d, 292, 110, 66, S.SAFF, 0.4, 1.0)
S.fort(d, 320, 480, 330, 210, (60, 38, 18), 1.0, 0.4, with_flag=False)
centered_x = lambda y, t, k, sz, c: S.text_c(d, 320, y, t, S.font(k, sz), c)
centered_x(488, "शिवगाथा", "serifb", 62, S.INK)
bg.resize((1080, 1080), Image.LANCZOS).save("assets/profile_picture.png")

covers = {"shivaji": ("शिवाजी\nमहाराज", "flag"), "sambhaji": ("संभाजी\nमहाराज", "seal"), "forts": ("किले", "fort"), "battles": ("रणनीति", "map")}
for name, (title, icon) in covers.items():
    im = S.background()
    d = ImageDraw.Draw(im)
    if icon == "flag":
        S.flag(d, 300, 330, 120, S.SAFF, 0.3, 1.0)
    elif icon == "seal":
        S.seal(d, 360, 480, 190, 1.0)
        d.polygon([(360, 410), (400, 480), (360, 550), (320, 480)], fill=S.SAFF)
    elif icon == "fort":
        S.ridge(d, 700, 90, (150, 116, 76), 3)
        S.fort(d, 360, 720, 520, 360, (60, 38, 18), 1.0, 0.3)
    else:
        S.ridge(d, 760, 120, (190, 168, 128), 12)
        pts = [(150, 640), (300, 520), (430, 580), (560, 400)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for k in range(12):
                d.ellipse((x0 + (x1 - x0) * k / 12 - 4, y0 + (y1 - y0) * k / 12 - 4, x0 + (x1 - x0) * k / 12 + 4, y0 + (y1 - y0) * k / 12 + 4), fill=S.MAROON)
        for x, y in pts:
            d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=S.PARCH2, outline=S.SAFF, width=4)
    for j, line in enumerate(title.split("\n")):
        centered(d, 830 + j * 100, line, "serifb", 84, S.INK)
    im.save(f"assets/cover_{name}.png")
print("assets done")
