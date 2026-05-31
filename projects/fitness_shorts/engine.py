"""
Config-driven engine for vertical fitness shorts, built ON MoneyPrinterTurbo.

A "project" is just a folder containing:
    config.yaml      - settings (task_id, voice, clip order, cuts, ...)
    transcript.md    - the narration, read verbatim (LLM is skipped)
    assets/clips/    - optional local footage (else use --source pexels)

This module reuses the core pipeline (app.services.task.start, the ffmpeg helper,
edge-tts, captioning) and never reimplements TTS/FFmpeg. Heavy third-party imports
(loguru, app.*, yaml) are deferred into the functions that need them so the pure
helpers (transcript/SRT parsing, cut snapping) stay importable and unit-testable.

CLI: see run.py. Per-project wrappers (build.py / verify.py) just call load_config()
then run()/verify().
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(THIS_DIR))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# --- project config ---------------------------------------------------------------

@dataclass
class ProjectConfig:
    project_dir: str
    task_id: str
    subject: str
    clip_order: List[str] = field(default_factory=list)
    pexels_terms: List[str] = field(default_factory=list)
    voice_name: str = "en-US-AndrewNeural-Male"
    voice_rate: float = 1.0
    bgm_type: str = "random"
    bgm_volume: float = 0.12
    video_clip_duration: int = 10
    stage_subdir: str = ""           # subfolder under storage/local_videos
    target_seconds: float = 82.0
    duration_tolerance: float = 3.0  # master duration window = target +/- this
    cuts: List[Tuple[str, float]] = field(default_factory=list)
    # subtitle styling
    subtitle_position: str = "bottom"
    custom_position: float = 70.0
    font_name: str = "MicrosoftYaHeiBold.ttc"
    font_size: int = 60
    text_fore_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: float = 1.5
    transcript_file: str = "transcript.md"


def load_config(project_dir: str) -> ProjectConfig:
    import yaml

    project_dir = os.path.abspath(project_dir)
    cfg_path = os.path.join(project_dir, "config.yaml")
    if not os.path.isfile(cfg_path):
        raise SystemExit(f"no config.yaml found in {project_dir}")
    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "task_id" not in data:
        raise SystemExit(f"config.yaml must define task_id ({cfg_path})")

    cuts = [(c["label"], float(c["seconds"])) for c in (data.get("cuts") or [])]
    sub = data.get("subtitle") or {}
    return ProjectConfig(
        project_dir=project_dir,
        task_id=data["task_id"],
        subject=data.get("subject", data["task_id"]),
        clip_order=list(data.get("clip_order") or []),
        pexels_terms=list(data.get("pexels_terms") or []),
        voice_name=data.get("voice_name", "en-US-AndrewNeural-Male"),
        voice_rate=float(data.get("voice_rate", 1.0)),
        bgm_type=data.get("bgm_type", "random"),
        bgm_volume=float(data.get("bgm_volume", 0.12)),
        video_clip_duration=int(data.get("video_clip_duration", 10)),
        stage_subdir=data.get("stage_subdir", data["task_id"]),
        target_seconds=float(data.get("target_seconds", 82.0)),
        duration_tolerance=float(data.get("duration_tolerance", 3.0)),
        cuts=cuts,
        subtitle_position=sub.get("position", "bottom"),
        custom_position=float(sub.get("custom_position", 70.0)),
        font_name=sub.get("font_name", "MicrosoftYaHeiBold.ttc"),
        font_size=int(sub.get("font_size", 60)),
        text_fore_color=sub.get("text_fore_color", "#FFFFFF"),
        stroke_color=sub.get("stroke_color", "#000000"),
        stroke_width=float(sub.get("stroke_width", 1.5)),
        transcript_file=data.get("transcript_file", "transcript.md"),
    )


# --- pure helpers (no heavy deps; unit-testable) ----------------------------------

def read_transcript(cfg: ProjectConfig) -> str:
    """Read the transcript, dropping note lines (# ... or <!-- ... -->)."""
    path = os.path.join(cfg.project_dir, cfg.transcript_file)
    if not os.path.isfile(path):
        raise SystemExit(f"transcript not found: {path}")
    out, in_comment = [], False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            s = line.strip()
            if in_comment:
                if "-->" in s:
                    in_comment = False
                continue
            if s.startswith("<!--"):
                if "-->" not in s:
                    in_comment = True
                continue
            if s.startswith("#"):
                continue
            out.append(line)
    text = "\n".join(out).strip()
    if not text:
        raise SystemExit(f"transcript is empty after stripping notes: {path}")
    return text


_SRT_TIME = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


def caption_end_times(srt_path: str) -> list:
    """Sorted caption END times (seconds) from an SRT file."""
    ends = []
    if not srt_path or not os.path.isfile(srt_path):
        return ends
    with open(srt_path, encoding="utf-8") as f:
        for line in f:
            m = _SRT_TIME.search(line)
            if m:
                h, mn, s, ms = map(int, m.group(5, 6, 7, 8))
                ends.append(h * 3600 + mn * 60 + s + ms / 1000.0)
    return sorted(ends)


def snap_to_caption(target: float, ends: list) -> float:
    """Largest caption end <= target; else nearest caption end; else target."""
    if not ends:
        return target
    below = [e for e in ends if e <= target + 0.25]
    return below[-1] if below else min(ends, key=lambda e: abs(e - target))


# --- pipeline (defers heavy imports) ----------------------------------------------

def stage_local_materials(cfg: ProjectConfig) -> list:
    from loguru import logger
    from app.models.schema import MaterialInfo
    from app.utils import utils

    src_dir = os.path.join(cfg.project_dir, "assets", "clips")
    dst_dir = os.path.join(utils.storage_dir("local_videos", create=True),
                           cfg.stage_subdir)
    os.makedirs(dst_dir, exist_ok=True)

    materials = []
    for name in cfg.clip_order:
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            logger.warning(f"missing clip (skipping): {src}")
            continue
        shutil.copy2(src, os.path.join(dst_dir, name))
        materials.append(MaterialInfo(
            provider="local", url=os.path.join(cfg.stage_subdir, name)))

    if not materials:
        raise SystemExit(
            f"No clips found in {src_dir}. Add footage named like "
            f"{cfg.clip_order[:1]} ... or run with --source pexels.")
    logger.info(f"staged {len(materials)} local clips into {dst_dir}")
    return materials


def build_params(cfg: ProjectConfig, source: str):
    from app.models.schema import VideoParams

    params = VideoParams(
        video_subject=cfg.subject,
        video_script=read_transcript(cfg),     # bypasses the LLM (task.py:18)
        video_aspect="9:16",                    # -> 1080x1920
        video_concat_mode="sequential",         # play materials in array order
        video_clip_duration=cfg.video_clip_duration,
        video_count=1,                          # keep sequential (task.py:204)
        voice_name=cfg.voice_name,              # fixed voice = the "character"
        voice_rate=cfg.voice_rate,
        bgm_type=cfg.bgm_type,
        bgm_volume=cfg.bgm_volume,
        subtitle_enabled=True,
        subtitle_position=cfg.subtitle_position,
        custom_position=cfg.custom_position,
        font_name=cfg.font_name,
        text_fore_color=cfg.text_fore_color,
        text_background_color=True,
        stroke_color=cfg.stroke_color,
        stroke_width=cfg.stroke_width,
        font_size=cfg.font_size,
        n_threads=os.cpu_count() or 4,
    )
    if source == "pexels":
        params.video_source = "pexels"
        params.video_terms = cfg.pexels_terms
    else:
        params.video_source = "local"
        params.video_materials = stage_local_materials(cfg)
    return params


def _trim_cut(ffmpeg: str, master: str, out_path: str, end_sec: float) -> None:
    """Stream-copy trim master[0:end_sec] -> out_path (burned-in captions survive)."""
    cmd = [ffmpeg, "-y", "-i", master, "-ss", "0", "-to", f"{end_sec:.3f}",
           "-c", "copy", "-avoid_negative_ts", "make_zero", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg trim failed for {out_path}:\n{proc.stderr}")


def make_cuts(cfg: ProjectConfig, master: str) -> list:
    from loguru import logger
    from app.services.video import get_ffmpeg_binary
    from app.utils import utils

    ffmpeg = get_ffmpeg_binary()
    srt = os.path.join(utils.task_dir(cfg.task_id), "subtitle.srt")
    ends = caption_end_times(srt)
    if not ends:
        logger.warning("no captions found; cuts will use raw target times")

    cuts_dir = os.path.join(utils.task_dir(cfg.task_id), "cuts")
    os.makedirs(cuts_dir, exist_ok=True)

    master_copy = os.path.join(cuts_dir, "master.mp4")
    shutil.copy2(master, master_copy)
    outputs = [master_copy]

    for label, target in cfg.cuts:
        end = snap_to_caption(target, ends)
        out = os.path.join(cuts_dir, f"{label}.mp4")
        _trim_cut(ffmpeg, master, out, end)
        logger.success(f"{label}: 0 -> {end:.1f}s  ->  {out}")
        outputs.append(out)
    return outputs


def run(cfg: ProjectConfig, source: str = "local", make_cuts_flag: bool = True):
    from loguru import logger
    from app.services import task

    params = build_params(cfg, source)
    logger.info(f"rendering '{cfg.task_id}' ({source} source) ...")
    result = task.start(task_id=cfg.task_id, params=params, stop_at="video")
    if not result or not result.get("videos"):
        raise SystemExit("render failed - check the logs above.")

    master = result["videos"][0]
    logger.success(f"master video: {master}")
    logger.info(f"audio duration: {result.get('audio_duration')}s "
                f"(target ~{cfg.target_seconds:.0f}s; tune voice_rate/transcript)")

    if make_cuts_flag and cfg.cuts:
        for path in make_cuts(cfg, master):
            logger.success(f"output: {path}")
    return result


# --- verification (ffprobe) -------------------------------------------------------

def _find_ffprobe() -> str:
    from app.services.video import get_ffmpeg_binary

    ffmpeg = get_ffmpeg_binary()
    cand = os.path.join(os.path.dirname(ffmpeg),
                        "ffprobe.exe" if os.name == "nt" else "ffprobe")
    if os.path.isfile(cand):
        return cand
    found = shutil.which("ffprobe")
    if found:
        return found
    raise SystemExit("ffprobe not found. Install ffmpeg (which bundles ffprobe).")


def _probe(ffprobe: str, path: str) -> dict:
    def run_(args):
        return subprocess.run([ffprobe, "-v", "error", *args, path],
                              capture_output=True, text=True).stdout.strip()

    dur = run_(["-show_entries", "format=duration", "-of", "default=nw=1:nokey=1"])
    vid = run_(["-select_streams", "v:0", "-show_entries",
                "stream=width,height,r_frame_rate", "-of", "default=nw=1:nokey=1"])
    aud = run_(["-select_streams", "a:0", "-show_entries",
                "stream=codec_name", "-of", "default=nw=1:nokey=1"])
    w, h, rate = (vid.splitlines() + ["", "", ""])[:3]
    try:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {"duration": float(dur) if dur else 0.0, "width": w, "height": h,
            "fps": round(fps, 2), "audio": aud or "(none)"}


def verify(cfg: ProjectConfig) -> bool:
    from app.utils import utils

    ffprobe = _find_ffprobe()
    cuts_dir = os.path.join(utils.task_dir(cfg.task_id), "cuts")
    master = os.path.join(utils.task_dir(cfg.task_id), "final-1.mp4")

    targets = []
    if os.path.isdir(cuts_dir):
        targets += [os.path.join(cuts_dir, f) for f in sorted(os.listdir(cuts_dir))
                    if f.endswith(".mp4")]
    if not targets and os.path.isfile(master):
        targets = [master]
    if not targets:
        raise SystemExit("No outputs found. Run the build first.")

    lo = cfg.target_seconds - cfg.duration_tolerance
    hi = cfg.target_seconds + cfg.duration_tolerance
    ok = True
    for path in targets:
        info = _probe(ffprobe, path)
        is_master = "master" in os.path.basename(path) or path == master
        dur_ok = (lo <= info["duration"] <= hi) if is_master else info["duration"] > 0
        res_ok = info["width"] == "1080" and info["height"] == "1920"
        fps_ok = 29 <= info["fps"] <= 31
        aud_ok = "aac" in info["audio"].lower()
        line_ok = dur_ok and res_ok and fps_ok and aud_ok
        ok = ok and line_ok
        flag = "OK " if line_ok else "!! "
        print(f"{flag}{os.path.basename(path):16} {info['duration']:6.1f}s  "
              f"{info['width']}x{info['height']}  {info['fps']}fps  "
              f"audio={info['audio']}")

    srt = os.path.join(utils.task_dir(cfg.task_id), "subtitle.srt")
    present = os.path.isfile(srt)
    print(f"\nsubtitle.srt: {'present' if present else 'MISSING'}")
    print("Result:", "PASS" if ok else "CHECK FAILURES ABOVE")
    return ok
