const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() {
    this.listeners = {};
    this.children = [];
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this._text = "";
  }
  get firstChild() { return this.children[0] || null; }
  get textContent() { return this._text; }
  set textContent(value) { this._text = String(value); this.children = []; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  appendChild(child) { this.children.push(child); return child; }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); }
}

const tick = (ms = 0) => new Promise(resolve => setTimeout(resolve, ms));
const ok = body => ({ ok: true, status: 200, json: async () => body });

async function main() {
  const elements = new Map();
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, new Element());
      return elements.get(selector);
    },
    createElement() { return new Element(); },
  };
  const oldId = "Guiaaaaaaaaaaaa";
  const currentId = "Guibbbbbbbbbbbb";
  let rejectOld;
  const oldPending = new Promise((resolve, reject) => { rejectOld = reject; });
  let failCurrent = false;

  const fetch = async url => {
    if (url === "/") return ok({});
    if (url === "/api/dbvora") return ok({ available: false, error_code: "NOT_CONFIGURED" });
    if (url === "/api/runs?limit=10") {
      return ok({ runs: [
        { run_id: oldId, status: "completed", created_at: "2026-10-29T02:00:00.000Z" },
        { run_id: currentId, status: "completed", created_at: "2026-10-29T02:01:00.000Z" },
      ] });
    }
    if (url === "/api/status?run_id=" + oldId) return oldPending;
    if (url === "/api/status?run_id=" + currentId) {
      if (failCurrent) throw new Error("current status request failed");
      return ok({
        run_id: currentId, status: "completed",
        steps_recorded: 1, step_outcomes: { completed: 1 },
        integration: { workflow_status: "completed", dbvora: { available: false, error_code: "NOT_CONFIGURED" } },
      });
    }
    if (url.startsWith("/api/audit?run_id=")) return ok({ available: false });
    throw new Error("Unexpected route: " + url);
  };

  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "..", "axflow", "static", "app.js"), "utf8"),
    { document, fetch, localStorage: { getItem() { return null; }, setItem() {} } },
  );
  await tick(10);
  const runs = elements.get("#recent-runs-list").children.map(li => li.children[0]);
  assert.equal(runs.length, 2, "synthetic recent-run choices must render");
  runs[0].listeners.click();
  await tick();
  runs[1].listeners.click();
  await tick(10);

  assert.equal(elements.get("#run-id").textContent, currentId);
  assert.equal(elements.get("#result-card").hidden, false);
  rejectOld(new Error("stale status request failed"));
  await tick(10);
  assert.equal(elements.get("#run-id").textContent, currentId, "stale rejection must preserve newer run");
  assert.equal(elements.get("#result-card").hidden, false, "stale rejection must not hide newer result");
  assert.match(elements.get("#history-state").textContent, /불러왔습니다/, "newer success message must be retained");

  failCurrent = true;
  runs[1].listeners.click();
  await tick(10);
  assert.equal(elements.get("#result-card").hidden, true, "current failed lookup must hide stale result");
  assert.equal(elements.get("#history-state").className, "history-state error");
  assert.match(elements.get("#history-state").textContent, /요청을 완료하지 못했습니다/);
  process.stdout.write("PASS: stale history failure ignored, current failure displayed\n");
}

main().catch(error => { process.stderr.write(error.stack + "\n"); process.exitCode = 1; });
