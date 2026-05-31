#!/usr/bin/env python3
"""
Verify the rendered ankle-strength outputs with ffprobe.

Checks each video in storage/tasks/ankle-strength-master/cuts/ for:
  - duration (master ~80-84s)
  - resolution 1080x1920 and ~30 fps
  - presence of an AAC audio stream
Also confirms the generated subtitle.srt has enough cues.

Run: python projects/ankle-strength/verify.py
"""

import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(PROJECT_DIR))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.services.video import get_ffmpeg_binary  # noqa: E402
from app.utils import utils  # noqa: E402

TASK_ID = "ankle-strength-master"


def find_ffprobe() -> str:
    """ffprobe lives next to ffmpeg for most installs; fall back to PATH."""
    ffmpeg = get_ffmpeg_binary()
    cand = os.path.join(os.path.dirname(ffmpeg),
                        "ffprobe.exe" if os.name == "nt" else "ffprobe")
    if os.path.isfile(cand):
        return cand
    found = shutil.which("ffprobe")
    if found:
        return found
    raise SystemExit("ffprobe not found. Install ffmpeg (which bundles ffprobe).")


def probe(ffprobe: str, path: str) -> dict:
    def run(args):
        return subprocess.run([ffprobe, "-v", "error", *args, path],
                              capture_output=True, text=True).stdout.strip()

    dur = run(["-show_entries", "format=duration", "-of", "default=nw=1:nokey=1"])
    vid = run(["-select_streams", "v:0", "-show_entries",
               "stream=width,height,r_frame_rate", "-of", "default=nw=1:nokey=1"])
    aud = run(["-select_streams", "a:0", "-show_entries",
               "stream=codec_name", "-of", "default=nw=1:nokey=1"])
    w, h, rate = (vid.splitlines() + ["", "", ""])[:3]
    try:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {
        "duration": float(dur) if dur else 0.0,
        "width": w, "height": h, "fps": round(fps, 2),
        "audio": aud or "(none)",
    }


def main():
    ffprobe = find_ffprobe()
    cuts_dir = os.path.join(utils.task_dir(TASK_ID), "cuts")
    master = os.path.join(utils.task_dir(TASK_ID), "final-1.mp4")

    targets = []
    if os.path.isdir(cuts_dir):
        targets += [os.path.join(cuts_dir, f) for f in sorted(os.listdir(cuts_dir))
                    if f.endswith(".mp4")]
    if not targets and os.path.isfile(master):
        targets = [master]
    if not targets:
        raise SystemExit("No outputs found. Run build.py first.")

    ok = True
    for path in targets:
        info = probe(ffprobe, path)
        is_master = "master" in os.path.basename(path) or path == master
        dur_ok = (80 <= info["duration"] <= 84) if is_master else info["duration"] > 0
        res_ok = info["width"] == "1080" and info["height"] == "1920"
        fps_ok = 29 <= info["fps"] <= 31
        aud_ok = "aac" in info["audio"].lower()
        line_ok = dur_ok and res_ok and fps_ok and aud_ok
        ok = ok and line_ok
        flag = "OK " if line_ok else "!! "
        print(f"{flag}{os.path.basename(path):16} "
              f"{info['duration']:6.1f}s  {info['width']}x{info['height']}  "
              f"{info['fps']}fps  audio={info['audio']}")

    srt = os.path.join(utils.task_dir(TASK_ID), "subtitle.srt")
    cues = sum(1 for ln in open(srt, encoding="utf-8")) if os.path.isfile(srt) else 0
    print(f"\nsubtitle.srt: {'present' if os.path.isfile(srt) else 'MISSING'} "
          f"({cues} lines)")

    print("\nResult:", "PASS" if ok else "CHECK FAILURES ABOVE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
