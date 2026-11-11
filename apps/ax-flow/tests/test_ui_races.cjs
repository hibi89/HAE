// Dependency-free simulated DOM regression tests for the shipped HAE browser UI.
// Run: node tests/test_ui_races.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

function element() {
  return {
    value: "", checked: false, disabled: false, hidden: false, textContent: "",
    className: "", children: [], listeners: {},
    addEventListener(type, callback) { this.listeners[type] = callback; },
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) { this.children.splice(this.children.indexOf(child), 1); },
    get firstChild() { return this.children[0] || null; },
    async fire(type) { return this.listeners[type]?.({ key: type }); },
  };
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
function setup() {
  const elements = new Map();
  const get = (selector) => {
    if (!elements.has(selector)) elements.set(selector, element());
    return elements.get(selector);
  };
  const requests = [];
  const context = {
    document: { querySelector: get, createElement: element },
    localStorage: { getItem: () => null, setItem: () => {} },
    navigator: { clipboard: { writeText: async () => {} } },
    fetch(url, options) {
      const item = deferred();
      requests.push({ url, options, ...item });
      return item.promise;
    },
    console, btoa: (value) => Buffer.from(value, "binary").toString("base64"),
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../axflow/static/app.js"), "utf8"), context);
  const respond = (request, data, status = 200) => request.resolve({
    ok: status >= 200 && status < 300, status,
    json: async () => data,
  });
  const flush = async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); };
  return { get, requests, respond, flush };
}
async function testPreviewStaleFailure() {
  const ui = setup();
  const task = ui.get("#task");
  const csv = ui.get("#csv-path");
  task.value = "Import CSV into SQLite";
  csv.value = "first.csv";
  const running = ui.get("#preview").fire("click");
  const request = ui.requests.find((r) => r.url === "/api/preview");
  assert.ok(request, "preview must start");
  csv.value = "second.csv";
  await csv.fire("input");
  request.reject(new Error("old preview failed"));
  await running;
  assert.equal(ui.get("#run").disabled, true);
  assert.equal(ui.get("#message").textContent.includes("old preview failed"), false);
  assert.equal(ui.get("#preview").disabled, false);
}
async function testUploadStaleResponse() {
  const ui = setup();
  const csv = ui.get("#csv-path");
  const file = { name: "first.csv", size: 5, arrayBuffer: async () => Uint8Array.from([105,100,10,49,10]).buffer };
  ui.get("#csv-file").files = [file];
  const running = ui.get("#csv-file").fire("change");
  await ui.flush();
  const request = ui.requests.find((r) => r.url === "/api/upload");
  assert.ok(request, "upload must start");
  csv.value = "manual.csv";
  await csv.fire("input");
  ui.respond(request, { csv_path: "old-upload.csv", size_bytes: 5 });
  await running;
  assert.equal(csv.value, "manual.csv");
  assert.equal(ui.get("#preview").disabled, false);
}
async function testRecentRunsNewestWins() {
  const ui = setup();
  const button = ui.get("#refresh-run-list");
  const first = button.fire("click");
  const second = button.fire("click");
  const runs = ui.requests.filter((r) => r.url.startsWith("/api/runs?"));
  assert.equal(runs.length, 3); // initial page load + two manual refreshes
  ui.respond(runs[2], { runs: [{ run_id: "Gui0123456789ab", status: "completed", steps_recorded: 1 }] });
  await second;
  ui.respond(runs[1], { runs: [] });
  await first;
  assert.equal(ui.get("#recent-runs-list").children.length, 1);
  assert.equal(button.disabled, false);
}
async function testHistoryStaleFailure() {
  const ui = setup();
  const id = ui.get("#history-run-id");
  id.value = "Gui0123456789ab";
  const first = ui.get("#load-run-history").fire("click");
  const request = ui.requests.find((r) => r.url.startsWith("/api/status?"));
  assert.ok(request, "history request must start");
  id.value = "Gui0123456789ac";
  await id.fire("input");
  request.reject(new Error("old history failed"));
  await first;
  assert.equal(ui.get("#history-state").className, "history-state");
  assert.equal(ui.get("#load-run-history").disabled, false);
}
async function testPreviewSupersededByNewRequest() {
  const ui = setup();
  ui.get("#task").value = "Import CSV into SQLite";
  ui.get("#csv-path").value = "data.csv";
  const first = ui.get("#preview").fire("click");
  const second = ui.get("#preview").fire("click");
  const requests = ui.requests.filter((r) => r.url === "/api/preview");
  assert.equal(requests.length, 2);
  requests[0].reject(new Error("old request"));
  await first;
  assert.equal(ui.get("#preview").disabled, true, "older request must not re-enable newer preview");
  requests[1].reject(new Error("current request"));
  await second;
  assert.equal(ui.get("#preview").disabled, false);
}
async function testRunRejectsMissingPreviewToken() {
  const ui = setup();
  ui.get("#task").value = "Import CSV into SQLite";
  ui.get("#csv-path").value = "data.csv";
  const preview = ui.get("#preview").fire("click");
  const request = ui.requests.find((r) => r.url === "/api/preview");
  ui.respond(request, { plan: { steps: [] }, preview_id: "", requires_approval: false, workflow: "csv_lookup" });
  await preview;
  assert.equal(ui.get("#run").disabled, true);
  await ui.get("#run").fire("click");
  assert.equal(ui.requests.filter((r) => r.url === "/api/run").length, 0);
}
async function testExecutionIsSingleFlightAndNeedsFreshPreview() {
  const ui = setup();
  const task = ui.get("#task");
  const csv = ui.get("#csv-path");
  task.value = "Import CSV into SQLite";
  csv.value = "data.csv";
  const preview = ui.get("#preview").fire("click");
  const previewRequest = ui.requests.find((r) => r.url === "/api/preview");
  ui.respond(previewRequest, {
    plan: { steps: [] }, engine_backend: { name: "HAE" },
    preview_id: "preview-test", requires_approval: true,
    workflow: "csv_to_sqlite", input: { row_count: 1, headers: ["id"], size_bytes: 5 },
  });
  await preview;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  const first = ui.get("#run").fire("click");
  const second = ui.get("#run").fire("click");
  assert.equal(ui.requests.filter((r) => r.url === "/api/run").length, 1, "only one SQLite run may be submitted");
  const submitted = JSON.parse(ui.requests.find((r) => r.url === "/api/run").options.body);
  assert.equal(submitted.task, "Import CSV into SQLite");
  assert.equal(submitted.csv_path, "data.csv");
  assert.equal(submitted.preview_id, "preview-test");
  assert.equal(submitted.approve_writes, true);
  assert.equal(ui.get("#run").disabled, true);
  assert.equal(ui.get("#preview").disabled, true);
  csv.value = "changed-while-running.csv";
  await csv.fire("input");
  assert.equal(ui.get("#preview").disabled, true, "input changes must preserve execution lock");
  await ui.get("#preview").fire("click");
  assert.equal(ui.requests.filter((r) => r.url === "/api/preview").length, 1, "execution blocks new preview");
  const request = ui.requests.find((r) => r.url === "/api/run");
  ui.respond(request, { error: "synthetic failure" }, 500);
  await Promise.all([first, second]);
  assert.equal(ui.get("#run").disabled, true, "new preview required after run attempt");
  assert.equal(ui.get("#approval").checked, false);
}
async function testFailedDurableRunCanRetryWithSamePreviewAfterReapproval() {
  const ui = setup();
  ui.get("#task").value = "Import CSV into SQLite";
  ui.get("#csv-path").value = "data.csv";
  const preview = ui.get("#preview").fire("click");
  const previewRequest = ui.requests.find((r) => r.url === "/api/preview");
  ui.respond(previewRequest, {
    plan: { steps: [] }, engine_backend: { name: "Lightning Azent" },
    preview_id: "approved-preview", requires_approval: true,
    workflow: "csv_to_sqlite", input: { row_count: 1, headers: ["id"], size_bytes: 5 },
  });
  await preview;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  const first = ui.get("#run").fire("click");
  const firstRun = ui.requests.find((r) => r.url === "/api/run");
  ui.respond(firstRun, {
    error: "Lightning Azent execution failed: StepTimeout",
    error_type: "LightningExecutionError", run_id: "Gui0123456789ab",
    status: { run_id: "Gui0123456789ab", status: "failed", steps_recorded: 1, error_type: "StepTimeout" },
  }, 409);
  await first;
  assert.equal(ui.get("#run").disabled, true, "a failed write still requires fresh explicit approval");
  assert.equal(ui.get("#approval").checked, false);
  assert.ok(ui.get("#message").textContent.includes("다시 시도"));
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  assert.equal(ui.get("#run").disabled, false, "same approved preview permits retry after reapproval");
  const second = ui.get("#run").fire("click");
  const submissions = ui.requests.filter((r) => r.url === "/api/run");
  assert.equal(submissions.length, 2);
  assert.equal(JSON.parse(submissions[1].options.body).preview_id, "approved-preview");
  assert.equal(JSON.parse(submissions[1].options.body).approve_writes, true);
  ui.respond(submissions[1], {
    run_id: "Gui0123456789ab", result: { imported_rows: 1 },
    status: { run_id: "Gui0123456789ab", status: "completed", steps_recorded: 1 },
    backend: { name: "Lightning Azent" }, workflow_status: "partial",
  });
  await second;
  assert.equal(ui.get("#run").disabled, true, "successful execution consumes the UI preview");
}
async function testInvalidatedPreviewNeverRetried() {
  const ui = setup();
  ui.get("#task").value = "Import CSV into SQLite";
  ui.get("#csv-path").value = "data.csv";
  const preview = ui.get("#preview").fire("click");
  ui.respond(ui.requests.find((r) => r.url === "/api/preview"), {
    plan: { steps: [] }, preview_id: "invalidated-preview", requires_approval: true,
    workflow: "csv_to_sqlite", input: { row_count: 1, headers: ["id"], size_bytes: 5 },
  });
  await preview;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  const run = ui.get("#run").fire("click");
  ui.respond(ui.requests.find((r) => r.url === "/api/run"), {
    error: "CSV changed after preview; preview it again before execution",
    error_type: "RequestError", run_id: "Gui0123456789ab",
    status: { run_id: "Gui0123456789ab", status: "failed" },
  }, 409);
  await run;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  assert.equal(ui.get("#run").disabled, true, "input invalidation must require a new preview");
}
async function testResumePreviewRequiresMatchingRunAndReapproval() {
  const ui = setup();
  ui.get("#task").value = "Import CSV into SQLite";
  ui.get("#csv-path").value = "data.csv";
  ui.get("#history-run-id").value = "Gui0123456789ab";
  const pending = ui.get("#prepare-resume").fire("click");
  const req = ui.requests.find((r) => r.url === "/api/preview");
  assert.ok(req, "resume preview must reach the preview API, not execute writes");
  assert.equal(JSON.parse(req.options.body).resume_run_id, "Gui0123456789ab");
  assert.equal(ui.requests.filter((r) => r.url === "/api/run").length, 0);
  ui.respond(req, {
    plan: { steps: [] }, engine_backend: { name: "Lightning Azent" },
    preview_id: "restart-recovery-preview", resumes_run_id: "Gui0123456789ab",
    requires_approval: true, workflow: "csv_to_sqlite",
    input: { row_count: 2, headers: ["id"], size_bytes: 6 },
  });
  await pending;
  assert.equal(ui.get("#run").disabled, true, "recovery cannot reuse a prior write approval");
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  assert.equal(ui.get("#run").disabled, false, "fresh approval enables resumed run");
}
async function testResumePreviewRejectsInvalidRunIdWithoutRequest() {
  const ui = setup();
  ui.get("#history-run-id").value = "bad-run-id";
  await ui.get("#prepare-resume").fire("click");
  assert.equal(ui.requests.filter((r) => r.url === "/api/preview").length, 0);
  assert.equal(ui.requests.filter((r) => r.url === "/api/run").length, 0);
}
async function testLiveReceiptRendersRedactedLaEvents() {
  const ui = setup();
  ui.get("#task").value = "Import CSV into SQLite";
  ui.get("#csv-path").value = "data.csv";
  const preview = ui.get("#preview").fire("click");
  ui.respond(ui.requests.find((r) => r.url === "/api/preview"), {
    plan: { steps: [] }, engine_backend: { name: "Lightning Azent" },
    preview_id: "approved", requires_approval: true, workflow: "csv_to_sqlite",
    input: { row_count: 1, headers: ["id"], size_bytes: 4 },
  });
  await preview;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  const executing = ui.get("#run").fire("click");
  ui.respond(ui.requests.find((r) => r.url === "/api/run"), {
    run_id: "Gui0123456789ab",
    status: { run_id: "Gui0123456789ab", status: "completed", steps_recorded: 2 },
    result: { imported_rows: 1 }, backend: { name: "Lightning Azent" },
    audit: { events: [{ event_type: "step_completed", occurred_at: "2026-10-29T05:00:00Z",
      details: { step_id: "csv_read", secret: "MUST_NOT_DISPLAY" } }] },
    sovia_audit: { available: false }, dbvora: { available: false }, workflow_status: "partial",
  });
  await executing;
  assert.equal(ui.get("#la-audit-details").hidden, false);
  assert.equal(ui.get("#la-audit-events").children.length, 1);
  const rendered = ui.get("#la-audit-events").children[0].textContent;
  assert.ok(rendered.includes("step_completed"));
  assert.ok(rendered.includes("csv_read"));
  assert.equal(rendered.includes("MUST_NOT_DISPLAY"), false, "raw audit details must never render");
}
async function testHistoryRestoresLaAuditWithoutSovia() {
  const ui = setup();
  ui.get("#history-run-id").value = "Gui0123456789ab";
  const loading = ui.get("#load-run-history").fire("click");
  const status = ui.requests.find((r) => r.url.startsWith("/api/status?"));
  ui.respond(status, {
    run_id: "Gui0123456789ab", status: "completed", steps_recorded: 2, integration: {},
  });
  await ui.flush();
  await new Promise((resolve) => setImmediate(resolve));
  const sovia = ui.requests.find((r) => r.url.startsWith("/api/audit?"));
  assert.ok(sovia);
  ui.respond(sovia, { error: "SOVIA unavailable" }, 404);
  await ui.flush();
  await new Promise((resolve) => setImmediate(resolve));
  const la = ui.requests.find((r) => r.url.startsWith("/api/la-audit?"));
  assert.ok(la, "LA audit remains available when SOVIA is missing");
  ui.respond(la, {
    run_id: "Gui0123456789ab", total_events: 3, approval_count: 1,
    events: [{ event_type: "run_started", occurred_at: "2026-10-29T05:00:00Z" }],
  });
  await loading;
  assert.equal(ui.get("#la-audit-details").hidden, false);
  assert.equal(ui.get("#la-audit-events").children.length, 1);
  assert.ok(ui.get("#la-audit-result").textContent.includes("이벤트 3건"));
}
async function testAssetProofManualOnlyAndLatestResponseWins() {
  const ui = setup();
  assert.equal(ui.requests.filter((r) => r.url === "/api/dbvora-asset").length, 0,
    "asset attestation must never run automatically on page load");
  const button = ui.get("#verify-dbvora-asset");
  const first = button.fire("click");
  const second = button.fire("click");
  const calls = ui.requests.filter((r) => r.url === "/api/dbvora-asset");
  assert.equal(calls.length, 2);
  ui.respond(calls[1], { available: false, error_code: "ASSET_ATTESTATION_HOLD" });
  await second;
  ui.respond(calls[0], { available: true, provider_protocol_verified: true,
    source_sha256: "a".repeat(64), table_count: 2 });
  await first;
  assert.match(ui.get("#dbvora-asset-attestation").textContent, /검증 보류/);
  assert.equal(button.disabled, false);
}

