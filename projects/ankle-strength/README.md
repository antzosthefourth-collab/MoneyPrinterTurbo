# Stronger Ankles in 80 Seconds — build pipeline

A small, repeatable project that turns a fixed script + ankle-exercise footage into a
vertical short (1080×1920, 30 fps, ~82s) with voiceover, burned-in captions, and light
music — plus 45s and 15s cuts. It **reuses the MoneyPrinterTurbo pipeline**; it does
not reimplement TTS, captioning, or FFmpeg.

The default path needs **no paid API keys** (free edge-tts voice + your own/Pexels
footage). You run the render on your machine.

## Why this design
Successful instructional shorts use **real footage + one consistent voiceover +
captions**, not an AI-generated person — current video models visibly warp feet and
ankles. So the "consistent instructor" here is the **voice**. (See `CLAUDE.md`.)

## 1. Prerequisites
- Python env for this repo (`uv sync` or `pip install -r requirements.txt`).
- FFmpeg on `PATH` (or set `IMAGEIO_FFMPEG_EXE`). ffprobe (bundled with ffmpeg) is
  used by `verify.py`.
- `config.toml` at the repo root (copy from `config.example.toml`). Defaults are fine:
  - Local footage path → **no keys needed** (LLM skipped; edge-tts is free).
  - Pexels path → set `pexels_api_keys = ["YOUR_KEY"]` under `[app]`.
  - `subtitle_provider = "edge"` (default) or `"whisper"`.

## 2. Add footage
Put **vertical** clips that clearly show feet/ankles/lower legs in
`projects/ankle-strength/assets/clips/`, named to match the order:

```
00_hook.mp4  01_calf_raises.mp4  02_tibialis_raises.mp4  03_band_4way.mp4
04_single_leg_balance.mp4  05_toe_walks.mp4  06_heel_walks.mp4
07_short_foot.mp4  08_lateral_step_downs.mp4
```

`build.py` copies these into `storage/local_videos/ankle/` automatically (required by
the pipeline's path-security check). Missing clips are skipped; the pipeline loops
footage to fill the narration.

No clips yet? Use Pexels instead (step 3, `--source pexels`). Search terms are in
`content/shotlist.md`.

## 3. Render
```bash
# from the repo root
python projects/ankle-strength/build.py                 # local clips (default)
python projects/ankle-strength/build.py --source pexels # auto-download footage
python projects/ankle-strength/build.py --no-cuts       # master only
```
Outputs land in `storage/tasks/ankle-strength-master/`:
- `final-1.mp4` (raw master from the pipeline)
- `cuts/master-82s.mp4`, `cuts/cut-45s.mp4`, `cuts/hook-15s.mp4`

## 4. Verify
```bash
python projects/ankle-strength/verify.py
```
Checks duration (~82s), 1080×1920 @ ~30 fps, AAC audio, and that `subtitle.srt` exists.

## Tuning
- **Length** is driven by the voiceover. If the master isn't ~82s, edit
  `content/transcript.md` (word count) or nudge `voice_rate` in `build.py` (0.95–1.05).
- **Alignment**: clips play sequentially; reorder `CLIP_ORDER`/footage and adjust
  `video_clip_duration` so each exercise roughly fills its window. Frame-exact
  per-segment sync is out of scope for this MVP.
- **Voice**: change `voice_name` (any edge-tts voice, e.g. `en-US-AriaNeural-Female`).
- **Cuts**: edit `CUT_SPECS` in `build.py` (they snap to caption boundaries).
- **Custom captions**: the pipeline auto-generates `subtitle.srt`. To force the exact
  wording in `content/captions.srt`, render with `stop_at` left as-is, then replace
  `storage/tasks/ankle-strength-master/subtitle.srt` and re-run the video step. (The
  auto SRT is recommended for MVP — it's timing-accurate to the narration.)

## Optional: generative B-roll (off by default)
For a couple of *establishing* shots only (never the detailed ankle work). Prompts are
in `prompts/broll_prompts.md`. Wiring it up adds a gated source in
`app/services/material.py` behind `enable_generative_broll` in config — see the plan.
Generate clips externally (fal.ai LTX/Wan or Veo 3.1, native 9:16) and drop them into
`assets/clips/` like any other local footage; no code change needed for that route.

## Files
```
projects/ankle-strength/
  build.py        driver (reuses task.start + ffmpeg helpers)
  verify.py       ffprobe checks
  CLAUDE.md       project rules (safety/visual/audio/quality)
  README.md       this file
  content/        transcript.md, shotlist.md, captions.srt, metadata.md
  prompts/        broll_prompts.md (optional)
  assets/clips/   your vertical exercise footage
```
