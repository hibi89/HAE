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
(async () => {
  await testPreviewStaleFailure();
  await testHistoryStaleFailure();
  await testPreviewSupersededByNewRequest();
  await testUploadStaleResponse();
  await testRecentRunsNewestWins();
  console.log("HAE simulated UI race tests: 5 PASS");
})().catch((error) => { console.error(error); process.exitCode = 1; });
