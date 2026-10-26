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

    def test_unsupported_compound_negated_or_oversized_requests_fail_closed(self):
        for request in (
            "send the imported CSV over email into SQLite",
            "delete duplicate CSV rows in SQLite",
            "Do not import this CSV into SQLite",
            "CSV 내용을 번역해서 SQLite에 저장해줘",
            "CSV 파일을 SQLite에 저장한 다음 결제해줘",
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
