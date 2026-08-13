#!/usr/bin/env python3
"""Check the toolchain before a run starts, so failures are legible instead of a stack trace.

    python preflight.py
    python preflight.py --quiet          # exit code only, for scripting

ffmpeg is this skill's one external dependency, and it is used read-only: probing a
recording, finding scene boundaries, and extracting keyframes. Nothing here renders or
encodes video — Synthesia does that — so the requirements are modest and any reasonably
current ffmpeg build satisfies them.

Exits non-zero if anything required is missing, with the install command for the platform.
"""

import argparse
import platform
import shutil
import subprocess
import sys

REQUIRED = {
    "ffmpeg": "Segment the recording and extract keyframes",
    "ffprobe": "Measure duration, resolution and frame rate",
}

INSTALL_HINTS = {
    "Darwin": "brew install ffmpeg",
    "Linux": "sudo apt-get install ffmpeg   (or: sudo dnf install ffmpeg)",
    "Windows": "winget install Gyan.FFmpeg   (or: choco install ffmpeg)",
}

# Filters ingest_capture.py relies on. All are in ffmpeg's default build, but a stripped
# distro package occasionally drops one, and finding that out mid-run is worse than here.
REQUIRED_FILTERS = ["select", "showinfo", "scale"]


def _version(binary):
    try:
        out = subprocess.run(
            [binary, "-version"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    first = (out.stdout or "").splitlines()
    return first[0].strip() if first else f"{binary} (version line not parsed)"


def _available_filters():
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    names = set()
    for line in (out.stdout or "").splitlines():
        parts = line.split()
        # Rows look like: " T.. scale   V->V  Scale the input video size."
        if len(parts) >= 2 and not line.startswith("Filters:"):
            names.add(parts[1])
    return names


def check():
    problems = []
    report = []

    for binary, why in REQUIRED.items():
        if shutil.which(binary) is None:
            problems.append(f"{binary} not found on PATH — needed to: {why}")
            report.append((binary, None))
            continue
        version = _version(binary)
        if version is None:
            problems.append(f"{binary} is on PATH but failed to run")
        report.append((binary, version))

    if not problems:
        filters = _available_filters()
        if filters is None:
            problems.append("could not list ffmpeg filters")
        else:
            missing = [f for f in REQUIRED_FILTERS if f not in filters]
            if missing:
                problems.append(
                    "ffmpeg build is missing required filters: " + ", ".join(missing)
                )

    return report, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--quiet", action="store_true", help="suppress output; use the exit code"
    )
    args = parser.parse_args()

    report, problems = check()

    if not args.quiet:
        for binary, version in report:
            print(f"  {'ok  ' if version else 'MISS'}  {binary:8} {version or ''}")
        print()

    if problems:
        if not args.quiet:
            print("Preflight failed:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            hint = INSTALL_HINTS.get(platform.system())
            if hint:
                print(f"\nInstall ffmpeg with:\n  {hint}", file=sys.stderr)
        return 1

    if not args.quiet:
        print("Preflight passed — ready to ingest a recording.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
