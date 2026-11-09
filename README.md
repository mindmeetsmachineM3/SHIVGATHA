# Shivgatha: daily Hindi story Reels on Chhatrapati Shivaji Maharaj and Chhatrapati Sambhaji Maharaj

Fully automatic, zero-cost Instagram Reels (3 a day): the AI picks a new, well-documented story, writes a Hindi script,
a deep narrator voice reads it, parchment-style animated graphics are rendered (forts, maps, timelines, scrolls, no faces/paintings),
and the Reel is posted through the Instagram API.

- `story.py`: topic planner (never repeats, big stories become Part 1/2/3), safe-history prompt, visuals, voice, caption, posting.
- `core.py`: Gemini/Groq, Cloudinary upload, Instagram publish, token refresh (same plumbing as the other pages).
- `sfx.py`: BGM (tanpura drone + slow war-drum) and scene sounds (horse walking, birds, landslide, whispering, sword clash), all generated in code, mixed softly under the voice. The AI picks the sound per scene.
- `fonts/`: Noto Devanagari + DejaVu (open licence) so Hindi renders correctly everywhere.
- `.github/workflows/post.yml`: 3 posts a day (07:37, 12:37, 19:37 IST). `refresh-token.yml`: weekly token refresh.
- `state.json`: memory of posted topics (created and committed by the bot).

## Safety (so the page stays free of controversy)
Every script is checked automatically. A video is rejected and rewritten if it contains religion, caste, politics or abusive words
(see `RISKY` in `story.py`), is not in Devanagari Hindi, or is too long. The prompt (`SAFETY_RULES`) only allows well-documented history,
forbids invented quotes/dates, frames conflicts as political/military events only, and tells the AI to tell painful events with dignity.
Visuals never show faces or paintings of the Maharajas.

## Local test
```
pip install -r requirements.txt
python story.py --sample        # renders the look with a fake voice, saves output/previews/*.png
python story.py --dry-run       # real script + real voice, nothing posted (needs GEMINI_API_KEY)
```
See `SETUP_STEPS.md` for the full new-account setup.

## Look (THEME)
THEME=paper (default) = paper-craft diorama look, drawn in code, no cost. THEME=parchment = the old parchment look.
