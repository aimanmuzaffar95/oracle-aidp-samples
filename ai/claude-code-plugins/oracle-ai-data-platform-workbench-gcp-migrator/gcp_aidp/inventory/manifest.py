"""The inventory manifest: one JSON object per scan, one entry per source."""
from __future__ import annotations

import json
from pathlib import Path

from gcp_aidp._atomic import write_text_atomic

# Every source the migrator knows about, migrated or not. A source that is
# only inventoried still appears here so the plan never understates the estate.
ALL_SOURCES = ("bigquery", "gcs", "dataproc", "composer", "dataform", "dataflow", "vertex")


def write_manifest(manifest: dict, out_path: str | Path) -> Path:
    return write_text_atomic(out_path, json.dumps(manifest, indent=2, default=str))


def summarize(manifest: dict) -> str:
    """One-screen summary string for the user."""
    lines = [
        f"GCP project: {manifest.get('project_id')}",
        f"scanned at:  {manifest.get('scanned_at')}",
        "",
    ]
    for src, data in manifest.get("sources", {}).items():
        s = data.get("summary", {})
        if "error" in s:
            lines.append(f"  {src:10s}  ERROR: {s['error']}")
            continue
        lines.append(f"  {src:10s}  " + ", ".join(f"{k}={v}" for k, v in s.items()))
    return "\n".join(lines)
