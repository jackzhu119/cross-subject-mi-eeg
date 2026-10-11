"""Compatibility entry point: editorial revision export only."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("build_revision.py")), run_name="__main__")
