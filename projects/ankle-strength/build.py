#!/usr/bin/env python3
"""
Build the "Stronger Ankles in 80 Seconds" short.

Thin wrapper around the generic engine (projects/fitness_shorts/engine.py) using this
folder's config.yaml + transcript.md. All settings live in config.yaml.

    python projects/ankle-strength/build.py                 # local clips (default)
    python projects/ankle-strength/build.py --source pexels # auto-download footage
    python projects/ankle-strength/build.py --no-cuts       # master only
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "fitness_shorts"))
import engine  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build the ankle-strength short.")
    ap.add_argument("--source", choices=["local", "pexels"], default="local")
    ap.add_argument("--no-cuts", action="store_true", help="render master only")
    args = ap.parse_args()

    cfg = engine.load_config(HERE)
    engine.run(cfg, source=args.source, make_cuts_flag=not args.no_cuts)
    print("\nVerify with: python projects/ankle-strength/verify.py")


if __name__ == "__main__":
    main()
