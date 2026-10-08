# Test estate: setup, manual steps, and the M3 check

`seed.sql` creates everything SQL can create. The objects below need the console,
the `bq` CLI, or billing. Replace `<project>` with your project id throughout.

## 0. Before you start

- **Billing.** The BigQuery sandbox (no billing account) runs `seed.sql`, but
  it has no scheduled queries and no Cloud Storage, so steps 2 and 3 need billing
  enabled. In the sandbox, tables and partitions also expire after 60 days, so
  `orders` and `order_items` keep only the last 60 days of thelook's data.
- **Service account** (read-only), for `gcp-aidp inventory` and the AIDP copy:
  BigQuery Data Viewer, BigQuery Read Session User and BigQuery Job User. Listing
  buckets (`storage.buckets.list`) and scheduled queries (`bigquery.transfers.get`)
  needs more than those roles; if one is missing, the inventory records that
  collection as *not scanned* and names the refused permission, so add a role
  holding it only if you need that collection. Keep the JSON key outside the
  repository and point to it from your shell:
  `export GOOGLE_APPLICATION_CREDENTIALS=/path/outside/the/repo/key.json`.

## 1. Seed

Open BigQuery Studio in `<project>`, paste `seed.sql`, and run it as one script.

## 2. Scheduled query (billing required)

```bash
bq mk --transfer_config --project_id=<project> --location=US \
  --data_source=scheduled_query --target_dataset=migration_test \
  --display_name="migration_test status summary" --schedule="every 24 hours" \
  --params='{"query":"SELECT status, COUNT(*) AS n FROM migration_test.orders GROUP BY status",
             "destination_table_name_template":"status_summary_daily",
             "write_disposition":"WRITE_TRUNCATE"}'
```

Or in the console: run that query, then **Schedule** → *Create new scheduled query*.

## 3. Cloud Storage and an external table (billing required)

```bash
gcloud storage buckets create gs://<project>-migration-test --location=US
bq query --use_legacy_sql=false \
  "EXPORT DATA OPTIONS (uri='gs://<project>-migration-test/products/*.parquet', format='PARQUET')
   AS SELECT * FROM migration_test.products"
bq query --use_legacy_sql=false \
  "CREATE OR REPLACE EXTERNAL TABLE migration_test.ext_products
   OPTIONS (format='PARQUET', uris=['gs://<project>-migration-test/products/*.parquet'])"
```

## 4. Saved query

In BigQuery Studio, open a new query, paste
`saved_queries/Returned_orders_by_status.sql`, and **Save** it as
*Returned orders by status*. The inventory cannot read saved queries through an API
in 0.1, so pass the exported copy instead:
`--saved-queries-dir test-estate/saved_queries`.

## 5. Notebook

In BigQuery Studio, create a notebook named *migration test notebook*. The
inventory records notebooks as **not scanned** in 0.1 (they migrate in 0.2), and
the plan shows that at the top.

## 6. Run the inventory (M3 check)

```bash
pip install -e '.[gcp]'
export GOOGLE_APPLICATION_CREDENTIALS=/path/outside/the/repo/key.json
gcp-aidp inventory --project <project> --saved-queries-dir test-estate/saved_queries -o inv.json
gcp-aidp plan inv.json -o plan.json
```

Every call is a metadata `GET` with a read-only token: nothing is queried and
nothing is billed. Add `--scan-services` to also list Dataproc, Composer,
Dataform, Dataflow and Vertex AI (their APIs refuse a read-only token, so this
asks for a broader one; the calls are still GETs). In the sandbox they report
"API not enabled: none". Check that `inv.json` lists:

| Collection | Expected |
|---|---|
| datasets | `migration_test` |
| tables | `users`, `products`, `orders`, `order_items`, `customer_profiles`, `type_carried`, `type_blocked` (and `status_summary` / `status_summary_daily` if the procedure or the scheduled query has run) |
| views | `v_simple`, `v_rewritable`, `v_blocked` |
| materialized_views | `mv_daily_orders` |
| routines | `net_price` (SQL), `parse_utm` (JAVASCRIPT), `refresh_status_summary` (PROCEDURE) |
| external_tables | `ext_products` (with billing) |
| scheduled_queries | *migration_test status summary* (with billing) |
| saved_queries | *Returned_orders_by_status* (from the folder) |
| access_policies | the dataset's IAM entries, one per role |
| gcs | `<project>-migration-test` (with billing) |
| not scanned | notebooks, pipelines (listed at the top of `plan.md`) |

Then send me the output of `gcp-aidp inventory` and of the probe below. The output
holds metadata only (no data, and no credentials).

## 7. Zero-byte semantic probes

```bash
python3 scripts/probe_bigquery_semantics.py --project <project>
```

Each probe is a query on literals. It is dry-run first and refused unless
BigQuery reports 0 bytes processed. It prints BigQuery's answer next to Spark
3.5's, which confirms or changes the translator rules marked † in
`references/dialect-translation.md`.

## Teardown

```bash
bq query --use_legacy_sql=false < test-estate/teardown.sql
bq rm --transfer_config <transfer-config-resource-name>   # from: bq ls --transfer_config --transfer_location=US
gcloud storage rm --recursive gs://<project>-migration-test
```
