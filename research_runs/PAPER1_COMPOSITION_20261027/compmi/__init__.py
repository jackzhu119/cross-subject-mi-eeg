"""Composition-by-objective follow-up; independently versioned scientific tasks."""
from pathlib import Path
import sys
_SHARED = str(Path(__file__).resolve().parents[1] / "shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)
