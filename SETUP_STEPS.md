# Shivgatha setup (navin account, ~45 min)

## 0. Instagram account (5 min)
1. Navin account banva (nav suggestion: **Shivgatha | शिवगाथा**, handle: `shivgatha` kinva `shivgatha.official`, jo free asel to).
2. Settings -> Account type and tools -> Switch to professional account -> **Creator**.
3. Profile picture: `assets/profile_picture.png`. Highlights covers: `assets/cover_*.png` (shivaji, sambhaji, forts, battles).
4. Bio (copy-paste):
   ```
   🚩 छत्रपति शिवाजी महाराज और संभाजी महाराज की कहानियाँ
   रोज़ 3 नई कहानियाँ | इतिहास, किले, रणनीति
   जय शिवराय
   ```

## 1. Meta app madhe navin account add kara (10 min)
Junya Myuibot sathi vaparleli **ch Meta app vapra** (Instagram login wali).
1. developers.facebook.com -> My Apps -> app -> **App roles -> Roles -> Add People -> Instagram Testers** -> navin handle taka.
2. Instagram app (navin account): Settings -> **Website permissions -> Apps and websites -> Tester invites -> Accept**.
3. Meta app -> Instagram -> **API setup with Instagram login -> Generate access token** (navin account select kara -> Allow).
4. **Instagram account ID** (IG_USER_ID, fakt digits) ani **Access token** (IG_ACCESS_TOKEN, `IGAA...` lamb text) copy kara.

## 2. GitHub: navin repo (10 min)
1. New repository -> `shivgatha-automation` -> **Private** -> Create.
2. Ya folder madhle sarv files upload kara (`.github/workflows`, `fonts`, `assets` folders sudha). `.github` upload hot nasel tar "Create new file" madhe `.github/workflows/post.yml` path taka ani content paste kara.
3. Settings -> Secrets and variables -> Actions -> **Secrets**:
   | Name | Value |
   |---|---|
   | GEMINI_API_KEY | aistudio.google.com/apikey (**navin account/project cha vegla key ghya**, kaaran 3 Reels/day + 2 junhe page ekach quota vaparat astil) |
   | GROQ_API_KEY | junhach (optional) |
   | IG_USER_ID | navin account cha ID |
   | IG_ACCESS_TOKEN | navin account cha token |
   | CLOUDINARY_CLOUD_NAME | junhach |
   | CLOUDINARY_UPLOAD_PRESET | junhach (unsigned) |
   | GH_PAT | fine-grained token, **ya repo** sathi, Secrets = Read and write (weekly token refresh sathi) |
4. **Variables** (optional):
   | Name | Value |
   |---|---|
   | IG_HANDLE | tumcha handle (uda. `shivgatha`) |
   | BRAND_NAME | `शिवगाथा` |
   | GEMINI_TTS_VOICE | `Algenib` (gravelly, deep). Dusre deep voices: `Orus`, `Alnilam`, `Gacrux`, `Charon` |
   | EXPLAIN_DEEP | `0.93` (jast deep = `0.90`, kami = `0.96`, band = `1`) |
   | EXPLAIN_SPEED | `1.0` (halu havi tar `0.95`) |
   | EXPLAIN_SFX | `on` (BGM + scene sounds). `off` = fakt voice |
   | BGM_LEVEL | `0.5` (jast awaj = `0.8`, kami = `0.3`) |
   | SFX_LEVEL | `0.9` (horse/birds/sword sounds cha awaj) |
   | SERIES_SHARE | `0.5` (mothya goshti Part 1/2/3 madhe, 0 = nehmi ek video) |

## 3. Test (10 min)
1. Actions -> **Shivgatha story Reel** -> Run workflow -> `diagnose` = true. Log madhe account ani quota dista pahije.
2. Run workflow -> `dry_run` = true (default). Shevti **Artifacts -> shivgatha-output** download kara: video baghha, voice aika.
   Voice avadla nahi tar `GEMINI_TTS_VOICE` badla (Orus / Alnilam) kinva `EXPLAIN_DEEP` badla.
3. Chhan watla tar `dry_run` = **false** -> pahila Reel post hoto.
4. Aata apoap: roj **07:37, 12:37, 19:37 IST**.

## Niyam
- Pahile 4-5 divas post kelelya Reels **tumhi swatah baghha** (facts ani tone). Kahi chukla tar Instagram madhun delete kara ani `RISKY` list (story.py) madhe shabda vadhva.
- Navin account var pahilya 1-2 athavdyat 1-2 Reels roj thevne safe, mag 3 var jaa (workflow madhe 2 cron lines kadhun).
- Followers chi guarantee nahi. Insights madhe saves ani watch time baghha.
- Actions minutes: 3 Reels roj = ~600-750 min/mahina (private repo free limit ~2000). Junya repos cha usage pan milun Settings -> Billing madhe tapasa.

## Sound (BGM + horse, birds, landslide, whisper, sword)
- Sarv sounds code madhun banvle jatat (copyright cha prashna nahi). Pratyek scene la AI yogya sound nivadto.
- Swatahchi royalty-free recordings vaprayachya astil tar `assets/sfx/` folder madhe thevaa: `bgm.mp3`, `horse.wav`, `birds.wav`, `landslide.wav`, `whisper.wav`, `sword.wav`. Je file asel tya cha vaprat yeil, baki built-in.
