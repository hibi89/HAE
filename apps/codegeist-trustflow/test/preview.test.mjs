import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPreview } from '../src/core.mjs';

const issue = {
  key: 'PAY-142',
  fields: {
    summary: '긴급 결제 오류 수정',
    description: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '완료조건: 테스트 완료 후 https://example.com/test 확인' }] }] },
    labels: ['incident'],
    status: { name: 'Done' },
    issuetype: { name: 'Bug' }
  }
};

test('triage computes suggestion without any write plan', () => {
  const plan = buildPreview(issue, 'triage');
  assert.equal(plan.work.suggestion.category, 'BUG');
  assert.equal(plan.work.suggestion.suggestedPriority, 'REVIEW_URGENT');
  assert.equal(plan.state, 'READ_ONLY_PREVIEW');
  assert.equal(plan.policy.decision, 'NO_EXECUTION');
  assert.ok(plan.work.steps.every(s => s.sideEffect === 'NONE'));
});

test('breakdown creates three proposals but no real subtasks', () => {
  const plan = buildPreview(issue, 'breakdown');
  assert.equal(plan.work.suggestion.subtasks.length, 3);
  assert.ok(plan.work.suggestion.subtasks.every(t => t.status === 'DRAFT'));
});

test('release gate refuses certification based on plain text links', () => {
  const plan = buildPreview(issue, 'release_guard');
  assert.equal(plan.work.suggestion.releaseDecision, 'REVIEW_REQUIRED');
  assert.equal(plan.work.checks.find(c => c.code === 'TEST_EVIDENCE').outcome, 'LINK_MENTIONED_UNVERIFIED');
  assert.equal(plan.work.checks.find(c => c.code === 'REVIEW_APPROVAL').outcome, 'UNKNOWN_NOT_FETCHED');
});

test('unrecognized natural language is not mapped to arbitrary operation', () => {
  assert.throws(() => buildPreview(issue, 'delete_all'), /UNSUPPORTED_WORKFLOW/);
});

test('issue key validation rejects path injection', () => {
  assert.throws(() => buildPreview({ ...issue, key: '../../evil' }, 'triage'), /INVALID_ISSUE_KEY/);
});

test('missing issue fields are rejected rather than assumed', () => {
  assert.throws(() => buildPreview({ key: 'PAY-142' }, 'triage'), /INVALID_ISSUE_FIELDS/);
});

test('plan hash stable for identical issue snapshot and mode', () => {
  assert.equal(buildPreview(issue, 'triage').planHash, buildPreview(issue, 'triage').planHash);
});

test('plan hash changes when issue summary changes', () => {
  const altered = { ...issue, fields: { ...issue.fields, summary: 'other' } };
  assert.notEqual(buildPreview(issue, 'triage').planHash, buildPreview(altered, 'triage').planHash);
});

test('missing description remains incomplete, not certified', () => {
  const altered = { ...issue, fields: { ...issue.fields, description: null } };
  assert.equal(buildPreview(altered, 'release_guard').work.checks.find(c => c.code === 'ISSUE_DESCRIPTION').outcome, 'MISSING');
});
