const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor(selector) {
    this.selector = selector;
    this.listeners = {};
    this.children = [];
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this.textContent = "";
  }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  appendChild(child) { this.children.push(child); return child; }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); }
  get firstChild() { return this.children[0] || null; }
}

async function main() {
  const elements = new Map();
  let deferredPreview = null;
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, new Element(selector));
      return elements.get(selector);
    },
    createElement(tag) { return new Element(tag); },
  };
  const fetch = async (url) => {
    if (url === "/") return { ok: true, status: 200, json: async () => ({}) };
    if (url === "/api/dbvora") return { ok: true, status: 200, json: async () => ({ available: false, error_code: "NOT_CONFIGURED" }) };
    if (url === "/api/runs?limit=10") return { ok: true, status: 200, json: async () => ({ runs: [] }) };
    if (url === "/api/upload") return { ok: true, status: 201, json: async () => ({ csv_path: "axflow-upload/test/file.csv", size_bytes: 7 }) };
    if (url === "/api/preview") {
      if (deferredPreview) return deferredPreview;
      return { ok: true, status: 200, json: async () => ({
        plan: { steps: [] }, workflow: "csv_to_sqlite", requires_approval: true,
        preview_id: "preview-token", input: { row_count: 1, headers: ["id"], size_bytes: 7 },
      }) };
    }
    throw new Error("unexpected request: " + url);
  };
  const app = path.join(__dirname, "..", "axflow", "static", "app.js");
  vm.runInNewContext(fs.readFileSync(app, "utf8"), { document, fetch, btoa: global.btoa, Uint8Array });
  await new Promise((resolve) => setTimeout(resolve, 0));
  const task = elements.get("#task");
  const csv = elements.get("#csv-path");
  const approval = elements.get("#approval");
  const preview = elements.get("#preview");
  const csvFile = elements.get("#csv-file");
  const run = elements.get("#run");
  task.value = "Import this CSV into SQLite";
  csv.value = "sales.csv";

  await preview.listeners.click();
  assert.equal(approval.checked, false);
  assert.equal(run.disabled, true, "a new write preview requires a fresh explicit approval");
  approval.checked = true;
  approval.listeners.change();
  assert.equal(run.disabled, false);

  task.value = "Import this CSV after changing the request";
  task.listeners.input();
  assert.equal(approval.checked, false, "changing the task clears the prior approval checkbox");
  assert.equal(run.disabled, true, "changing the task invalidates the approved preview");

  await preview.listeners.click();
  approval.checked = true;
  approval.listeners.change();
  assert.equal(run.disabled, false);
  await preview.listeners.click();
  assert.equal(approval.checked, false, "re-running preview requires approval again");
  assert.equal(run.disabled, true);

  approval.checked = true;
  approval.listeners.change();
  csvFile.files = [{ name: "replacement.csv", size: 7, arrayBuffer: async () => new Uint8Array([105, 100, 10, 49, 10]).buffer }];
  await csvFile.listeners.change();
  assert.equal(approval.checked, false, "selecting a new CSV clears the prior approval checkbox");
  assert.equal(run.disabled, true, "selecting a new CSV leaves execution disabled until re-preview and approval");

  let finishPreview;
  deferredPreview = new Promise((resolve) => { finishPreview = resolve; });
  const pending = preview.listeners.click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  task.value = "Request changed while the preview was running";
  task.listeners.input();
  finishPreview({ ok: true, status: 200, json: async () => ({
    plan: { steps: [{ id: "old", op: "sqlite_import_csv" }] },
    workflow: "csv_to_sqlite", requires_approval: true, preview_id: "stale-preview-token",
    input: { row_count: 1, headers: ["id"], size_bytes: 7 },
  }) });
  await pending;
  deferredPreview = null;
  assert.equal(run.disabled, true, "a stale preview response cannot enable execution for changed input");
  assert.equal(approval.checked, false, "a stale preview response cannot restore approval state");
  assert.equal(elements.get("#preview-detail").hidden, true, "a stale plan is not displayed as current preview");
  assert.match(elements.get("#message").textContent, /입력이 변경되었습니다/);
  process.stdout.write("PASS: task, CSV, and fresh preview changes clear approval state\n");
}

main().catch((error) => {
  process.stderr.write(error.stack + "\n");
  process.exitCode = 1;
});
