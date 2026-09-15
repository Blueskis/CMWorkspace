"""Thin subprocess wrappers around the existing cm-comms-generator / cm-proposal-generator
scripts. Nothing here re-implements a stage — it only shells out to the scripts that already
carry the QA gate, the registry lookups and the producer footguns, and turns their exit codes
into Python exceptions the MCP tools can report cleanly.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "skills" / "cm-comms-generator" / "scripts"
PROPOSAL_SCRIPTS = REPO_ROOT / "skills" / "cm-proposal-generator" / "scripts"
KNOWLEDGE_BANK = REPO_ROOT / "proposal-assets" / "knowledge-bank"


class StageError(RuntimeError):
    def __init__(self, script: str, returncode: int, stdout: str, stderr: str):
        self.script = script
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"{script} exited {returncode}: {stderr.strip() or stdout.strip()}")


def _run(args: list[str], allow_exit: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if args[0] == "node" and "NODE_PATH" not in env:
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True)
        if npm_root.returncode == 0:
            env["NODE_PATH"] = npm_root.stdout.strip()
    proc = subprocess.run(args, capture_output=True, text=True, env=env)
    if proc.returncode not in allow_exit:
        raise StageError(args[1] if len(args) > 1 else args[0], proc.returncode, proc.stdout, proc.stderr)
    return proc


def index_kb(out_path: Path) -> Path:
    if not out_path.exists():
        _run(["python3", str(PROPOSAL_SCRIPTS / "index_kb.py"), str(KNOWLEDGE_BANK), "-o", str(out_path)])
    return out_path


def retrieve(kb_index: Path, section: str, tags: list[str], top: int = 5) -> list[dict]:
    proc = _run([
        "python3", str(PROPOSAL_SCRIPTS / "retrieve.py"), str(kb_index),
        "--section", section, "--tags", ",".join(tags), "--top", str(top),
        "--strict-section", "--json",
    ])
    return json.loads(proc.stdout or "[]")


def render_markdown(plan_path: Path, brand_path: Path, out_path: Path) -> Path:
    _run(["python3", str(SCRIPTS / "render_markdown.py"), str(plan_path), "--brand", str(brand_path), "-o", str(out_path)])
    return out_path


def qa_comms(brief_path: Path, plan_path: Path, brand_path: Path, out_path: Path) -> dict:
    """QA is expected to fail on real drafts — that is the gate working, not a service error."""
    proc = _run(
        ["python3", str(SCRIPTS / "qa_comms.py"), str(brief_path), str(plan_path), "--brand", str(brand_path), "-o", str(out_path)],
        allow_exit=(0, 1),
    )
    return {"passed": proc.returncode == 0, "report_path": str(out_path), "report": out_path.read_text() if out_path.exists() else proc.stdout}


def route_channel(plan_path: Path, brief_path: Path, brand_path: Path, out_path: Path) -> dict:
    proc = _run(
        ["python3", str(SCRIPTS / "route_channel.py"), str(plan_path), "--brief", str(brief_path), "--brand", str(brand_path), "-o", str(out_path)],
        allow_exit=(0, 1),
    )
    return {"ok": proc.returncode == 0, "route_path": str(out_path), "route": out_path.read_text() if out_path.exists() else proc.stdout, "stderr": proc.stderr}


def list_channels() -> str:
    proc = _run(["python3", str(SCRIPTS / "route_channel.py"), "--list"])
    return proc.stdout


def apply_brand(brand_path: Path, out_path: Path, fmt: str = "pptx") -> Path:
    _run(["python3", str(SCRIPTS / "apply_brand.py"), str(brand_path), "--format", fmt, "-o", str(out_path)])
    return out_path


def build_docx(plan_path: Path, brand_path: Path, out_dir: Path) -> Path:
    _run(["python3", str(SCRIPTS / "build_docx.py"), str(plan_path), "--brand", str(brand_path), "-o", str(out_dir)])
    _run(["node", str(out_dir / "build.js")])
    return out_dir / "draft.docx"


def build_pptx(plan_path: Path, theme_path: Path, out_dir: Path) -> Path:
    _run(["python3", str(SCRIPTS / "build_pptx.py"), str(plan_path), "--theme", str(theme_path), "-o", str(out_dir)])
    _run(["node", str(out_dir / "build_deck.js")])
    return out_dir / "deck.pptx"


def canva_brief(plan_path: Path, brand_path: Path, out_path: Path) -> Path:
    _run(["python3", str(SCRIPTS / "canva_brief.py"), str(plan_path), "--brand", str(brand_path), "-o", str(out_path)])
    return out_path


def video_spec(plan_path: Path, brand_path: Path, out_path: Path) -> Path:
    _run(["python3", str(SCRIPTS / "video_spec.py"), str(plan_path), "--brand", str(brand_path), "-o", str(out_path)])
    return out_path
