# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [Unreleased]

### Added
- Plugin skeleton: `.claude-plugin/plugin.json`, `pyproject.toml`, `gcp-aidp` CLI.
- `inventory --fixture demo`: the bundled Northwind Retail estate, built by
  `gcp_aidp/fixtures/build_demo_manifest.py`.
- `plan`: one row per asset with `MIGRATE` / `REPORT` / `SKIP`, the version
  each source is migrated in, and an approval document (`plan.md`). Halts on
  duplicate ids and on name collisions.
- `demo.sh`: the offline demo, inventory through verify.
- Type mapping (`TY01`–`TY17`, `TY99`) recorded on every planned column, with
  `--bignumeric string` and `--geography wkt` modes; table layout rules
  (`D01`–`D04`): liquid `CLUSTER BY` wherever BigQuery partitioning is not an
  exact Delta partition.
- GoogleSQL → Spark SQL translator: a lexer plus 27 named rules (rewrite,
  caveat, flag, block); a blocked statement is never partially translated.
  Spark-side behaviour checked on Spark 3.5.9.
- `gs://` → `oci://` rewriting through the bucket map, and an rclone transfer
  job per bucket.
- `migrate`: one artifact per asset plus `report.json` / `report.md`; offline.
- `verify`: PASS / REVIEW / SKIP / FAIL, failing closed on an interrupted run,
  a count mismatch, or a missing or escaping artifact.
- Tests for every rule ID, and an optional Spark 3.5 + Delta runtime test.
- Live inventory: BigQuery (datasets, tables, views, materialized views,
  external tables, routines, models, row access policies, column policy tags,
  dataset IAM, scheduled queries), Cloud Storage, and Dataproc, Composer,
  Dataform, Dataflow and Vertex AI for SKIP reporting. Read-only REST GETs with
  a `cloud-platform.read-only` token; `google-auth` is the only dependency.
  Gaps are recorded as *not scanned* and shown in the plan.
- `--scan-services`: those five APIs refuse a read-only token, so they are
  listed only on request, with a `cloud-platform` token used for them alone.
- Run against a seeded sandbox project: every object `seed.sql` creates is
  listed, and the zero-byte probes confirmed or corrected the BigQuery side of
  the translator rules (`G02_SAFE_CAST`'s reason was wrong and is fixed).
- `G97_LEGACY_SQL`: a legacy SQL view is blocked.
- `test-estate/`: `seed.sql`, `MANUAL_STEPS.md`, `teardown.sql`.
- `scripts/probe_bigquery_semantics.py`: zero-byte queries that confirm the
  BigQuery side of the translator rules.
