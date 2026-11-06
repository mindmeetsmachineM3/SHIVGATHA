"""Procedural sound design (no audio files, no downloads, no copyright): cinematic BGM with a tanpura drone and war-drum pulse,
plus scene sounds: horse walking, birds, landslide, whispering, sword clash.

    mix_bed(scene_durs, scene_sfx, out_wav)  -> writes a mono 44.1 kHz wav (BGM + scene sounds) to lay under the narration
"""
import wave

import numpy as np

SR = 44100


def _rng(seed):
    return np.random.default_rng(seed)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _lp(x, hz):
    """one-pole low-pass (fast, enough for sound effects)"""
    a = np.exp(-2 * np.pi * hz / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def _fft_filter(x, lo=None, hi=None):
    """zero-phase band filter through FFT (fast for the lengths we need)"""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def _env(n, a=0.01, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))


def _add(buf, clip, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[:j - i]


def _fade(x, fin=0.3, fout=0.4):
    n = len(x)
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:min(a, n)] *= np.linspace(0, 1, min(a, n))
    if b:
        x[max(0, n - b):] *= np.linspace(1, 0, len(x[max(0, n - b):]))
    return x


def _norm(x, peak=0.9):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def _reverb(x, rt=0.5, mix=0.25, seed=1):
    n = int(rt * SR)
    ir = _rng(seed).standard_normal(n) * np.exp(-np.arange(n) / SR / (rt / 4))
    ir[0] = 0
    wet = np.fft.irfft(np.fft.rfft(x, len(x) + n) * np.fft.rfft(ir, len(x) + n))[:len(x)]
    return x * (1 - mix) + _norm(wet, np.max(np.abs(x)) + 1e-9) * mix


# ---------------------------------------------------------------- BGM: tanpura drone + low strings + slow dhol pulse
def pluck(freq, dur=3.0):
    t = _t(dur)
    y = np.zeros_like(t)
    for k in range(1, 12):
        y += np.sin(2 * np.pi * freq * k * t * (1 + 0.0004 * k)) / k * np.exp(-t * (0.9 + 0.35 * k))
    return y * np.minimum(1, t / 0.006)


def bgm(dur, seed=5):
    r = _rng(seed)
    t = _t(dur)
    Sa, Pa = 73.42, 110.0                               # D2 and A2
    out = np.zeros_like(t)
    # tanpura cycle: Pa, Sa, Sa, low Sa (about 1 s per string)
    cycle = [Pa * 0.5, Sa * 2, Sa * 2, Sa]
    step = 1.05
    k = 0
    at = 0.0
    while at < dur:
        _add(out, pluck(cycle[k % 4]) * (0.55 if k % 4 else 0.7), at)
        at += step
        k += 1
    # warm pad: detuned sines on Sa, Pa, upper Sa with slow swell
    lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.07 * t + r.uniform(0, 6))
    for f, a in ((Sa, 0.5), (Sa * 1.003, 0.35), (Pa, 0.32), (Pa * 0.997, 0.2), (Sa * 2, 0.22), (Sa * 3, 0.1)):
        out += a * 0.45 * np.sin(2 * np.pi * f * t + r.uniform(0, 6)) * lfo
    # slow war-drum pulse (two hits, a pause)
    hit_t = _t(0.9)
    thump = np.sin(2 * np.pi * (48 + 70 * np.exp(-hit_t * 14)) * hit_t) * np.exp(-hit_t * 5)
    beat = 2.4
    at = 1.0
    while at < dur:
        _add(out, thump * 0.9, at)
        _add(out, thump * 0.55, at + 0.62)
        at += beat
    out = _reverb(out, 1.2, 0.22, 3)
    return _fade(_norm(out, 0.6), 1.2, 1.8)


