import { createHash } from 'node:crypto';

const MODES = new Set(['triage', 'breakdown', 'release_guard']);
const ISSUE_KEY = /^[A-Z][A-Z0-9_]*-[1-9][0-9]*$/;
const MAX_TEXT = 12000;

function hash(value) {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

function adfToText(value, depth = 0) {
  if (depth > 25 || value == null) return '';
  if (typeof value === 'string') return value.slice(0, MAX_TEXT);
  if (Array.isArray(value)) return value.slice(0, 250).map(item => adfToText(item, depth + 1)).join(' ').slice(0, MAX_TEXT);
  if (typeof value !== 'object') return '';
  const own = typeof value.text === 'string' ? value.text : '';
  return (own + ' ' + adfToText(value.content, depth + 1)).trim().slice(0, MAX_TEXT);
}

function normalizeIssue(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new TypeError('INVALID_ISSUE');
  if (typeof raw.key !== 'string' || !ISSUE_KEY.test(raw.key)) throw new TypeError('INVALID_ISSUE_KEY');
  if (!raw.fields || typeof raw.fields !== 'object') throw new TypeError('INVALID_ISSUE_FIELDS');
  const summary = typeof raw.fields.summary === 'string' ? raw.fields.summary.trim().slice(0, 1000) : '';
  const description = adfToText(raw.fields.description).trim();
  const labels = Array.isArray(raw.fields.labels) ? raw.fields.labels.filter(x => typeof x === 'string').slice(0, 30) : [];
  return {
    key: raw.key,
    summary,
    description,
    labels,
    status: String(raw.fields.status?.name || 'UNKNOWN').slice(0, 80),
    issueType: String(raw.fields.issuetype?.name || 'UNKNOWN').slice(0, 80)
  };
}

function triage(issue) {
  const source = (issue.summary + ' ' + issue.description).toLowerCase();
  const category = /버그|오류|실패|bug|crash|exception|error/.test(source) ? 'BUG'
    : /문의|요청|지원|help|support/.test(source) ? 'SUPPORT' : 'GENERAL_TASK';
  const urgent = /긴급|중단|장애|critical|outage|sev[ -]?1|p0/.test(source);
  return {
    suggestion: { category, suggestedPriority: urgent ? 'REVIEW_URGENT' : 'UNDETERMINED', assignee: null },
    steps: [
      { op: 'jira.issue.read', state: 'OBSERVED', sideEffect: 'NONE' },
      { op: 'triage.suggest', state: 'PREVIEW_ONLY', sideEffect: 'NONE' },
      { op: 'human.review', state: 'REQUIRED_BEFORE_WRITE', sideEffect: 'NONE' }
    ],
    checks: [{ code: 'ASSIGNEE_RULE_AVAILABLE', outcome: 'UNKNOWN' }]
  };
}

function breakdown(issue) {
  const source = issue.summary + ' ' + issue.description;
  const hasCriteria = /인수조건|완료조건|수용조건|acceptance criteria|definition of done/i.test(source);
  return {
    suggestion: {
      subtasks: [
        { title: '요구사항과 완료 조건 확인', status: 'DRAFT' },
        { title: '구현·변경 작업 검토', status: 'DRAFT' },
        { title: '테스트 근거·승인 확인', status: 'DRAFT' }
      ]
    },
    steps: [
      { op: 'jira.issue.read', state: 'OBSERVED', sideEffect: 'NONE' },
      { op: 'task.breakdown.preview', state: 'PREVIEW_ONLY', sideEffect: 'NONE' },
      { op: 'human.review', state: 'REQUIRED_BEFORE_WRITE', sideEffect: 'NONE' }
    ],
    checks: [{ code: 'ACCEPTANCE_CRITERIA_EXPLICIT', outcome: hasCriteria ? 'TEXT_MENTIONED_UNVERIFIED' : 'MISSING' }]
  };
}

function releaseGuard(issue) {
  const body = issue.summary + ' ' + issue.description;
  const criteria = /인수조건|완료조건|수용조건|acceptance criteria|definition of done/i.test(body);
  const evidenceLink = /https?:\/\/[a-z0-9.-]+(?:\/[\S]*)?/i.test(body);
  const checks = [
    { code: 'ISSUE_DESCRIPTION', outcome: issue.description ? 'TEXT_PRESENT' : 'MISSING' },
    { code: 'ACCEPTANCE_CRITERIA', outcome: criteria ? 'TEXT_MENTIONED_UNVERIFIED' : 'MISSING' },
    { code: 'TEST_EVIDENCE', outcome: evidenceLink ? 'LINK_MENTIONED_UNVERIFIED' : 'MISSING' },
    { code: 'REVIEW_APPROVAL', outcome: 'UNKNOWN_NOT_FETCHED' }
  ];
  return {
    suggestion: { releaseDecision: 'REVIEW_REQUIRED', reason: 'External proof has not been independently validated' },
    steps: [
      { op: 'jira.issue.read', state: 'OBSERVED', sideEffect: 'NONE' },
      { op: 'evidence.check.preview', state: 'PREVIEW_ONLY', sideEffect: 'NONE' },
      { op: 'human.review', state: 'REQUIRED_BEFORE_RELEASE', sideEffect: 'NONE' }
    ],
    checks
  };
}

export function buildPreview(rawIssue, mode) {
  if (!MODES.has(mode)) throw new TypeError('UNSUPPORTED_WORKFLOW');
  const issue = normalizeIssue(rawIssue);
  const evidence = ['summary', 'description', 'labels', 'status', 'issuetype'].map(field => ({
    ref: 'jira:issue:' + issue.key + ':field:' + field,
    evidenceLevel: 'JIRA_API_FIELD_OBSERVED',
    valueHash: hash(issue[field === 'issuetype' ? 'issueType' : field])
  }));
  const work = mode === 'triage' ? triage(issue) : mode === 'breakdown' ? breakdown(issue) : releaseGuard(issue);
  const canonicalPlan = { schemaVersion: 'hae.codegeist.preview.v1', issueKey: issue.key, mode, work, evidence };
  return {
    ...canonicalPlan,
    planHash: hash(canonicalPlan),
    state: 'READ_ONLY_PREVIEW',
    policy: {
      decision: 'NO_EXECUTION',
      reason: 'READ_ONLY_FIRST_GATE; separate versioned consent and server-side enforcement required for writes',
      permittedEffects: ['JIRA_READ']
    },
    quality: { automatedClaimVerification: 'NOT_RUN', externalEvidenceRetrieval: 'NOT_RUN', modelInference: 'NOT_USED' }
  };
}
