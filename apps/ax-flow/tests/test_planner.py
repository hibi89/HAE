import unittest

from axflow.engine import PlanError
from axflow.planner import plan_request


class PlannerTests(unittest.TestCase):
    def test_supported_english_and_korean_requests_generate_the_same_ir(self):
        expected = {
            "version": "axflow.ir.v0",
            "steps": [
                {"id": "input", "op": "csv_read", "path": "contacts.csv"},
                {"id": "imported", "op": "sqlite_import_csv", "from": "input"},
            ],
        }
        for request in (
            "Import this CSV file into local SQLite",
            "이 CSV 파일을 로컬 SQLite에 저장해줘",
            "CSV를 SQLite로 가져오기",
        ):
            with self.subTest(request=request):
                self.assertEqual(plan_request(request, "contacts.csv"), expected)

    def test_bounded_column_normalization_is_planned_before_filter_and_import(self):
        expected = {
            "version": "axflow.ir.v0",
            "steps": [
                {"id": "input", "op": "csv_read", "path": "contacts.csv"},
                {"id": "normalized", "op": "csv_normalize", "from": "input",
                 "transforms": {"name": "trim"}},
                {"id": "imported", "op": "sqlite_import_csv", "from": "normalized"},
            ],
        }
        for request in (
            "Trim whitespace in the name column, then import this CSV into local SQLite",
            "CSV의 name 열 앞뒤 공백을 제거하고 로컬 SQLite에 저장해줘",
        ):
            with self.subTest(request=request):
                self.assertEqual(plan_request(request, "contacts.csv"), expected)

        filtered = plan_request(
            "Lowercase the email column and import this CSV with amount > 10 into SQLite",
            "contacts.csv",
        )
        self.assertEqual([step["op"] for step in filtered["steps"]], [
            "csv_read", "csv_normalize", "csv_filter", "sqlite_import_csv",
        ])
        self.assertEqual(filtered["steps"][2]["from"], "normalized")
        self.assertEqual(filtered["steps"][1]["transforms"], {"email": "lower"})

    def test_explicit_numeric_and_string_column_conversions_are_planned(self):
        for request, field, transform in (
            ("Convert the amount column to a number, then import this CSV into SQLite", "amount", "number"),
            ("CSV의 amount 열을 숫자로 변환하고 로컬 SQLite에 저장해줘", "amount", "number"),
            ("Convert the name column to string, then import this CSV into SQLite", "name", "string"),
            ("CSV의 name 열을 문자열로 변환하고 로컬 SQLite에 저장해줘", "name", "string"),
        ):
            with self.subTest(request=request):
                plan = plan_request(request, "contacts.csv")
                self.assertEqual([step["op"] for step in plan["steps"]], [
                    "csv_read", "csv_normalize", "sqlite_import_csv",
                ])
                self.assertEqual(plan["steps"][1]["transforms"], {field: transform})

        numeric_filter = plan_request(
            "Convert amount to number and import this CSV where amount > 10 into SQLite",
            "contacts.csv",
        )
        self.assertEqual(numeric_filter["steps"][1]["transforms"], {"amount": "number"})
        self.assertEqual(numeric_filter["steps"][2]["from"], "normalized")

    def test_unsupported_compound_negated_or_oversized_requests_fail_closed(self):
        for request in (
            "send the imported CSV over email into SQLite",
            "delete duplicate CSV rows in SQLite",
            "Do not import this CSV into SQLite",
            "CSV 내용을 번역해서 SQLite에 저장해줘",
            "CSV 파일을 SQLite에 저장한 다음 결제해줘",
            "clean this CSV into SQLite",
            "deduplicate this CSV into SQLite",
            "convert CSV values to arbitrary objects and import into SQLite",
            "Trim the name column and lowercase the email column in this CSV before saving to SQLite",
            "Trim this CSV name column",
            " ", "x" * 513,
        ):
            with self.subTest(request=request), self.assertRaises(PlanError):
                plan_request(request, "contacts.csv")

    def test_missing_domains_or_action_are_rejected(self):
        for request in ("import this CSV", "save JSON into SQLite", "CSV SQLite"):
            with self.subTest(request=request), self.assertRaises(PlanError):
                plan_request(request, "contacts.csv")


if __name__ == "__main__":
    unittest.main()
