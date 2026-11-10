"""HAE planner-to-LA opt-in adapter contract (isolated bridge stub)."""
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from axflow.la_adapter import HAEConsumer


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Mock()
        self.bridge.review.return_value.public_view.return_value = {'approved': False}
        self.bridge.execute.return_value = {'ok': True}
        self.bridge.evidence.return_value = {'verified': True}
        self.consumer = HAEConsumer(self.bridge)
        self.plan = {'version': 'axflow.ir.v0', 'steps': [{'id': 'x', 'op': 'literal', 'value': 'bounded'}]}
        self.patcher = patch('axflow.la_adapter.plan_request', return_value=self.plan)
        self.planner = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_rejects_missing_bridge(self):
        with self.assertRaises(TypeError): HAEConsumer(None)

    def test_rejects_incomplete_bridge(self):
        with self.assertRaises(TypeError): HAEConsumer(object())

    def test_preview_uses_hae_planner_exact_request(self):
        self.assertEqual(self.consumer.preview('task', 'source.csv', 'RunA'), {'approved': False})
        self.planner.assert_called_once_with('task', 'source.csv')
        self.bridge.review.assert_called_once_with(self.plan, 'RunA')

    def test_execute_preserves_explicit_denied_defaults(self):
        self.assertEqual(self.consumer.execute('task', 'source.csv', 'RunA'), {'ok': True})
        self.bridge.execute.assert_called_once_with(self.plan, 'RunA', synthetic=False,
            owner_confirmed=False, confirmed_request_sha256=None, resume=False)

    def test_execute_forwards_all_consent_scope_args(self):
        self.consumer.execute('task', 'source.csv', 'RunA', synthetic=True,
            owner_confirmed=True, confirmed_request_sha256='abc', resume=True)
        self.bridge.execute.assert_called_once_with(self.plan, 'RunA', synthetic=True,
            owner_confirmed=True, confirmed_request_sha256='abc', resume=True)

    def test_evidence_routes_same_plan_and_run(self):
        self.assertEqual(self.consumer.evidence('task', 'source.csv', 'RunA'), {'verified': True})
        self.bridge.evidence.assert_called_once_with(self.plan, 'RunA')

    def test_planner_rejection_is_not_swallowed(self):
        self.planner.side_effect = ValueError('unsupported task')
        with self.assertRaisesRegex(ValueError, 'unsupported task'):
            self.consumer.execute('unsafe', 'source.csv', 'RunA')
        self.bridge.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
