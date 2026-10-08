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
- `demo.sh`: the offline demo.
