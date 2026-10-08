# gcp-aidp-migrator

Migration assistant for Google Cloud → Oracle AI Data Platform (AIDP). It
inventories a Google Cloud data estate centred on BigQuery, plans the mapping to
AIDP, and (in later milestones) generates reviewable artifacts and copy jobs,
verifies them, and publishes to AIDP on request.

> **Work in progress (0.1, milestone M2).** `inventory` (fixture mode), `plan`,
> `migrate` and `verify` work offline today. Live inventory, the data-copy
> notebooks and `publish` are not built yet. Full documentation arrives with M6.

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
