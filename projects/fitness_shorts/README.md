# fitness_shorts — config-driven vertical short engine

A thin, reusable layer on top of MoneyPrinterTurbo for making vertical (9:16,
1080×1920, 30 fps) instructional shorts: fixed script → voiceover → burned-in captions
→ light music → master + export cuts. It reuses the core pipeline
(`app.services.task.start`, the FFmpeg helper, edge-tts, captioning) — no
reimplementation.

Design rationale (see `../ankle-strength/CLAUDE.md`): use **real footage + one
consistent voiceover + captions**, not an AI-generated person — current video models
warp feet/ankles. The "consistent instructor" is the **voice**.

## A "project" is a folder
```
projects/<your-short>/
  config.yaml      # all settings (see TEMPLATE/config.yaml)
  transcript.md    # narration, read verbatim (LLM skipped)
  assets/clips/    # optional local footage (else --source pexels)
```

## Make a new short
```bash
cp -r projects/fitness_shorts/TEMPLATE projects/my-short
# edit projects/my-short/config.yaml + transcript.md, add clips
python projects/fitness_shorts/run.py projects/my-short --verify
```

## Run an existing project
```bash
python projects/fitness_shorts/run.py projects/ankle-strength            # local
python projects/fitness_shorts/run.py projects/ankle-strength --source pexels
python projects/fitness_shorts/run.py projects/ankle-strength --no-cuts --verify
```
Outputs land in `storage/tasks/<task_id>/`:
`final-1.mp4` (raw master) and `cuts/{master,<label>}.mp4`.

## Files
- `engine.py` — `ProjectConfig`, `load_config`, `read_transcript`, `build_params`,
  `run`, `make_cuts`, `verify`. Heavy imports (app/loguru/yaml) are deferred so the
  pure helpers (transcript/SRT parsing, cut snapping) stay unit-testable.
- `run.py` — generic CLI.
- `TEMPLATE/` — copy to start a new short.

Per-project `build.py` / `verify.py` wrappers (e.g. in `ankle-strength/`) just call
`load_config()` then `run()` / `verify()`.

## config.yaml keys
`task_id, subject, stage_subdir, voice_name, voice_rate, bgm_type, bgm_volume,
video_clip_duration, target_seconds, duration_tolerance, clip_order[], pexels_terms[],
cuts[{label,seconds}], subtitle{position,custom_position,font_name,font_size,
text_fore_color,stroke_color,stroke_width}, transcript_file`.

## Notes / limits
- Length is voiceover-driven — tune `voice_rate` / transcript word count to hit
  `target_seconds` (verify checks ±`duration_tolerance`).
- Clips play **sequentially**; order footage to match the script. Frame-exact
  per-segment sync is out of scope.
- Cuts are contiguous from the start, snapped to caption boundaries (edit `cuts`).
