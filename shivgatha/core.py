"""Shared plumbing: AI (Gemini free tier + Groq free backup), Cloudinary hosting, Instagram publishing.

    python core.py --diagnose        # is the token valid? how much of the publish quota is used?
    python core.py --refresh-token   # refresh the 60-day Instagram token (the weekly workflow does this)
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GRAPH = "https://graph.instagram.com/v21.0"
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
_FALLBACKS = None


# ------------------------------------------------------------------ AI
def _discover_fallbacks():
    """Flash models this key can use (newest first); each has its own free quota."""
    global _FALLBACKS
    if _FALLBACKS is not None:
        return _FALLBACKS
    _FALLBACKS = []
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                         headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=20)
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        names = [n for n in names if "flash" in n and n != GEMINI_MODEL
                 and not re.search(r"image|tts|live|audio|embed|thinking|exp|robotics|computer", n)]

        def key(n):
            v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
            return (-(float(v.group(1)) if v else 0), "lite" not in n, n)
        names.sort(key=key)
        _FALLBACKS = names[:4]
    except Exception as ex:
        print(f"could not list models: {ex}", file=sys.stderr)
    print(f"fallback models: {_FALLBACKS or 'none'}", file=sys.stderr)
    return _FALLBACKS


def call_gemini(prompt):
    """Main model -> other flash models -> main again; busy/limit aware; Groq as last resort. Returns JSON text."""
    dead, last = set(), ""
    plan = [("main", 0), ("main", 20), ("fb", 0), ("main", 45), ("fb", 30), ("main", 90)]
    if os.getenv("GROQ_API_KEY"):
        plan = [("main", 0), ("fb", 0), ("main", 20), ("fb", 20)]
    for who, wait in plan:
        models = [GEMINI_MODEL] if who == "main" else _discover_fallbacks()
        models = [m for m in models if m not in dead]
        if not models:
            continue
        if wait:
            print(f"Gemini busy/limited, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
        for model in models:
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8}},
                    timeout=90)
            except requests.RequestException as ex:
                last = f"network error [{model}]: {ex}"
                continue
            if r.ok:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            last = f"Gemini API error {r.status_code} [{model}]: {r.text[:300]}"
            print(f"Gemini {model}: {r.status_code}", file=sys.stderr)
            if r.status_code in (400, 401, 403) and model == GEMINI_MODEL:
                raise RuntimeError(last)       # bad key / bad request: retrying will not help
            if r.status_code in (400, 401, 403, 404):
                dead.add(model)
            elif r.status_code == 429 and re.search(r"PerDay|per day|daily", r.text, re.I):
                dead.add(model)                # daily free quota used up for this model
            elif r.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(last)
    if os.getenv("GROQ_API_KEY"):
        print("Gemini unavailable -> Groq backup", file=sys.stderr)
        return call_groq(prompt)
    raise RuntimeError(last or "Gemini unavailable")


def call_groq(prompt):
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
    base = "https://api.groq.com/openai/v1"
    model = os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
    tried = False
    for _ in range(4):
        try:
            r = requests.post(f"{base}/chat/completions", headers=headers, timeout=90, json={
                "model": model, "temperature": 0.8, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": "Reply with one valid JSON object only."},
                             {"role": "user", "content": prompt}]})
        except requests.RequestException:
            time.sleep(10)
            continue
        if r.ok:
            return r.json()["choices"][0]["message"]["content"]
        if r.status_code in (400, 404) and not tried:
            tried = True
            try:
                ids = [m["id"] for m in requests.get(f"{base}/models", headers=headers, timeout=20).json()["data"]]
                ids = [i for i in ids if re.search(r"llama|gpt-oss|qwen", i) and not re.search(r"guard|whisper|tts|vision|prompt", i)]
                ids.sort(key=lambda i: (not re.search(r"70b|120b|large|versatile", i), i))
                if ids:
                    model = ids[0]
                    continue
            except Exception:
                pass
        if r.status_code in (429, 500, 502, 503):
            time.sleep(15)
            continue
        break
    raise RuntimeError(f"Groq failed (model {model})")


# ------------------------------------------------------------------ Cloudinary + Instagram
def upload_video(path):
    cloud, preset = os.environ["CLOUDINARY_CLOUD_NAME"], os.environ["CLOUDINARY_UPLOAD_PRESET"]
    with open(path, "rb") as f:
        r = requests.post(f"https://api.cloudinary.com/v1_1/{cloud}/video/upload",
                          data={"upload_preset": preset}, files={"file": f}, timeout=300)
    if not r.ok:
        raise RuntimeError(f"video upload failed: {r.text[:300]}")
    return r.json()["secure_url"]


def get_token():
    return os.environ["IG_ACCESS_TOKEN"]


def publish(media_url, caption, reel=True):
    token, ig_id = get_token(), os.environ["IG_USER_ID"]
    payload = ({"media_type": "REELS", "video_url": media_url, "share_to_feed": "true", "thumb_offset": "1500"}
               if reel else {"image_url": media_url})
    r = requests.post(f"{GRAPH}/{ig_id}/media", data={**payload, "caption": caption, "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"create container failed: {r.text}")
    cid = r.json()["id"]
    for _ in range(90):
        s = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code", "access_token": token}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"container error: {s}")
        time.sleep(5)
    r = requests.post(f"{GRAPH}/{ig_id}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"publish failed: {r.text}")
    return r.json()["id"]


def ig_recent_captions(limit=25):
    """What is really on the account (best effort; empty list on any problem). Used to avoid repeating topics."""
    try:
        r = requests.get(f"{GRAPH}/{os.environ['IG_USER_ID']}/media",
                         params={"fields": "caption", "limit": limit, "access_token": get_token()}, timeout=30)
        return [m.get("caption", "") for m in r.json().get("data", []) if m.get("caption")]
    except Exception as ex:
        print(f"could not read recent posts: {ex}", file=sys.stderr)
        return []


def diagnose():
    token, ig_id = get_token(), os.environ["IG_USER_ID"]
    for label, path, fields in [("account", "me", "user_id,username,account_type,media_count"),
                                ("publish quota", f"{ig_id}/content_publishing_limit", "quota_usage,config"),
                                ("recent media", f"{ig_id}/media", "id,timestamp,media_type")]:
        r = requests.get(f"{GRAPH}/{path}", params={"fields": fields, "limit": 5, "access_token": token}, timeout=30)
        print(f"--- {label}: HTTP {r.status_code}")
        print(r.text[:600])


def refresh_token():
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": get_token()}, timeout=30)
    r.raise_for_status()
    j = r.json()
    out = os.getenv("NEW_TOKEN_FILE")
    if out:
        Path(out).write_text(j["access_token"], encoding="utf-8")   # the workflow stores it as the new secret
    print("Token refreshed, valid for days:", j.get("expires_in", 0) // 86400)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--refresh-token", action="store_true")
    a = ap.parse_args()
    if a.diagnose:
        diagnose()
    elif a.refresh_token:
        refresh_token()
    else:
        ap.print_help()