async function testDbvoraRefreshCancelsPendingAssetProof() {
  const ui = setup();
  const verify = ui.get("#verify-dbvora-asset");
  const pending = verify.fire("click");
  const proof = ui.requests.find((r) => r.url === "/api/dbvora-asset");
  assert.ok(proof);
  const refresh = ui.get("#refresh-dbvora").fire("click");
  const db = ui.requests.filter((r) => r.url === "/api/dbvora").at(-1);
  ui.respond(db, { available: false, error_code: "NOT_CONFIGURED" });
  await refresh;
  assert.equal(verify.disabled, false, "DBVORA refresh must unlock canceled proof button");
  ui.respond(proof, {
    available: true, provider_protocol_verified: true,
    source_sha256: "a".repeat(64), table_count: 2,
  });
  await pending;
  assert.match(ui.get("#dbvora-asset-attestation").textContent, /검증 미실행/);
}

async function testRegistryRequiresManualReviewConsentAndNoDuplicateSubmission() {
  const ui = setup();
  const button = ui.get("#register-dbvora-asset");
  assert.equal(button.disabled, true, "registration must not be possible on page load");
  assert.equal(ui.requests.filter((r) => r.url === "/api/asset-registry/register").length, 0);
  const verify = ui.get("#verify-dbvora-asset").fire("click");
  const review = ui.requests.find((r) => r.url === "/api/dbvora-asset");
  ui.respond(review, {available: true, provider_protocol_verified: true,
    source_sha256: "a".repeat(64), table_count: 2});
  await verify;
  assert.equal(button.disabled, true, "successful review alone does not approve persistence");
  ui.get("#asset-registry-consent").checked = true;
  await ui.get("#asset-registry-consent").fire("change");
  assert.equal(button.disabled, false);
  const first = button.fire("click");
  const second = button.fire("click");
  const requests = ui.requests.filter((r) => r.url === "/api/asset-registry/register");
  assert.equal(requests.length, 1, "registration must be single-flight");
  assert.equal(JSON.parse(requests[0].options.body).expected_sha256, "a".repeat(64));
  ui.respond(requests[0], {status: "REGISTERED", release_gate: "HOLD"});
  await Promise.all([first, second]);
  assert.match(ui.get("#asset-registry-status").textContent, /등록 완료/);
  assert.equal(ui.get("#asset-registry-consent").checked, false);
  assert.equal(button.disabled, true);
}
async function testRegistryReviewClearsAfterMapChange() {
  const ui = setup();
  const verify = ui.get("#verify-dbvora-asset").fire("click");
  const review = ui.requests.find((r) => r.url === "/api/dbvora-asset");
  ui.respond(review, {available: true, provider_protocol_verified: true,
    source_sha256: "a".repeat(64), table_count: 2});
  await verify;
  ui.get("#asset-registry-consent").checked = true;
  await ui.get("#asset-registry-consent").fire("change");
  assert.equal(ui.get("#register-dbvora-asset").disabled, false);
  const refresh = ui.get("#refresh-dbvora").fire("click");
  const network = ui.requests.filter((r) => r.url === "/api/dbvora").at(-1);
  ui.respond(network, {available:false, error_code:"UNAVAILABLE"});
  await refresh;
  assert.equal(ui.get("#register-dbvora-asset").disabled, true);
  await ui.get("#register-dbvora-asset").fire("click");
  assert.equal(ui.requests.filter((r) => r.url === "/api/asset-registry/register").length, 0);
}
async function testPresetSelectionNeedsNewReviewAndApproval() {
  const ui = setup();
  ui.get("#csv-path").value = "offers.csv";
  ui.get("#workflow-preset").value = "filter";
  await ui.get("#workflow-preset").fire("change");
  assert.match(ui.get("#task").value, /amount > 100/);
  assert.equal(ui.get("#run").disabled, true);
  const preview = ui.get("#preview").fire("click");
  const request = ui.requests.find((r) => r.url === "/api/preview");
  assert.ok(request);
  ui.respond(request, { plan: {steps: []}, preview_id:"0123456789abcdef0123456789abcdef",
    requires_approval:true, workflow:"csv_filtered_import", engine_backend:{name:"HAE"} });
  await preview;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  assert.equal(ui.get("#run").disabled, false);
  ui.get("#workflow-preset").value = "normalize";
  await ui.get("#workflow-preset").fire("change");
  assert.match(ui.get("#task").value, /Trim whitespace/);
  assert.equal(ui.get("#run").disabled, true, "changing preset must invalidate old preview");
  assert.equal(ui.get("#approval").checked, false, "changing preset must revoke old approval");
}

