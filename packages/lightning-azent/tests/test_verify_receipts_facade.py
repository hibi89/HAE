import tempfile
import unittest
from pathlib import Path

from lightning_azent.engine import PlanError
from lightning_azent.runtime import LAExecutor


class VerifyReceiptsFacadeTests(unittest.TestCase):
    def test_receipts_validate_completed_literal_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = LAExecutor(root / 'state.sqlite', root / 'business.sqlite')
            plan = {'version': 'axflow.ir.v0', 'steps': [{'id': 'seed', 'op': 'literal', 'value': 1}]}
            executor.execute(plan, 'completed_run')
            result = executor.verify_receipts(plan, 'completed_run')
            self.assertEqual(result, {'run_id': 'completed_run', 'verified': True})

    def test_missing_run_does_not_create_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = LAExecutor(root / 'state.sqlite', root / 'business.sqlite')
            plan = {'version': 'axflow.ir.v0', 'steps': [{'id': 'seed', 'op': 'literal', 'value': 1}]}
            with self.assertRaises(PlanError):
                executor.verify_receipts(plan, 'missing_run')
            self.assertFalse((root / 'state.sqlite').exists())
            self.assertFalse((root / 'business.sqlite').exists())

    def test_invalid_run_id_does_not_create_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = LAExecutor(root / 'state.sqlite', root / 'business.sqlite')
            with self.assertRaises(PlanError):
                executor.verify_receipts({'version': 'axflow.ir.v0', 'steps': [{'id': 'seed', 'op': 'literal', 'value': 1}]}, '../unsafe')
            self.assertFalse((root / 'state.sqlite').exists())
            self.assertFalse((root / 'business.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
