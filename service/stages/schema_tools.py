"""Load a schema from skills/cm-comms-generator/schemas/ as an Anthropic tool input_schema."""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "cm-comms-generator" / "schemas"


def load_tool_schema(filename: str) -> dict:
    raw = json.loads((SCHEMA_DIR / filename).read_text())
    raw.pop("$schema", None)
    raw.pop("$id", None)
    raw.pop("title", None)
    return raw
