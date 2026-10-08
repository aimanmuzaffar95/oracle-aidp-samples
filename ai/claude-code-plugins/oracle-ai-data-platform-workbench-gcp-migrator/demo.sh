#!/usr/bin/env bash
# Offline demo of gcp-aidp. No Google Cloud or OCI credentials needed.
# Run from the plugin directory: ./demo.sh
set -euo pipefail
cd "$(dirname "$0")"

OUT="${OUT:-/tmp/gcp-aidp-demo}"
rm -rf "$OUT" && mkdir -p "$OUT"
export OCI_NAMESPACE="${OCI_NAMESPACE:-acme-demo-ns}"

bar() { printf '\n%s\n' "════════════════════════════════════════════════════════════"; }
show() {  # show <asset_id> <field>
  python3 -c "import json,sys; r=[x for x in json.load(open('$OUT/migrated/report.json'))['results'] if x['asset_id']==sys.argv[1]][0]; print(r[sys.argv[2]])" "$1" "$2"
}

bar; echo "  1/4  INVENTORY — scan Google Cloud (fixture: Northwind Retail)"; bar
python3 -m gcp_aidp.cli inventory --fixture demo -o "$OUT/inventory.json"

bar; echo "  2/4  PLAN — manifest → mapping plan + approval document"; bar
python3 -m gcp_aidp.cli plan "$OUT/inventory.json" -o "$OUT/plan.json"

bar; echo "  3/4  MIGRATE — translated artifacts, written locally only"; bar
python3 -m gcp_aidp.cli migrate "$OUT/plan.json" -o "$OUT/migrated" | tail -3

bar; echo "  4/4  VERIFY"; bar
python3 -m gcp_aidp.cli verify "$OUT/migrated" | head -11

bar; echo "  A view with rewrites (v_order_kpis): BEFORE (GoogleSQL)"; bar
show bigquery.view.sales.v_order_kpis source_sql
bar; echo "  AFTER (Spark SQL on AIDP) — REVIEW: two rewrites carry a caveat"; bar
cat "$OUT/migrated/views/sales.v_order_kpis.sql"

bar; echo "  A blocked view (v_latest_order_per_customer) — never partially translated"; bar
cat "$OUT/migrated/views/sales.v_latest_order_per_customer.sql"

bar; echo "  Artifacts at $OUT/"; bar
echo "  → $OUT/plan.md                (approval document)"
echo "  → $OUT/migrated/report.md     (migration report, before/after per asset)"
echo
echo "  publish (dry run by default) arrives in M5; the data copy notebooks in M4."
