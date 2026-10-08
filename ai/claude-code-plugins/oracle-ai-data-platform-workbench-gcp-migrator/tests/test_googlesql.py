"""One test per GoogleSQL → Spark rule (references/dialect-translation.md)."""
from __future__ import annotations

import unittest

from gcp_aidp.translate.googlesql_to_spark import Context, translate

CTX = Context(project="proj",
              relations={("sales", "orders"): ("cat", "sales", "orders")},
              functions={("sales", "net"): ("cat", "sales", "net")},
              buckets={"landing": "landing-oci"}, namespace="ns")


def t(sql):
    return translate(sql, CTX)


def rules(r, severity=None):
    return {f.rule for f in r.findings if severity is None or f.severity == severity}


class Rewrites(unittest.TestCase):
    def test_G01_REFERENCE(self):
        r = t("SELECT * FROM `proj.sales.orders` JOIN sales.orders o ON TRUE")
        self.assertEqual(r.sql, "SELECT * FROM `cat`.`sales`.`orders` JOIN `cat`.`sales`.`orders` o ON TRUE")
        self.assertEqual(r.status, "ok")
        self.assertEqual(t("SELECT `proj`.sales.orders.x FROM `proj`.`sales`.`orders`").sql,
                         "SELECT `proj`.sales.orders.x FROM `cat`.`sales`.`orders`")

    def test_G01_function_reference(self):
        self.assertEqual(t("SELECT sales.net(1)").sql, "SELECT `cat`.`sales`.`net`(1)")

    def test_G01_column_paths_are_left_alone(self):
        r = t("SELECT o.address.city FROM `proj.sales.orders` o")
        self.assertIn("o.address.city", r.sql)
        self.assertEqual(r.status, "ok")

    def test_G01_unresolved_and_cross_project_are_flagged(self):
        self.assertEqual(t("SELECT 1 FROM `proj.sales.missing`").status, "needs_manual_review")
        r = t("SELECT 1 FROM `other.sales.orders`")
        self.assertIn("cross-project", r.findings[0].detail)

    def test_G03_SAFE_DIVIDE(self):
        r = t("SELECT SAFE_DIVIDE(a, b) FROM `proj.sales.orders`")
        self.assertIn("try_divide(a, b)", r.sql)
        self.assertIn("G03_SAFE_DIVIDE", rules(r, "caveat"))

    def test_G04_COUNTIF(self):
        r = t("SELECT COUNTIF(x > 1) FROM `proj.sales.orders`")
        self.assertIn("count_if(x > 1)", r.sql)
        self.assertEqual(r.status, "ok")

    def test_G06_TIMESTAMP_TRUNC(self):
        r = t("SELECT TIMESTAMP_TRUNC(ts, ISOWEEK)")
        self.assertEqual(r.sql, "SELECT date_trunc('WEEK', ts)")
        self.assertIn("G06_TIMESTAMP_TRUNC", rules(r, "caveat"))
        self.assertIn("G06_TIMESTAMP_TRUNC", rules(t("SELECT TIMESTAMP_TRUNC(ts, WEEK)"), "flag"))
        self.assertIn("G06_TIMESTAMP_TRUNC", rules(t("SELECT TIMESTAMP_TRUNC(ts, DAY, 'UTC')"), "flag"))

    def test_G06_nested_rewrites_compose(self):
        self.assertEqual(t("SELECT TIMESTAMP_TRUNC(COUNTIF(x), DAY)").sql, "SELECT date_trunc('DAY', count_if(x))")

    def test_G07_DATE_DIFF(self):
        r = t("SELECT DATE_DIFF(a, b, DAY)")
        self.assertEqual((r.sql, r.status), ("SELECT datediff(a, b)", "ok"))
        self.assertIn("G07_DATE_DIFF", rules(t("SELECT DATE_DIFF(a, b, MONTH)"), "flag"))

    def test_G08_FORMAT_DATE(self):
        r = t("SELECT FORMAT_DATE('%Y/%m/%d', d)")
        self.assertEqual(r.sql, "SELECT date_format(d, 'yyyy/MM/dd')")
        self.assertIn("G08_FORMAT_DATE", rules(r, "caveat"))
        self.assertIn("G08_FORMAT_DATE", rules(t("SELECT FORMAT_DATE('%A', d)"), "flag"))

    def test_G19_CAST_TYPE(self):
        r = t("SELECT CAST(a AS INT64), CAST(b AS ARRAY<STRUCT<x FLOAT64, y NUMERIC(10, 2)>>)")
        self.assertEqual(r.sql, "SELECT CAST(a AS BIGINT), CAST(b AS ARRAY<STRUCT<x DOUBLE, y DECIMAL(10, 2)>>)")
        self.assertEqual(r.status, "ok")
        self.assertIn("G19_CAST_TYPE", rules(t("SELECT CAST(a AS GEOGRAPHY)"), "flag"))

    def test_G20_HASH_COMMENT(self):
        self.assertEqual(t("SELECT 1 # note").sql, "SELECT 1 -- note")

    def test_G21_GCS_PATH(self):
        r = t("SELECT 'gs://landing/a.csv', 'gs://elsewhere/b'")
        self.assertIn("'oci://landing-oci@ns/a.csv'", r.sql)
        self.assertIn("'gs://elsewhere/b'", r.sql)
        self.assertEqual(r.status, "needs_manual_review")

    def test_literals_and_comments_are_never_rewritten(self):
        sql = "SELECT 'COUNTIF(x) FROM sales.orders' -- SAFE_DIVIDE(a, b)\n/* QUALIFY */"
        r = t(sql)
        self.assertEqual((r.sql, r.status), (sql, "ok"))


