#!/usr/bin/env bash
# Offline demo of gcp-aidp. No Google Cloud or OCI credentials needed.
# Run from the plugin directory: ./demo.sh
set -euo pipefail
cd "$(dirname "$0")"

OUT="${OUT:-/tmp/gcp-aidp-demo}"
rm -rf "$OUT" && mkdir -p "$OUT"
export OCI_NAMESPACE="${OCI_NAMESPACE:-acme-demo-ns}"

bar() { printf '\n%s\n' "════════════════════════════════════════════════════════════"; }

bar; echo "  1/2  INVENTORY — scan Google Cloud (fixture: Northwind Retail)"; bar
python3 -m gcp_aidp.cli inventory --fixture demo -o "$OUT/inventory.json"

bar; echo "  2/2  PLAN — manifest → mapping plan + approval document"; bar
python3 -m gcp_aidp.cli plan "$OUT/inventory.json" -o "$OUT/plan.json"

bar; echo "  Artifacts at $OUT/"; bar
echo "  → $OUT/plan.json   (machine-readable plan)"
echo "  → $OUT/plan.md     (approval document)"
echo
echo "  migrate, verify and publish arrive in later milestones."
