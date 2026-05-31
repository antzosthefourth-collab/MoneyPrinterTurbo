#!/usr/bin/env python3
"""
Driver for the "Stronger Ankles in 80 Seconds" vertical fitness short.

This reuses the MoneyPrinterTurbo pipeline end-to-end (no duplication of TTS /
captioning / FFmpeg logic). It:

  1. Reads the fixed narration from content/transcript.md (so the LLM is skipped).
  2. Stages local clips from assets/clips/ into storage/local_videos/ankle/
     (required: app/services/video.preprocess_video only accepts materials inside
     that directory).
  3. Builds VideoParams for a 9:16 / 1080x1920 / 30fps short and renders the master
     via app.services.task.start().
  4. Produces 45s and 15s export cuts by trimming the master, snapping cut points to
     caption boundaries, using the repo's own FFmpeg binary resolver.

Run from anywhere:  python projects/ankle-strength/build.py
Options:            --source pexels   (skip local staging, auto-download footage)
                    --no-cuts         (master only)

The actual render is meant to run on your machine. No paid API keys are required for
the default local+edge-tts path. See README.md.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

# Make `import app.*` work regardless of the current working directory.
PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(PROJECT_DIR))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from loguru import logger  # noqa: E402

from app.models.schema import MaterialInfo, VideoParams  # noqa: E402
from app.services import task  # noqa: E402
from app.services.video import get_ffmpeg_binary  # noqa: E402
from app.utils import utils  # noqa: E402

TASK_ID = "ankle-strength-master"

# Clip order MUST match the narration order in content/transcript.md.
# Filenames are looked up in assets/clips/ and staged into storage/local_videos/ankle/.
CLIP_ORDER = [
    "00_hook.mp4",
    "01_calf_raises.mp4",
    "02_tibialis_raises.mp4",
    "03_band_4way.mp4",
    "04_single_leg_balance.mp4",
    "05_toe_walks.mp4",
    "06_heel_walks.mp4",
    "07_short_foot.mp4",
    "08_lateral_step_downs.mp4",
]

# Pexels fallback search terms (used with --source pexels).
PEXELS_TERMS = [
    "calf raise",
    "ankle mobility exercise",
    "resistance band foot",
    "single leg balance",
    "walking on toes",
    "barefoot foot exercise",
    "lateral step down",
]

# Export cuts: (label, target_seconds). Contiguous from the start, snapped to the
# nearest caption boundary so each cut ends on a clean sentence. Edit freely.
CUT_SPECS = [
    ("cut-45s", 45.0),
    ("hook-15s", 15.0),
]


def read_transcript() -> str:
    """Read content/transcript.md, dropping note lines (# ... or <!-- ... -->)."""
    path = os.path.join(PROJECT_DIR, "content", "transcript.md")
    lines = []
    in_comment = False
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        if stripped.startswith("#"):
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    if not text:
        raise SystemExit(f"transcript is empty after stripping notes: {path}")
    return text


def stage_local_materials() -> list:
    """Copy assets/clips/* into storage/local_videos/ankle/ and return ordered
    MaterialInfo list. Honors CLIP_ORDER; ignores missing entries with a warning."""
    src_dir = os.path.join(PROJECT_DIR, "assets", "clips")
    dst_dir = os.path.join(utils.storage_dir("local_videos", create=True), "ankle")
    os.makedirs(dst_dir, exist_ok=True)

    materials = []
    for name in CLIP_ORDER:
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            logger.warning(f"missing clip (skipping): {src}")
            continue
        shutil.copy2(src, os.path.join(dst_dir, name))
        # url is relative to storage/local_videos (subdir allowed by file_security).
        materials.append(MaterialInfo(provider="local", url=os.path.join("ankle", name)))

    if not materials:
        raise SystemExit(
            f"No clips found in {src_dir}. Add vertical ankle/lower-leg clips named "
            f"like {CLIP_ORDER[0]} ... or run with --source pexels."
        )
    logger.info(f"staged {len(materials)} local clips into {dst_dir}")
    return materials


def build_params(source: str) -> VideoParams:
    transcript = read_transcript()
    params = VideoParams(
        video_subject="Stronger Ankles in 80 Seconds",
        video_script=transcript,            # bypasses the LLM (task.py:18)
        video_aspect="9:16",                # -> 1080x1920
        video_concat_mode="sequential",     # play materials in array order
        video_clip_duration=10,             # ~one clip per exercise window
        video_count=1,                      # keep sequential (task.py:204)
        voice_name="en-US-AndrewNeural-Male",   # fixed voice = the "character"
        voice_rate=1.0,                     # tune 0.95-1.05 to land near 82s
        bgm_type="random",
        bgm_volume=0.12,                    # quieter than default so narration is clear
        subtitle_enabled=True,
        subtitle_position="bottom",
        custom_position=70.0,
        font_name="MicrosoftYaHeiBold.ttc",
        text_fore_color="#FFFFFF",
        text_background_color=True,
        stroke_color="#000000",
        stroke_width=1.5,
        font_size=60,
        n_threads=os.cpu_count() or 4,
    )
    if source == "pexels":
        params.video_source = "pexels"
        params.video_terms = PEXELS_TERMS
    else:
        params.video_source = "local"
        params.video_materials = stage_local_materials()
    return params


# --- export cuts ------------------------------------------------------------------

_SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def caption_end_times(srt_path: str) -> list:
    """Return sorted list of caption END times (seconds) from an SRT file."""
    ends = []
    if not srt_path or not os.path.isfile(srt_path):
        return ends
    for line in open(srt_path, encoding="utf-8"):
        m = _SRT_TIME.search(line)
        if m:
            h, mn, s, ms = map(int, m.group(5, 6, 7, 8))
            ends.append(h * 3600 + mn * 60 + s + ms / 1000.0)
    return sorted(ends)


def snap_to_caption(target: float, ends: list) -> float:
    """Largest caption end <= target; if none, the nearest caption end; else target."""
    if not ends:
        return target
    below = [e for e in ends if e <= target + 0.25]
    if below:
        return below[-1]
    return min(ends, key=lambda e: abs(e - target))


def trim_cut(ffmpeg: str, master: str, out_path: str, end_sec: float) -> None:
    """Stream-copy trim master[0:end_sec] -> out_path (burned-in captions survive)."""
    cmd = [ffmpeg, "-y", "-i", master, "-ss", "0", "-to", f"{end_sec:.3f}",
           "-c", "copy", "-avoid_negative_ts", "make_zero", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed for {out_path}:\n{proc.stderr}")


def make_cuts(master: str) -> list:
    ffmpeg = get_ffmpeg_binary()
    srt = os.path.join(utils.task_dir(TASK_ID), "subtitle.srt")
    ends = caption_end_times(srt)
    if not ends:
        logger.warning("no captions found; cuts will use raw target times")

    cuts_dir = os.path.join(utils.task_dir(TASK_ID), "cuts")
    os.makedirs(cuts_dir, exist_ok=True)

    # Always include the full master alongside the cuts for convenience.
    master_copy = os.path.join(cuts_dir, "master-82s.mp4")
    shutil.copy2(master, master_copy)
    outputs = [master_copy]

    for label, target in CUT_SPECS:
        end = snap_to_caption(target, ends)
        out = os.path.join(cuts_dir, f"{label}.mp4")
        trim_cut(ffmpeg, master, out, end)
        logger.success(f"{label}: 0 -> {end:.1f}s  ->  {out}")
        outputs.append(out)
    return outputs


def main():
    ap = argparse.ArgumentParser(description="Build the ankle-strength short.")
    ap.add_argument("--source", choices=["local", "pexels"], default="local",
                    help="visual source (default: local clips in assets/clips/)")
    ap.add_argument("--no-cuts", action="store_true", help="render master only")
    args = ap.parse_args()

    params = build_params(args.source)
    logger.info(f"rendering master ({args.source} source) ...")
    result = task.start(task_id=TASK_ID, params=params, stop_at="video")
    if not result or not result.get("videos"):
        raise SystemExit("render failed — check the logs above.")

    master = result["videos"][0]
    logger.success(f"master video: {master}")
    logger.info(f"audio duration: {result.get('audio_duration')}s "
                f"(target ~82s; tune voice_rate / transcript if off)")

    if not args.no_cuts:
        for path in make_cuts(master):
            logger.success(f"output: {path}")

    logger.info("done. Verify with: python projects/ankle-strength/verify.py")


if __name__ == "__main__":
    main()
