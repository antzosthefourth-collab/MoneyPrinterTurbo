#!/usr/bin/env python3
"""
Generic runner for config-driven fitness shorts.

Usage:
    python projects/fitness_shorts/run.py <project_dir> [--source local|pexels]
                                          [--no-cuts] [--verify]

Example:
    python projects/fitness_shorts/run.py projects/ankle-strength --verify
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import engine  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a config-driven fitness short.")
    ap.add_argument("project_dir", help="folder containing config.yaml + transcript")
    ap.add_argument("--source", choices=["local", "pexels"], default="local")
    ap.add_argument("--no-cuts", action="store_true", help="render master only")
    ap.add_argument("--verify", action="store_true", help="run ffprobe checks after")
    args = ap.parse_args()

    cfg = engine.load_config(args.project_dir)
    engine.run(cfg, source=args.source, make_cuts_flag=not args.no_cuts)
    if args.verify:
        ok = engine.verify(cfg)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
