"""The generated data-plane notebooks, without Spark."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gcp_aidp.dataplane import STAGES
from gcp_aidp.migrate import migrate
from gcp_aidp.plan import build_plan

DEMO = json.loads((Path(__file__).parents[1] / "gcp_aidp/fixtures/demo-manifest.json").read_text())


class Notebooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.report = migrate(build_plan(DEMO), out_dir=cls.out)
        cls.dp = json.loads((cls.out / "notebooks/data_plan.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_one_self_contained_notebook_per_stage(self):
        self.assertEqual(self.report["notebooks"], [f"notebooks/{s}.ipynb" for s in STAGES])
        for path in self.report["notebooks"]:
            nb = json.loads((self.out / path).read_text())
            self.assertEqual((nb["nbformat"], nb["metadata"]["kernelspec"]["name"]), (4, "python3"))
            code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
            for cell in code:
                compile(cell, path, "exec")  # every cell is valid Python
                self.assertNotIn("from gcp_aidp", cell)  # nothing to upload beside the notebook
            self.assertIn("raise RuntimeError", code[-1])  # a failed stage fails the task
            self.assertNotIn("SystemExit", code[-1].split("\n", 3)[-1])

    def test_data_plan_holds_only_what_can_run(self):
        tables = {f"{t['dataset']}.{t['name']}" for t in self.dp["tables"]}
        self.assertIn("sales.orders", tables)
        self.assertNotIn("sales.store_visits", tables)  # blocked: GEOGRAPHY and more
        views = {v["name"] for v in self.dp["views"]}
        self.assertEqual(views, {"v_active_customers", "v_campaign_days", "v_order_kpis", "v_payments_masked",
                                 "v_latest_order_per_customer"})
        verdicts = {x["name"]: x["verdict"] for x in self.dp["not_created"]}
        self.assertEqual(verdicts["v_all_app_events"], "BLOCKED")
        self.assertEqual(verdicts["v_customer_tags"], "NEEDS_REVIEW")  # flagged UNNEST
        self.assertEqual(verdicts["mv_daily_sales"], "DEFERRED")
        self.assertEqual(self.dp["tables"][0]["source"], "northwind-analytics-demo.sales.orders")

    def test_credential_defaults_and_no_secret_in_notebooks(self):
        text = (self.out / "notebooks/02_copy_dataset.ipynb").read_text()
        self.assertIn("'credential-name': 'gcp_bigquery_reader'", text)
        self.assertIn("'viewsEnabled', 'false'", text.replace('\\"', "'").replace('"', "'"))
        self.assertNotIn("private_key\\\": \\\"-----", text)


if __name__ == "__main__":
    unittest.main()
