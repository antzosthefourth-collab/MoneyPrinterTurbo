#!/usr/bin/env python3
"""
Verify the rendered ankle-strength outputs with ffprobe (delegates to the engine).

    python projects/ankle-strength/verify.py
"""

import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "fitness_shorts"))
import engine  # noqa: E402

cfg = engine.load_config(HERE)
sys.exit(0 if engine.verify(cfg) else 1)