async function testPresetCannotChangeTaskDuringExecution() {
  const ui = setup();
  ui.get("#csv-path").value = "offers.csv";
  ui.get("#workflow-preset").value = "full";
  await ui.get("#workflow-preset").fire("change");
  const preview = ui.get("#preview").fire("click");
  const request = ui.requests.find((r) => r.url === "/api/preview");
  ui.respond(request, {plan:{steps:[]},preview_id:"approved-preview",requires_approval:true,
    workflow:"csv_to_sqlite",engine_backend:{name:"Lightning Azent"}});
  await preview;
  ui.get("#approval").checked = true;
  await ui.get("#approval").fire("change");
  const running = ui.get("#run").fire("click");
  const before = ui.get("#task").value;
  ui.get("#workflow-preset").value = "lookup";
  await ui.get("#workflow-preset").fire("change");
  assert.equal(ui.get("#task").value, before);
  const call = ui.requests.find((r) => r.url === "/api/run");
  ui.respond(call, {error:"synthetic controlled stop"}, 409);
  await running;
}

async function testSavedWorkflowRequiresPreviewAndOwnerSaveConsent() {
  const ui = setup();
  const button = ui.get("#save-workflow");
  assert.equal(button.disabled, true);
  assert.equal(ui.requests.filter(r => r.url === "/api/workflows/save").length, 0);
  ui.get("#task").value = "Import this CSV into local SQLite";
  ui.get("#csv-path").value = "data.csv";
  const preview = ui.get("#preview").fire("click");
  const request = ui.requests.find(r => r.url === "/api/preview");
  ui.respond(request, {plan:{steps:[]},preview_id:"0123456789abcdef0123456789abcdef",
    requires_approval:true,workflow:"csv_to_sqlite",engine_backend:{name:"HAE"}});
  await preview;
  assert.equal(button.disabled, true);
  ui.get("#workflow-save-consent").checked = true;
  await ui.get("#workflow-save-consent").fire("change");
  assert.equal(button.disabled, false);
  const saving = button.fire("click");
  await button.fire("click");
  const calls = ui.requests.filter(r => r.url === "/api/workflows/save");
  assert.equal(calls.length, 1);
  assert.equal(JSON.parse(calls[0].options.body).approve_workflow_save, true);
  ui.respond(calls[0], {status:"SAVED",needs_new_preview:true});
  await saving;
  assert.equal(button.disabled, true);
  assert.equal(ui.get("#workflow-save-consent").checked, false);
  assert.match(ui.get("#workflow-catalog-status").textContent, /저장 완료/);
}

