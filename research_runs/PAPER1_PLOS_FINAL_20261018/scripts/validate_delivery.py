#!/usr/bin/env python3
"""Compatibility entry point; use --help for --source/--out arguments."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('validate_package.py')),run_name="__main__")
