"""Where produced artifacts end up, and the URL a caller is handed back.

v0.3 needs somewhere durable to put a .docx, a .pptx, a canva_brief.json, a video_spec.json —
this repo has no object-storage account of its own, so this module defines the interface a
real deployment fills in rather than faking one. Set ARTIFACT_BASE_URL to a public base (an S3
bucket behind CloudFront, an Azure Blob container, whatever the deployment already has) and
files copied under WORKSPACE_ROOT/artifacts/ are assumed to be served from there. Absent that,
runs stay on local disk and the "URL" is the local path — fine for exercising the pipeline,
not for handing a link to someone else.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

WORKSPACE_ROOT = Path(os.environ.get("COMMS_WORKSPACE_ROOT", "/tmp/cm-comms-runs"))
ARTIFACT_BASE_URL = os.environ.get("ARTIFACT_BASE_URL", "").rstrip("/")


def workspace_for(run_id: str) -> Path:
    ws = WORKSPACE_ROOT / run_id
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def publish(local_path: Path) -> str:
    """Copy an artifact into the served tree and return the URL a client should follow.

    Without ARTIFACT_BASE_URL configured, returns a local path — the caller (server.py)
    reports it plainly as "not publicly reachable" rather than pretending it is a URL.
    """
    if not ARTIFACT_BASE_URL:
        return str(local_path)

    rel = local_path.relative_to(WORKSPACE_ROOT)
    dest = WORKSPACE_ROOT / "artifacts" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_path, dest)
    return f"{ARTIFACT_BASE_URL}/{rel.as_posix()}"