async function testSavedWorkflowReloadRequiresFreshPreview() {
  const ui = setup();
  const req = ui.requests.find(r => r.url === "/api/workflows");
  assert.ok(req);
  ui.respond(req, {available:true,recipe_count:1,recipes:[
    {recipe_id:"abcdef012345abcdef012345",workflow:"csv_to_sqlite"}
  ]});
  await ui.flush();
  await new Promise(resolve => setImmediate(resolve));
  const entries = ui.get("#saved-workflows").children;
  assert.equal(entries.length, 1);
  const recall = entries[0].children[0].fire("click");
  const load = ui.requests.find(r => r.url.startsWith("/api/workflows/load?"));
  ui.respond(load, {task:"이 CSV 파일을 로컬 SQLite에 저장해줘",
    csv_path:"data.csv",needs_new_preview:true,write_approved:false});
  await recall;
  assert.equal(ui.get("#csv-path").value, "data.csv");
  assert.equal(ui.get("#run").disabled, true);
  assert.equal(ui.get("#approval").checked, false);
  assert.match(ui.get("#message").textContent, /미리보기/);
}
async function testSavedWorkflowLateReplyDoesNotOverwriteManualEdit() {
  const ui = setup();
  const list = ui.requests.find((r) => r.url === "/api/workflows");
  ui.respond(list, {available:true, recipe_count:1,
    recipes:[{recipe_id:"a".repeat(24),workflow:"csv_to_sqlite"}]});
  await ui.flush();
  await new Promise((resolve) => setImmediate(resolve));
  const item = ui.get("#saved-workflows").children[0].children[0];
  const pending = item.fire("click");
  const request = ui.requests.find((r) => r.url.startsWith("/api/workflows/load?"));
  assert.ok(request);
  ui.get("#task").value = "My newer manual CSV import";
  await ui.get("#task").fire("input");
  ui.get("#csv-path").value = "manual.csv";
  await ui.get("#csv-path").fire("input");
  ui.respond(request, {task:"obsolete saved task", csv_path:"obsolete.csv",
    needs_new_preview:true, write_approved:false});
  await pending;
  assert.equal(ui.get("#task").value, "My newer manual CSV import");
  assert.equal(ui.get("#csv-path").value, "manual.csv");
  assert.equal(ui.get("#run").disabled, true);
  assert.equal(ui.requests.filter(r => r.url === "/api/run").length, 0);
}

