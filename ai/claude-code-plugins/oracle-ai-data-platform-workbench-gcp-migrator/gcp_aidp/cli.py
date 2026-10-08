"""`gcp-aidp <verb>` — inventory, plan, migrate and verify today; publish follows."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from importlib.resources import files
from pathlib import Path

from gcp_aidp import __version__
from gcp_aidp._env import load_dotenv
from gcp_aidp.inventory.manifest import ALL_SOURCES

_FIXTURE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def _load_json_object(path, label: str) -> dict:
    """Load a command input and fail closed when its JSON root is not an object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return value


def _fixture_path(name: str):
    """Resolve a bundled fixture name without allowing filesystem traversal."""
    if not _FIXTURE_NAME_RE.fullmatch(name):
        raise ValueError("invalid fixture name; use 1-64 letters, digits, underscores, or hyphens")
    resource = files("gcp_aidp.fixtures").joinpath(f"{name}-manifest.json")
    if not resource.is_file():
        raise ValueError(f"bundled fixture not found: {name}")
    return resource


def _parse_sources(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ALL_SOURCES
    sources = tuple(dict.fromkeys(p.strip().lower() for p in raw.split(",") if p.strip()))
    bad = [s for s in sources if s not in ALL_SOURCES]
    if not sources or bad:
        detail = f"unknown source(s): {bad}" if bad else "source list is empty"
        raise ValueError(f"{detail}; valid: {ALL_SOURCES}")
    return sources


def cmd_inventory(args: argparse.Namespace) -> int:
    from gcp_aidp.inventory.manifest import summarize, write_manifest

    sources = _parse_sources(args.sources)
    if args.fixture is None:
        # Live scans (metadata-only BigQuery and Cloud Storage calls) arrive in M3.
        print("error: live inventory is not implemented yet; use --fixture demo", file=sys.stderr)
        return 2
    path = _fixture_path(args.fixture)
    manifest = _load_json_object(path, "fixture manifest")
    fixture_sources = manifest.get("sources")
    if not isinstance(fixture_sources, dict):
        raise ValueError("fixture manifest field 'sources' must be a JSON object")
    missing = [s for s in sources if s not in fixture_sources]
    if missing:
        raise ValueError("fixture does not contain requested source(s): " + ", ".join(missing))
    manifest["sources"] = {s: fixture_sources[s] for s in sources}
    manifest["sources_scanned"] = list(sources)
    print(f"[fixture] using {path}")

    project = manifest.get("project_id") or "unknown"
    out = Path(args.output or f"inventory-{project}-{time.strftime('%Y%m%dT%H%M%S')}.json")
    write_manifest(manifest, out)
    print(f"\n# wrote {out}\n")
    print(summarize(manifest))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    from gcp_aidp.plan import build_plan, summarize_plan, write_plan, write_plan_markdown

    manifest = _load_json_object(Path(args.manifest), "manifest")
    ns = args.namespace or os.environ.get("OCI_NAMESPACE") or "<your-oci-namespace>"
    plan = build_plan(manifest, oci_namespace=ns, catalog=args.catalog,
                      bignumeric=args.bignumeric, geography=args.geography)
    out = Path(args.output) if args.output else Path(args.manifest).with_suffix(".plan.json")
    write_plan(plan, out)
    md = write_plan_markdown(plan, out.with_suffix(".md"))
    print(f"# wrote {out} and {md} (approval document)\n")
    print(summarize_plan(plan))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    from gcp_aidp.migrate import migrate

    plan = _load_json_object(Path(args.plan), "plan")
    out_dir = Path(args.out_dir)
    print(f"# plan={plan.get('plan_id')}  out={out_dir}  (offline: nothing is sent to AIDP)\n")
    report = migrate(plan, out_dir=out_dir, log=lambda line: print(line, flush=True))
    c = report["counts"]
    print(f"\n# done. ok={c['ok']}  needs_review={c['needs_manual_review']}  blocked={c['blocked']}  "
          f"reported={c['reported']}  skipped={c['skipped']}  error={c['error']}")
    print(f"# wrote {out_dir}/report.json and {out_dir}/report.md")
    return 0 if c["error"] == 0 else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from gcp_aidp.verify import format_verify, verify

    path = Path(args.report_or_dir)
    if path.is_dir():
        path = path / "report.json"
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 2
    result = verify(path)
    print(format_verify(result))
    return 0 if result["summary"]["FAIL"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gcp-aidp", description="Google Cloud data stack → Oracle AIDP migrator")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    inv = sub.add_parser("inventory", help="scan Google Cloud (read-only, metadata only) and emit a manifest")
    inv.add_argument("--project", help="GCP project id (default: $GCP_PROJECT)")
    inv.add_argument("--sources", help=f"comma-separated subset of {','.join(ALL_SOURCES)} (default: all)")
    inv.add_argument("--fixture", help="load a bundled fixture manifest instead of scanning (e.g. 'demo')")
    inv.add_argument("-o", "--output", help="manifest output path (default: ./inventory-<project>-<ts>.json)")
    inv.set_defaults(func=cmd_inventory)

    pl = sub.add_parser("plan", help="produce a migration plan and approval document from a manifest")
    pl.add_argument("manifest")
    pl.add_argument("-o", "--output", help="plan path (default: <manifest>.plan.json); the .md sits beside it")
    pl.add_argument("--namespace", help="OCI namespace for target buckets (default: $OCI_NAMESPACE)")
    pl.add_argument("--catalog", help="target INTERNAL catalog (default: the project id, made a valid name)")
    pl.add_argument("--bignumeric", choices=("block", "string"), default="block",
                    help="BIGNUMERIC columns: block the table (default) or carry exact decimal text")
    pl.add_argument("--geography", choices=("block", "wkt"), default="block",
                    help="GEOGRAPHY columns: block the table (default) or carry WKT text")
    pl.set_defaults(func=cmd_plan)

    mg = sub.add_parser("migrate", help="write translated artifacts and a report locally; contacts nothing")
    mg.add_argument("plan")
    mg.add_argument("-o", "--out-dir", default="./migrated", help="output directory (default: ./migrated)")
    mg.set_defaults(func=cmd_migrate)

    vf = sub.add_parser("verify", help="classify a migrate report into PASS / REVIEW / SKIP / FAIL")
    vf.add_argument("report_or_dir", help="report.json, or the directory migrate wrote")
    vf.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
