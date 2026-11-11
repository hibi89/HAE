"""HAE bridge safety tests with the real contract and a fake execution boundary.

The mock is limited to the LAExecutor side effects. No customer data or network.
"""
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from lightning_azent.contract import capabilities
from lightning_azent.engine import ApprovalRequired, PlanError
from lightning_azent.hae_bridge import HAEBridge

FIXTURES = REPO_ROOT / 'docs' / 'lightning-azent' / 'fixtures'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


class FakeExecutor:
    def __init__(self):
        self.calls = []
        self.caps = capabilities()
        self.step_count = 5
        self.approval_receipts = []

    def capabilities(self):
        return self.caps

    def execute(self, plan, run_id, *, approve_writes):
        self.calls.append(('execute', run_id, approve_writes))
        return {'ok': True}

    def resume(self, plan, run_id, *, approve_writes):
        self.calls.append(('resume', run_id, approve_writes))
        return {'resumed': True}

    def verify_receipts(self, plan, run_id):
        self.calls.append(('verify', run_id))
        return {'run_id': run_id, 'verified': True}

    def status(self, run_id):
        return {'run_id': run_id, 'status': 'completed',
                'plan_sha256': self.valid_sha, 'steps_recorded': self.step_count,
                'step_outcomes': {'completed': self.step_count - 1, 'skipped': 1,
                                  'failed': 0, 'running': 0}, 'error_type': None}

    def audit(self, run_id):
        return {
            'run_id': run_id, 'plan_sha256': self.valid_sha,
            'events': [
                {'event_type': 'run_started', 'occurred_at': '2026-11-12T00:00:00Z', 'details': {}},
                {'event_type': 'run_completed', 'occurred_at': '2026-11-12T00:00:01Z',
                 'details': {'step_count': self.step_count, 'output_sha256': 'a' * 64}},
            ],
            'approval_receipts': self.approval_receipts,
        }


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.executor = FakeExecutor()
        self.bridge = HAEBridge(self.executor)
        self.read = fixture('conditional-route.json')
        self.write = fixture('csv-filter-import.json')
        self.executor.valid_sha = self.bridge.review(self.read, 'RunA').plan_sha256

    def test_review_redacts_step_values_and_has_no_execution(self):
        view = self.bridge.review(self.read, 'Run_1').public_view()
        self.assertEqual(view['bridge_version'], 'hae.la-bridge.v0')
        self.assertFalse(view['requires_write_approval'])
        self.assertFalse(view['executed'])
        self.assertNotIn('sample', str(view))
        self.assertEqual(self.executor.calls, [])

    def test_readonly_exec_requires_synthetic_opt_in(self):
        with self.assertRaises(PlanError):
            self.bridge.execute(self.read, 'ReadOnly')
        self.assertEqual(self.bridge.execute(self.read, 'ReadOnly', synthetic=True), {'ok': True})
        self.assertEqual(self.executor.calls, [('execute', 'ReadOnly', False)])

    def test_missing_confirmation_denies_write(self):
        with self.assertRaises(ApprovalRequired):
            self.bridge.execute(self.write, 'Write', synthetic=True)
        self.assertEqual(self.executor.calls, [])

    def test_bool_alone_denies_write(self):
        with self.assertRaises(ApprovalRequired):
            self.bridge.execute(self.write, 'Write', synthetic=True, owner_confirmed=True)
        self.assertEqual(self.executor.calls, [])

    def test_digest_binds_write_to_run_id(self):
        digest = self.bridge.review(self.write, 'RunA').request_sha256
        self.assertEqual(self.bridge.execute(self.write, 'RunA', synthetic=True,
            owner_confirmed=True, confirmed_request_sha256=digest), {'ok': True})
        with self.assertRaises(ApprovalRequired):
            self.bridge.execute(self.write, 'RunB', synthetic=True,
                owner_confirmed=True, confirmed_request_sha256=digest)
        self.assertEqual(self.executor.calls, [('execute', 'RunA', True)])

    def test_changed_valid_plan_invalidates_confirmation(self):
        digest = self.bridge.review(self.write, 'RunA').request_sha256
        changed = deepcopy(self.write)
        changed['steps'][0]['path'] = 'orders_alt.csv'
        with self.assertRaises(ApprovalRequired):
            self.bridge.execute(changed, 'RunA', synthetic=True,
                owner_confirmed=True, confirmed_request_sha256=digest)

    def test_native_version_changes_confirmation_scope(self):
        native = deepcopy(self.write)
        native['version'] = 'azent.ir.v0'
        self.assertNotEqual(self.bridge.review(self.write, 'RunA').request_sha256,
                            self.bridge.review(native, 'RunA').request_sha256)
        self.assertEqual(native['version'], 'azent.ir.v0')

    def test_readonly_rejects_spurious_write_confirmation(self):
        with self.assertRaises(PlanError):
            self.bridge.execute(self.read, 'RunA', synthetic=True,
                owner_confirmed=True, confirmed_request_sha256='0' * 64)

    def test_bad_run_id_fails_before_executor(self):
        with self.assertRaises(PlanError):
            self.bridge.review(self.write, 'unsafe/run')
        self.assertEqual(self.executor.calls, [])

    def test_scheduled_plan_uses_separate_scheduler(self):
        plan = deepcopy(self.read)
        plan['trigger'] = {'type': 'interval', 'seconds': 60}
        with self.assertRaises(PlanError):
            self.bridge.review(plan, 'RunA')

    def test_runtime_api_and_scope_are_pinned(self):
        for key, bad in [('api_version', 'azent.api.v99'),
                         ('audit_feed', 'raw.v1'),
                         ('external_connectors', ['gmail']),
                         ('scope', 'real-data')]:
            with self.subTest(key=key):
                self.executor.caps[key] = bad
                with self.assertRaises(PlanError):
                    self.bridge.review(self.read, 'RunA')
                self.executor.caps = capabilities()

    def test_resume_reuses_exact_confirmation(self):
        digest = self.bridge.review(self.write, 'RunA').request_sha256
        self.assertEqual(self.bridge.execute(self.write, 'RunA', synthetic=True,
            owner_confirmed=True, confirmed_request_sha256=digest, resume=True), {'resumed': True})
        self.assertEqual(self.executor.calls, [('resume', 'RunA', True)])

    def test_readonly_verified_evidence(self):
        result = self.bridge.evidence(self.read, 'RunA')
        self.assertTrue(result['verified'])
        self.assertFalse(result['independent_sovia_audit'])
        self.assertEqual(self.executor.calls, [('verify', 'RunA')])

    def test_unverified_receipts_fail_closed(self):
        self.executor.verify_receipts = lambda *args: {'verified': False}
        with self.assertRaises(PlanError):
            self.bridge.evidence(self.read, 'RunA')

    def test_incomplete_states_cannot_claim_verified_evidence(self):
        for state in ('running', 'failed', 'pending', None):
            with self.subTest(state=state):
                self.executor.status = lambda run_id: {'run_id': run_id, 'status': state}
                with self.assertRaisesRegex(PlanError, 'not completed'):
                    self.bridge.evidence(self.read, 'RunA')

    def test_missing_or_wrong_run_status_fails_closed(self):
        for status in (None, {'status': 'completed'},
                       {'run_id': 'OtherRun', 'status': 'completed'}):
            with self.subTest(status=status):
                self.executor.status = lambda run_id: status
                with self.assertRaises(PlanError):
                    self.bridge.evidence(self.read, 'RunA')

    def test_malformed_receipt_verification_fails_closed(self):
        for proof in (None, True, 'verified', {}):
            with self.subTest(proof=proof):
                self.executor.verify_receipts = lambda *args: proof
                with self.assertRaises(PlanError):
                    self.bridge.evidence(self.read, 'RunA')

    def test_mismatched_persisted_plan_digest_is_not_verified(self):
        real_status = self.executor.status
        self.executor.status = lambda run_id: {
            **real_status(run_id), 'plan_sha256': '0'*64}
        with self.assertRaisesRegex(PlanError, 'status plan'):
            self.bridge.evidence(self.read, 'RunA')

    def test_missing_or_partially_checkpointed_step_records_are_denied(self):
        real_status = self.executor.status
        for n in (0, 3, 6, None, True):
            with self.subTest(n=n):
                self.executor.status = lambda run_id, n=n: {
                    **real_status(run_id), 'steps_recorded': n}
                with self.assertRaisesRegex(PlanError, 'step ledger'):
                    self.bridge.evidence(self.read, 'RunA')

    def test_failed_running_or_malformed_step_counts_are_denied(self):
        real_status = self.executor.status
        for bad in ({'completed': 3, 'skipped': 1, 'failed': 1, 'running': 0},
                    {'completed': 4, 'skipped': 0, 'failed': 0, 'running': 1},
                    {'completed': 5, 'skipped': -1, 'failed': 0, 'running': 1},
                    {'completed': 4, 'skipped': '1', 'failed': 0, 'running': 0},
                    None):
            with self.subTest(bad=bad):
                self.executor.status = lambda run_id, bad=bad: {
                    **real_status(run_id), 'step_outcomes': bad}
                with self.assertRaisesRegex(PlanError, 'step ledger'):
                    self.bridge.evidence(self.read, 'RunA')


    def test_wrong_run_receipt_is_rejected(self):
        self.executor.verify_receipts = lambda *args: {'verified': True, 'run_id': 'other'}
        with self.assertRaisesRegex(PlanError, 'bind this run'):
            self.bridge.evidence(self.read, 'RunA')

    def test_wrong_run_audit_and_absent_completion_are_rejected(self):
        real = self.executor.audit('RunA')
        cases = [None, {}, {**real, 'run_id': 'other'},
                 {**real, 'plan_sha256': '0' * 64},
                 {**real, 'events': []},
                 {**real, 'events': [real['events'][0]]},
                 {**real, 'events': real['events'] + [
                     {'event_type': 'run_failed', 'occurred_at': 'later', 'details': {}}]}]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.executor.audit = lambda _, candidate=candidate: candidate
                with self.assertRaises(PlanError):
                    self.bridge.evidence(self.read, 'RunA')

    def test_corrupt_completion_metadata_refused(self):
        original = self.executor.audit('RunA')
        cases = [{'step_count': 0, 'output_sha256': 'a'*64},
                 {'step_count': True, 'output_sha256': 'a'*64},
                 {'step_count': 5, 'output_sha256': 'invalid'},
                 {'step_count': 5, 'output_sha256': 'g'*64}]
        for bad in cases:
            with self.subTest(bad=bad):
                changed = deepcopy(original)
                changed['events'][-1]['details'] = bad
                self.executor.audit = lambda _, changed=changed: changed
                with self.assertRaisesRegex(PlanError, 'completion event'):
                    self.bridge.evidence(self.read, 'RunA')

    def test_malformed_event_fails_closed(self):
        original = self.executor.audit('RunA')
        for event in (None, {}, {'event_type': 'run_completed', 'details': []},
                      {'event_type': 'run_completed', 'occurred_at': None, 'details': {}}):
            with self.subTest(event=event):
                candidate = deepcopy(original)
                candidate['events'][-1] = event
                self.executor.audit = lambda _, candidate=candidate: candidate
                with self.assertRaisesRegex(PlanError, 'audit event'):
                    self.bridge.evidence(self.read, 'RunA')

    def test_readonly_unexpected_approval_refused(self):
        candidate = self.executor.audit('RunA')
        candidate['approval_receipts'] = [{'method': 'explicit-write-approval'}]
        self.executor.audit = lambda _: candidate
        with self.assertRaisesRegex(PlanError, 'approval receipts'):
            self.bridge.evidence(self.read, 'RunA')

    def test_write_receipt_scope_and_method_verified(self):
        self.executor.valid_sha = self.bridge.review(self.write, 'RunA').plan_sha256
        self.executor.step_count = len(self.write['steps'])
        receipt = {
            'method': 'explicit-write-approval',
            'approved_at': '2026-11-12T00:00:00Z',
            'scope': {'plan_sha256': self.executor.valid_sha,
                      'write_steps': [{'step_id': x['id'], 'operation': x['op']}
                                      for x in self.write['steps']
                                      if x['op'] in ('sqlite_put', 'sqlite_import_csv')]}}
        self.executor.approval_receipts = [deepcopy(receipt)]
        self.assertTrue(self.bridge.evidence(self.write, 'RunA')['verified'])
        cases = [[], [dict(receipt, method='silent')],
                 [dict(receipt, scope={**receipt['scope'], 'plan_sha256': '0'*64})],
                 [dict(receipt, scope={**receipt['scope'], 'write_steps': []})]]
        for bad in cases:
            with self.subTest(bad=bad):
                self.executor.approval_receipts = bad
                with self.assertRaisesRegex(PlanError, 'approval receipt'):
                    self.bridge.evidence(self.write, 'RunA')

    def test_completed_error_type_is_not_success(self):
        original = self.executor.status
        self.executor.status = lambda rid: {**original(rid), 'error_type': 'StepTimeout'}
        with self.assertRaisesRegex(PlanError, 'retains an error'):
            self.bridge.evidence(self.read, 'RunA')

    def test_changed_status_during_audit_cannot_claim_success(self):
        original = self.executor.status
        self.executor.audited = False
        self.executor.status = lambda rid: {**original(rid),
            'steps_recorded': self.executor.step_count + int(self.executor.audited)}
        audit = self.executor.audit
        def changed(rid):
            self.executor.audited = True
            return audit(rid)
        self.executor.audit = changed
        with self.assertRaisesRegex(PlanError, 'changed during audit'):
            self.bridge.evidence(self.read, 'RunA')



if __name__ == '__main__':
    unittest.main()