async function testSavedWorkflowNewestClickWinsOutOfOrderReplies() {
  const ui = setup();
  const list = ui.requests.find((r) => r.url === "/api/workflows");
  ui.respond(list, {available:true, recipe_count:2,
    recipes:[
      {recipe_id:"a".repeat(24),workflow:"csv_to_sqlite"},
      {recipe_id:"b".repeat(24),workflow:"csv_filtered_import"},
    ]});
  await ui.flush();
  await new Promise((resolve) => setImmediate(resolve));
  const children = ui.get("#saved-workflows").children;
  assert.equal(children.length, 2);
  const old = children[0].children[0].fire("click");
  const newest = children[1].children[0].fire("click");
  const requests = ui.requests.filter(r => r.url.startsWith("/api/workflows/load?"));
  assert.equal(requests.length, 2);
  ui.respond(requests[1], {task:"newest reviewed recipe", csv_path:"current.csv",
    needs_new_preview:true, write_approved:false});
  await newest;
  ui.respond(requests[0], {task:"obsolete old recipe", csv_path:"obsolete.csv",
    needs_new_preview:true, write_approved:false});
  await old;
  assert.equal(ui.get("#task").value, "newest reviewed recipe");
  assert.equal(ui.get("#csv-path").value, "current.csv");
  assert.equal(ui.get("#run").disabled, true);
  assert.equal(ui.get("#approval").checked, false);
}

