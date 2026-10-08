# gcp-aidp-migrator

Migration assistant for Google Cloud → Oracle AI Data Platform (AIDP). It
inventories a Google Cloud data estate centred on BigQuery, plans the mapping to
AIDP, and (in later milestones) generates reviewable artifacts and copy jobs,
verifies them, and publishes to AIDP on request.

> **Work in progress (0.1, milestone M5).** `inventory` (live and fixture),
> `plan`, `migrate` and `verify` are built. Live inventory has been run against
> a seeded sandbox project (BigQuery only: no billing, so no Cloud Storage,
> scheduled queries or other services). The data-copy notebooks have run end to
> end on an AIDP cluster (Spark 3.5.0) against that project: 7 tables copied
> with matching row counts, 3 views created. `publish` and `run` are built and
> tested against a fake AIDP client, not yet against a live workspace. Full
> documentation arrives with M6.

## Quick start (offline, no credentials)

```bash
cd oracle-aidp-samples/ai/claude-code-plugins/oracle-ai-data-platform-workbench-gcp-migrator
./demo.sh
```

The demo reads `gcp_aidp/fixtures/demo-manifest.json`, an invented estate
(Northwind Retail): 4 datasets, 35 tables, 8 views, 2 materialized views,
routines, BigQuery ML models, saved and scheduled queries, access policies, 4
Cloud Storage buckets, and Dataproc, Composer, Dataform, Dataflow and Vertex AI
assets. It writes `plan.json` and the approval document `plan.md`.

> **Codex / Cursor / any MCP client:** `inventory`, `plan`, `migrate` and
> `verify` are also exposed as an **MCP server** (`gcp-aidp-mcp`, wired up in
> `.mcp.json`). Run `pip install -e '.[mcp]'` (Python 3.10+) before first use;
> without it the server exits and the client reports it as failed in `/mcp`.
> `publish` and `run` change an AIDP workspace, so they are CLI-only.

## Live inventory (read-only)

```bash
pip install -e '.[gcp]'                       # google-auth only
export GOOGLE_APPLICATION_CREDENTIALS=/path/outside/the/repo/key.json
gcp-aidp inventory --project <project> [--regions us-central1] [--saved-queries-dir dir] [--scan-services] -o inv.json
```

Every call is a metadata `GET` made with a `cloud-platform.read-only` token, so
Google refuses any write. Dataproc, Composer, Dataform, Dataflow and Vertex AI
refuse a read-only token, so they are listed only with `--scan-services`. That
flag asks for a `cloud-platform` token for those five services only, and read-only
then rests on the client sending GETs only and on the service account's
viewer roles. Without it, they are recorded as *not scanned*. No query runs, and no bytes are billed. Row counts
come from table metadata. Anything the scan could not read is recorded as *not
scanned* and shown at the top of the plan: saved queries (pass
`--saved-queries-dir` instead), BigQuery Studio notebooks and pipelines in 0.1,
and any API call that was refused. A service whose API is disabled is recorded
as having nothing to migrate.

`test-estate/` recreates a small estate in any project (`seed.sql`,
`MANUAL_STEPS.md`, `teardown.sql`), with a checklist of what the inventory must
list.

Every asset gets a plan row with one of three actions:

| Action | Meaning |
|---|---|
| `MIGRATE` | migrated in this version |
| `REPORT` | inventoried and reported with an effort band; not translated (procedures, JavaScript and table functions, BigQuery ML models, access rules) |
| `SKIP` | planned for a later version, with the reason (notebooks and Dataproc in 0.2, Composer and Dataform in 0.3, Dataflow and Vertex AI later) |

Two assets that would land on the same target name (compared case-insensitively,
as Spark does) halt the plan. The planner does not pick a winner.

`migrate` writes one reviewable artifact per asset (schemas, tables, views,
materialized views, external tables, functions, saved and scheduled queries,
rclone transfer jobs) plus `report.json` and `report.md`. It writes files
locally only; nothing reaches AIDP before `publish --apply`. `verify` labels
every asset:

| Verdict | Meaning |
|---|---|
| PASS | translated, and no known issue was detected |
| REVIEW | a caveat or flag needs a human, or the asset is blocked (not translated) |
| SKIP | reported only, or planned for a later version |
| FAIL | the migrator failed, or the report contradicts itself |

> **What PASS means.** PASS = *translated, and no known issue was detected*. It is
> **not execution-verified**: `verify` does not parse or run the generated artifacts,
> so a construct none of the rules cover is reported clean. Treat PASS as "nothing
> the tool knows about is wrong here", and review artifacts before running them in
> production. REVIEW is the honest signal that something needs a human — a low
> REVIEW count is not by itself evidence of a clean migration.

## Copying the data

`migrate` also writes four self-contained notebooks to `migrated/notebooks/`,
which run on an AIDP cluster (the Snowflake migrator's pattern):

| Notebook | Reads | Writes |
|---|---|---|
| `00_diagnose` | connector, credential, catalog | nothing; prints the connector's type for every column |
| `01_structure` | the plan | schemas, empty Delta tables (each read back against the plan), views |
| `02_copy_dataset` | one BigQuery dataset, table by table | rows; verifies counts, and with `counts+sums` exact decimal sums |
| `03_reconcile` | plan, reports, catalog | `MIGRATION_REPORT.md` |

Prerequisites: AIDP has no built-in BigQuery connector. Install the open-source
Spark BigQuery connector as a **cluster library**, as a JAR file
(`spark-bigquery-with-dependencies_2.12-<version>.jar`; AIDP cluster libraries
take a JAR, not a Maven coordinate), on a Spark 3.5 / Scala 2.12 cluster. Store
the read-only service account key, base64-encoded, in the **AIDP credential
store** (default entry `gcp_bigquery_reader`, key `credentials_b64`). The
notebooks read it there and never print it. The service account needs
BigQuery Data Viewer, BigQuery Read Session User and BigQuery Job User.

The copy reads tables only: reading a view or a query result makes the
connector write a temporary table in BigQuery, so views are rebuilt from their
translated SQL and materialized views from their query. Nothing is dropped:
the default `skip-existing` mode leaves a table with rows untouched, and
`overwrite` rewrites rows, never the table.

> **Consistency.** Each table is copied at its own moment. If the source keeps
> changing during the copy, the target is consistent per table but not across
> tables. For a cutover, stop writers or copy from BigQuery table snapshots.

The rule tables are [`references/type-mapping.md`](references/type-mapping.md)
and [`references/dialect-translation.md`](references/dialect-translation.md).

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

`tests/test_spark_runtime.py` runs the demo's generated SQL on a local Spark
3.5 + Delta and is skipped unless both are installed:

```bash
pip install pyspark==3.5.9 delta-spark==3.2.1    # needs Java 17
python3 -m unittest tests.test_spark_runtime
```
