#!/usr/bin/env python3
"""Compatibility entry point; use --help for --source/--out arguments."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('render_figures.py')),run_name="__main__")