class Flags(unittest.TestCase):
    def flagged(self, sql, rule):
        r = t(sql)
        self.assertIn(rule, rules(r, "flag"))
        self.assertEqual(r.status, "needs_manual_review")
        return r

    def test_G02_SAFE_CAST(self):
        r = self.flagged("SELECT SAFE_CAST(x AS INT64)", "G02_SAFE_CAST")
        self.assertIn("SAFE_CAST", r.sql)

    def test_G05_GENERATE_ARRAY(self):
        self.flagged("SELECT GENERATE_ARRAY(5, 1)", "G05_GENERATE_ARRAY")

    def test_G08_PARSE_DATE(self):
        self.flagged("SELECT PARSE_DATE('%Y-%m-%d', s)", "G08_PARSE_DATE")

    def test_G09_ARRAY_LENGTH(self):
        self.flagged("SELECT ARRAY_LENGTH(a)", "G09_ARRAY_LENGTH")

    def test_G10_REGEXP(self):
        self.flagged("SELECT REGEXP_CONTAINS(s, r'a+')", "G10_REGEXP")

    def test_G11_JSON(self):
        self.flagged("SELECT JSON_VALUE(j, '$.a')", "G11_JSON")

    def test_G12_STRING_AGG(self):
        self.flagged("SELECT STRING_AGG(s, ',')", "G12_STRING_AGG")

    def test_G13_UNNEST(self):
        self.flagged("SELECT x FROM UNNEST([1, 2]) AS x", "G13_UNNEST")

    def test_G14_STAR_MODIFIER(self):
        self.flagged("SELECT * EXCEPT (a) FROM t", "G14_STAR_MODIFIER")
        self.flagged("SELECT * REPLACE (a + 1 AS a) FROM t", "G14_STAR_MODIFIER")

    def test_G22_SAME_NAME(self):
        self.flagged("SELECT SPLIT(s, '.')", "G22_SAME_NAME")
        self.flagged("SELECT DATE_SUB(d, INTERVAL 1 DAY)", "G22_SAME_NAME")

    def test_G23_QUERY_PARAMETER(self):
        self.flagged("SELECT @run_date", "G23_QUERY_PARAMETER")

    def test_G24_LITERAL(self):
        self.flagged("SELECT b'abc'", "G24_LITERAL")
        self.flagged("SELECT '''it's'''", "G24_LITERAL")

    def test_G90_NOT_SPARK_BUILTIN(self):
        self.flagged("SELECT ARRAY_TO_STRING(a, ',')", "G90_NOT_SPARK_BUILTIN")
        self.flagged("SELECT SAFE.PARSE_JSON(s)", "G01_REFERENCE")
        self.assertEqual(t("SELECT ifnull(a, 0), coalesce(a, 1) FROM t").status, "ok")


class Blocks(unittest.TestCase):
    def blocked(self, sql, rule):
        r = t(sql)
        self.assertIn(rule, rules(r, "block"))
        self.assertEqual((r.status, r.sql), ("blocked", sql))  # never partially translated

    def test_G15_QUALIFY(self):
        self.blocked("SELECT COUNTIF(a) FROM t QUALIFY ROW_NUMBER() OVER () = 1", "G15_QUALIFY")

    def test_G16_PSEUDO_COLUMN(self):
        self.blocked("SELECT _PARTITIONTIME FROM t", "G16_PSEUDO_COLUMN")
        self.blocked("SELECT * FROM `proj.logs.events_*`", "G16_PSEUDO_COLUMN")

    def test_G17_SCRIPTING(self):
        self.blocked("DECLARE x INT64 DEFAULT 1", "G17_SCRIPTING")
        self.blocked("CALL `proj.sales.close`()", "G17_SCRIPTING")
        self.blocked("SELECT 1; SELECT 2", "G17_SCRIPTING")
        self.assertEqual(t("SELECT 1;").status, "ok")

    def test_G18_ML_AI_GEO(self):
        self.blocked("SELECT * FROM ML.PREDICT(MODEL m, TABLE t)", "G18_ML_AI_GEO")
        self.blocked("SELECT ST_DISTANCE(a, b)", "G18_ML_AI_GEO")

    def test_G98_UNBALANCED(self):
        self.blocked("SELECT 'open", "G98_UNBALANCED")
        self.blocked("SELECT (1", "G98_UNBALANCED")


if __name__ == "__main__":
    unittest.main()