# ---------------------------------------------------------------- scene sounds
def horse(dur, seed=1):
    r = _rng(seed)
    out = np.zeros(int(dur * SR))
    gait = 1.55                                          # one full 4-beat walk cycle
    at = 0.05
    pat = [0.0, 0.40, 0.80, 1.17]
    while at < dur:
        for i, p in enumerate(pat):
            tt = at + p + r.uniform(-0.012, 0.012)
            n = int(0.16 * SR)
            noise = _fft_filter(r.standard_normal(n), 250, 2600) * _env(n, 0.001, 0.025)
            tm = np.arange(n) / SR
            thump = np.sin(2 * np.pi * (170 + 40 * (i % 2)) * tm) * np.exp(-tm * 38)
            click = _fft_filter(r.standard_normal(n), 2500, 6500) * _env(n, 0.0005, 0.006) * 0.5
            _add(out, (noise * 1.3 + thump * 0.9 + click) * (0.8 + 0.2 * (i % 2)), tt)
        at += gait
    return _fade(_norm(_reverb(out, 0.5, 0.3, 9), 0.9), 0.3, 0.5)


def birds(dur, seed=2):
    r = _rng(seed)
    out = np.zeros(int(dur * SR))
    at = r.uniform(0.1, 0.5)
    while at < dur - 0.2:
        f0 = r.choice([2300, 2800, 3300, 3900, 4400]) * r.uniform(0.92, 1.08)
        trill = r.integers(3, 8)
        gap = r.uniform(0.07, 0.13)
        sweep = r.uniform(-0.35, 0.5)
        for k in range(trill):
            d = r.uniform(0.05, 0.09)
            tt = _t(d)
            f = f0 * (1 + sweep * tt / d) * (1 + 0.02 * np.sin(2 * np.pi * 38 * tt))
            ph = 2 * np.pi * np.cumsum(f) / SR
            c = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.sin(np.pi * tt / d) ** 1.5
            _add(out, c * r.uniform(0.5, 1.0), at + k * gap)
        at += trill * gap + r.uniform(0.7, 2.2)
    return _fade(_norm(_reverb(out, 0.7, 0.25, 4), 0.8), 0.5, 0.7)


def landslide(dur, seed=3):
    r = _rng(seed)
    n = int(dur * SR)
    t = _t(dur)
    peak = 0.35
    env = np.where(t < dur * peak, (t / (dur * peak)) ** 1.6, np.exp(-(t - dur * peak) / (dur * 0.5)))
    rumble = _fft_filter(r.standard_normal(n), None, 260) * env * 6
    gravel = _fft_filter(r.standard_normal(n), 1800, 7000) * env ** 1.5 * 0.5
    out = rumble + gravel
    cnt = int(10 + dur * 9)
    for _ in range(cnt):
        tt = r.uniform(0.05, dur - 0.25)
        e = env[min(n - 1, int(tt * SR))]
        if r.random() > e + 0.15:
            continue
        m = int(r.uniform(0.08, 0.22) * SR)
        c = _fft_filter(r.standard_normal(m), r.uniform(120, 350), r.uniform(900, 2400)) * _env(m, 0.001, r.uniform(0.02, 0.06))
        _add(out, c * r.uniform(1.2, 3.0) * e, tt)
    return _fade(_norm(_reverb(out, 0.9, 0.2, 6), 0.95), 0.2, 0.8)


def whisper(dur, seed=4):
    r = _rng(seed)
    n = int(dur * SR)
    out = np.zeros(n)
    for lo, hi in ((600, 1700), (1500, 3800), (3500, 7000)):
        nz = _fft_filter(r.standard_normal(n), lo, hi)
        am = _fft_filter(r.standard_normal(n), None, 7)
        am = np.clip(am / (np.std(am) + 1e-9), -1, 3) * 0.5 + 0.5          # syllable-rate wobble
        out += nz * np.clip(am, 0, 1.5) ** 2
    # soft breathy swells so it feels like several people murmuring
    t = _t(dur)
    out *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t + r.uniform(0, 6)) ** 2
    return _fade(_norm(_reverb(out, 0.8, 0.35, 8), 0.8), 0.6, 0.8)


