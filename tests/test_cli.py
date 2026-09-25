import csv
import json
import tempfile
import unittest
from pathlib import Path
from azure_focus_cost_review.cli import ExportError, analyze, main

HEADER = ["BilledCost", "BillingCurrency", "ChargePeriodStart", "ServiceName", "Tags"]


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "export.csv"

    def write(self, rows, header=HEADER):
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def test_aggregation_refunds_and_unallocated(self):
        self.write([
            ["2.50", "EUR", "2026-09-01T12:30:00Z", "Virtual Machines", '{"costCenter":"platform"}'],
            ["-0.25", "EUR", "2026-09-02T12:30:00Z", "Virtual Machines", '{"costCenter":"platform"}'],
            ["1.00", "USD", "2026-09-02T12:30:00Z", "Virtual Machines", "{}"],
        ])
        result = analyze([self.path], "costCenter")
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["currencies"], ["EUR", "USD"])
        self.assertEqual(result["groups"][0]["billed_cost"], "2.25")
        self.assertEqual(result["groups"][1]["allocation"], "(unallocated)")

    def test_multiple_files_accumulate(self):
        self.write([["1", "EUR", "2026-09-01T00:00Z", "Storage", "{}"]])
        self.assertEqual(analyze([self.path, self.path], "costCenter")["groups"][0]["billed_cost"], "2")

    def test_missing_columns(self):
        self.write([], ["BilledCost"])
        with self.assertRaisesRegex(ExportError, "missing columns"):
            analyze([self.path], "costCenter")

    def test_bad_tags(self):
        self.write([["1", "EUR", "2026-09-01T00:00Z", "Storage", "not json"]])
        with self.assertRaisesRegex(ExportError, "Tags is not valid JSON"):
            analyze([self.path], "costCenter")

    def test_nan_and_invalid_dates(self):
        self.write([["NaN", "EUR", "2026-09-01T00:00Z", "Storage", "{}"]])
        with self.assertRaisesRegex(ExportError, "non-finite"):
            analyze([self.path], "costCenter")
        self.write([["1", "EUR", "2026-09-01", "Storage", "{}"]])
        with self.assertRaisesRegex(ExportError, "invalid ChargePeriodStart"):
            analyze([self.path], "costCenter")

    def test_cli_output(self):
        self.write([["1.00", "EUR", "2026-09-01T00:00Z", "Storage", "{}"]])
        output = Path(self.temp.name) / "result.json"
        self.assertEqual(main(["--output", str(output), str(self.path)]), 0)
        self.assertEqual(json.loads(output.read_text())["groups"][0]["billed_cost"], "1.00")


if __name__ == "__main__":
    unittest.main()
