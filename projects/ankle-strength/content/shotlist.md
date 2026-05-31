# Shot list — "Stronger Ankles in 80 Seconds"

Vertical 9:16 (1080×1920), 30 fps, ~82s master. Materials play in **sequential**
order, so the clip order below MUST match the narration order. Aim for one clip per
exercise window (~9–10s). Every clip should clearly show the **feet, ankles, and
lower legs** — waist-down or full-body framing, not face-heavy.

## Clip order (drives `video_materials` in build.py)

| # | File (in assets/clips/) | On-screen | Narration line | Pexels search fallback |
|---|---|---|---|---|
| 0 | `00_hook.mp4`            | ~0–8s   | "Weak ankles? Do this quick routine three times a week." | ankle pain, ankle close up |
| 1 | `01_calf_raises.mp4`     | ~8–18s  | "First, calf raises…"            | calf raise, heel raise |
| 2 | `02_tibialis_raises.mp4` | ~18–28s | "Next, tibialis raises…"         | toe lift, tibialis raise, shin exercise |
| 3 | `03_band_4way.mp4`       | ~28–40s | "…resistance band in four directions…" | resistance band ankle, foot band exercise |
| 4 | `04_single_leg_balance.mp4` | ~40–50s | "Next, single-leg balance…"   | single leg balance, balance exercise |
| 5 | `05_toe_walks.mp4`       | ~50–58s | "Then toe walks…"                | tip toe walk, walking on toes |
| 6 | `06_heel_walks.mp4`      | ~58–66s | "Now heel walks…"                | heel walk, walking on heels |
| 7 | `07_short_foot.mp4`      | ~66–76s | "Next, short-foot work…"         | barefoot arch, foot exercise barefoot |
| 8 | `08_lateral_step_downs.mp4` | ~76–82s | "Finish with lateral step-downs…" + safety outro | step down exercise, lateral step |

Notes:
- Timings are approximate — the real length is set by the voiceover. Verify with
  `verify.py` after rendering and tweak `voice_rate` / clip durations.
- If you have fewer than 9 clips, the pipeline loops/repeats footage to fill; if you
  have more, extras after the audio ends are dropped.

## Export-cut boundaries (used by build.py)

Cuts are contiguous from the start and snapped to the nearest caption boundary so they
end on a clean sentence:
- **82s master** — full video.
- **~45s cut** — hook + first ~4 exercises (calf raises → single-leg balance).
- **~15s hook** — hook + start of calf raises + the CTA feel.

To change to non-contiguous "best of" cuts, edit `CUT_SPECS` in build.py.
