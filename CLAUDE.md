# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MoneyPrinterTurbo automatically generates short videos from a topic/keyword. Given a
subject, it produces an AI-written script, search terms, voice-over (TTS), subtitles, and
assembles downloaded stock footage with background music into a final video (9:16, 16:9, or
1:1). It ships with both a **Streamlit web UI** and a **FastAPI REST API** that share the
same service layer.

## Common commands

Dependencies are defined in `pyproject.toml` with `uv.lock`; `requirements.txt` exists for
pip compatibility. Target Python is **3.11**. External binaries **FFmpeg** (auto-downloaded
via `imageio-ffmpeg`) and **ImageMagick** are required for rendering.

```bash
# Setup (preferred)
uv sync --frozen

# Run the FastAPI server -> http://0.0.0.0:8080  (docs at /docs)
uv run python main.py

# Run the Streamlit web UI -> http://127.0.0.1:8501
sh webui.sh            # macOS/Linux (auto-picks a free port 8501-8599)
.\webui.bat            # Windows
# equivalent: uv run streamlit run ./webui/Main.py --browser.gatherUsageStats=False

# Docker (brings up both WebUI :8501 and API :8080)
docker compose up
```

### Tests (Python `unittest`, located in `test/services/`)

```bash
python -m unittest discover -s test                                    # all tests
python -m unittest test.services.test_llm                              # one module
python -m unittest test.services.test_llm.TestScriptPromptOptions      # one class
python -m unittest test.services.test_llm.TestScriptPromptOptions.test_build_script_prompt_appends_advanced_requirements  # one test
```

## Configuration

Runtime config lives in `config.toml`, auto-created from `config.example.toml` on first run
and loaded by `app/config/config.py`. There is **no hot reload** — restart after editing.
Key `[app]` settings:

- `llm_provider` — selects the LLM backend; the matching provider keys (e.g.
  `openai_api_key`, `azure_*`, `gemini_*`, `ollama_*`, `litellm_model_name`, …) must be set.
  ~15 providers are supported, including a `litellm` route to 100+ others.
- `video_source` (`pexels`/`pixabay`) plus `pexels_api_keys` / `pixabay_api_keys` for stock footage.
- `subtitle_provider` — `edge` (edge-tts) or `whisper` (local faster-whisper), or empty to disable.
- Task queue/state backend: `enable_redis` + `redis_*`; otherwise in-memory.
- `imagemagick_path` / `ffmpeg_path` for manual binary locations (mainly Windows).

Other sections: `[whisper]`, `[azure]`, `[siliconflow]`, `[proxy]`, `[ui]`. Some env vars
override config (e.g. `MPT_APP_REDIS_HOST`, `CORS_ALLOWED_ORIGINS`).

## Architecture

The codebase under `app/` follows a controllers → services → models layering. Both the API
and the web UI call into the **same service functions** — the API controllers are thin
wrappers, and `webui/Main.py` imports the services directly.

```
main.py                  -> launches uvicorn on app.asgi:app
app/asgi.py              -> FastAPI app: CORS, exception handlers, static mounts
app/router.py            -> mounts the v1 routers
app/controllers/v1/      -> HTTP endpoints, prefix /api/v1 (set in v1/base.py)
  video.py               -> POST /videos, /subtitle, /audio; GET/DELETE /tasks; /stream, /download, bgm, materials
  llm.py                 -> POST /scripts, POST /terms
app/controllers/manager/ -> task queue: memory_manager.py (default) or redis_manager.py
app/services/            -> business logic (the heart of the app)
app/models/              -> schema.py (Pydantic: VideoParams, VideoAspect, …), const.py (task states), exception.py
app/utils/               -> utils.py (get_response wrapper, paths) and file_security.py (path-traversal guards)
webui/Main.py            -> Streamlit UI; calls app.services.task.start() directly
```

### Video generation pipeline

The orchestrator is **`app/services/task.py::start(task_id, params, stop_at="video")`**.
The web UI calls it directly; the API runs it as a background task. `stop_at` allows
stopping early (e.g. produce only audio or subtitle). It chains these stages, each a
function in `task.py` delegating to a dedicated service module:

1. `generate_script` / `generate_terms` → `services/llm.py` (script + stock-footage search terms)
2. `generate_audio` → `services/voice.py` (TTS voice-over)
3. `generate_subtitle` → `services/subtitle.py` (SRT via edge-tts or faster-whisper)
4. `get_video_materials` → `services/material.py` (search + download Pexels/Pixabay clips)
5. `generate_final_videos` → `services/video.py` (MoviePy: resize, transitions, subtitle overlay, mix voice + BGM, encode)

Progress and results are tracked through `services/state.py` (`MemoryState` or `RedisState`),
which clients poll via `GET /api/v1/tasks/{task_id}`.

## Conventions

- **LLM provider abstraction**: `services/llm.py` branches on `config.app["llm_provider"]`
  inside a unified generation helper. Add a new provider by extending that dispatch plus the
  corresponding `config.toml` keys — callers (`generate_script`, `generate_terms`) stay unchanged.
- **API responses**: wrap payloads with `app/utils/utils.py::get_response(status, data, message)`;
  raise `HttpException` / `FileNotFoundException` from `app/models/exception.py` for errors.
- **Service functions** use `generate_*` / `search_*` public names with `_`-prefixed helpers,
  update task state via `state.py`, and clean up temp files (`delete_files`, `gc.collect()`).
- **File access** from user-supplied paths (`/stream/{path}`, `/download/{path}`, uploads)
  must go through `app/utils/file_security.py` to prevent path traversal.
- Logging uses **loguru** throughout.