def sword(dur, seed=6):
    r = _rng(seed)
    out = np.zeros(int(dur * SR))
    partials = [(1870, 1.0, 0.9), (2790, 0.8, 0.7), (4120, 0.6, 0.45), (5510, 0.45, 0.3), (7420, 0.3, 0.2), (9100, 0.18, 0.12)]
    # draw: a rising shing
    n = int(0.35 * SR)
    sh = _fft_filter(r.standard_normal(n), 2500, 9000) * np.sin(np.pi * np.arange(n) / n) ** 2
    _add(out, sh * 0.5, 0.05)
    at = 0.55
    while at < dur - 0.4:
        base = r.uniform(0.9, 1.15)
        ln = 1.1
        tt = _t(ln)
        ring = np.zeros_like(tt)
        for f, a, dc in partials:
            ring += a * np.sin(2 * np.pi * f * base * tt + r.uniform(0, 6)) * np.exp(-tt / dc)
        m = int(0.03 * SR)
        hit = _fft_filter(r.standard_normal(m), 1500, 9000) * _env(m, 0.0005, 0.008) * 3.5
        low = np.sin(2 * np.pi * 260 * tt[:m * 2]) * np.exp(-tt[:m * 2] * 90)
        c = ring * 0.35 * np.minimum(1, tt / 0.001)
        c[:m] += hit
        c[:m * 2] += low * 0.8
        _add(out, c * r.uniform(0.7, 1.0), at)
        at += r.choice([0.28, 0.4, 0.55, 0.9, 1.3])
    return _fade(_norm(_reverb(out, 0.6, 0.25, 11), 0.9), 0.05, 0.6)


SFX = {"horse": horse, "birds": birds, "landslide": landslide, "whisper": whisper, "sword": sword}
# level of every scene sound relative to the BGM bed (they all sit under the narration anyway)
LEVEL = {"horse": 0.9, "birds": 0.7, "landslide": 1.0, "whisper": 0.55, "sword": 0.9}


def _load(path, dur):
    """optional: your own royalty-free recording (any format ffmpeg reads), looped/trimmed to dur seconds"""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<f4").astype(float)
    if len(x) < 100:
        raise ValueError("empty audio")
    n = int(dur * SR)
    x = np.tile(x, n // len(x) + 1)[:n]
    return _norm(x, 0.9)


def _own(name):
    from pathlib import Path
    for ext in ("wav", "mp3", "m4a", "ogg"):
        p = Path(__file__).parent / "assets" / "sfx" / f"{name}.{ext}"
        if p.exists():
            return p
    return None


def mix_bed(durs, kinds, out_path, bgm_level=0.5, sfx_level=0.9, seed=0):
    """assets/sfx/bgm.mp3 and assets/sfx/<horse|birds|landslide|whisper|sword>.wav (optional) replace the built-in synthesized sounds"""
    total = float(sum(durs))
    own_bgm = _own("bgm")
    try:
        base = _fade(_load(own_bgm, total + 0.5), 1.2, 1.8) * 0.6 if own_bgm else bgm(total + 0.5, seed + 5)
    except Exception:
        base = bgm(total + 0.5, seed + 5)
    bed = base[:int(total * SR)] * bgm_level
    at = 0.0
    for i, (d, k) in enumerate(zip(durs, kinds)):
        fn = SFX.get(k)
        if fn:
            own = _own(k)
            try:
                clip = _load(own, d + 0.3) if own else fn(d + 0.3, seed + 17 * (i + 1))
            except Exception:
                clip = fn(d + 0.3, seed + 17 * (i + 1))
            clip = _fade(clip, 0.25, 0.45) * LEVEL[k] * sfx_level * 0.55
            _add(bed, clip, max(0.0, at - 0.1))
        at += d
    bed = np.clip(bed, -1, 1)
    pcm = (bed * 32767).astype("<i2")
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path


if __name__ == "__main__":
    import sys
    from pathlib import Path
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(exist_ok=True)
    kinds = ["horse", "birds", "landslide", "whisper", "sword", "none"]
    mix_bed([6.0] * len(kinds), kinds, out / "bed_demo.wav")
    for k, fn in SFX.items():
        x = fn(5.0, 1)
        with wave.open(str(out / f"{k}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((x * 0.8 * 32767).astype("<i2").tobytes())
    print("demo written")
