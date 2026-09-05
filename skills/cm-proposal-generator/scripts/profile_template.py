#!/usr/bin/env python3
"""Shim — profile_template.py moved to lib/ so training-material-generator can share it.

Kept here so the commands documented in SKILL.md and README.md keep working unchanged.
See lib/profile_template.py for the actual implementation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from profile_template import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
