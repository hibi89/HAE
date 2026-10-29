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
  const request = ui.requests.find((r) => r.url === "/api/run");
  ui.respond(request, { error: "synthetic failure" }, 500);
  await Promise.all([first, second]);
  assert.equal(ui.get("#run").disabled, true, "new preview required after run attempt");
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
  await testDbvoraNewestResponseWins();
  await testPreviewStaleFailure();
  await testExecutionIsSingleFlightAndNeedsFreshPreview();
  await testHistoryStaleFailure();
  await testPreviewSupersededByNewRequest();
  await testUploadStaleResponse();
  await testRecentRunsNewestWins();
  console.log("HAE simulated UI race tests: 7 PASS");
})().catch((error) => { console.error(error); process.exitCode = 1; });