async function testDbvoraNewestResponseWins() {
  const ui = setup();
  const button = ui.get("#refresh-dbvora");
  const first = button.fire("click");
  const second = button.fire("click");
  const requests = ui.requests.filter((r) => r.url === "/api/dbvora");
  assert.equal(requests.length, 3); // initial load and two refreshes
  ui.respond(requests[2], { available: false, error_code: "NOT_CONFIGURED" });
  await second;
  ui.respond(requests[1], { available: false, error_code: "UNAVAILABLE" });
  await first;
  assert.equal(ui.get("#dbvora-status").textContent, "DBVORA 미설정");
  assert.equal(button.disabled, false);
}
(async () => {
  await testRunRejectsMissingPreviewToken();
  await testDbvoraNewestResponseWins();
  await testSavedWorkflowRequiresPreviewAndOwnerSaveConsent();
  await testSavedWorkflowReloadRequiresFreshPreview();
  await testSavedWorkflowLateReplyDoesNotOverwriteManualEdit();
  await testSavedWorkflowNewestClickWinsOutOfOrderReplies();
  await testPresetSelectionNeedsNewReviewAndApproval();
  await testPresetCannotChangeTaskDuringExecution();
  await testAssetProofManualOnlyAndLatestResponseWins();
  await testRegistryRequiresManualReviewConsentAndNoDuplicateSubmission();
  await testRegistryReviewClearsAfterMapChange();
  await testDbvoraRefreshCancelsPendingAssetProof();
  await testPreviewStaleFailure();
  await testExecutionIsSingleFlightAndNeedsFreshPreview();
  await testHistoryStaleFailure();
  await testPreviewSupersededByNewRequest();
  await testUploadStaleResponse();
  await testRecentRunsNewestWins();
  await testFailedDurableRunCanRetryWithSamePreviewAfterReapproval();
  await testInvalidatedPreviewNeverRetried();
  await testResumePreviewRequiresMatchingRunAndReapproval();
  await testResumePreviewRejectsInvalidRunIdWithoutRequest();
  await testLiveReceiptRendersRedactedLaEvents();
  await testHistoryRestoresLaAuditWithoutSovia();
  console.log("HAE simulated UI race tests: 24 PASS");
})().catch((error) => { console.error(error); process.exitCode = 1; });
