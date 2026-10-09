#!/usr/bin/env python3
"""Run every stakeholder-mapping test: Python (unittest) then the viewer core (node --test)."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    rc = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_*.py", "-v"], cwd=HERE)
    rc |= subprocess.call(["node", "--test", str(HERE / "viewer.test.js")])
    return rc


if __name__ == "__main__":
    sys.exit(main())
