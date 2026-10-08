# gcp-aidp-migrator

Migration assistant for Google Cloud → Oracle AI Data Platform (AIDP). It
inventories a Google Cloud data estate centred on BigQuery, plans the mapping to
AIDP, and (in later milestones) generates reviewable artifacts and copy jobs,
verifies them, and publishes to AIDP on request.

> **Work in progress (0.1, milestone M1).** `inventory` (fixture mode) and
> `plan` work today. Live inventory, `migrate`, `verify` and `publish` are not
> built yet. Full documentation arrives with M6.

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

Every asset gets a plan row with one of three actions:

| Action | Meaning |
|---|---|
| `MIGRATE` | migrated in this version |
| `REPORT` | inventoried and reported with an effort band; not translated (procedures, JavaScript and table functions, BigQuery ML models, access rules) |
| `SKIP` | planned for a later version, with the reason (notebooks and Dataproc in 0.2, Composer and Dataform in 0.3, Dataflow and Vertex AI later) |

Two assets that would land on the same target name (compared case-insensitively,
as Spark does) halt the plan. The planner does not pick a winner.

## Tests

```bash
python3 -m unittest discover -s tests -t .
```
