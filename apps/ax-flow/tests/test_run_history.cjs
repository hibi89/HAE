const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor(selector = "") {
    this.selector = selector;
    this.children = [];
    this.listeners = {};
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this._textContent = "";
  }
  get firstChild() { return this.children[0] || null; }
  get textContent() { return this._textContent; }
  set textContent(value) { this._textContent = String(value); this.children = []; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  appendChild(child) { this.children.push(child); return child; }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); return child; }
}

async function scenario({ auditAvailable }) {
  const elements = new Map();
  const stored = new Map([["hae.last_run_id", "Gui0123456789ab"]]);
  const calls = [];
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, new Element(selector));
      return elements.get(selector);
    },
    createElement(tag) { return new Element(tag); },
  };
  const integration = {
    workflow_status: "completed",
    dbvora: { available: false, error_code: "NOT_CONFIGURED", message: "ignored untrusted text" },
  };
  const audit = {
    available: true,
    review: { schema_version: "sovia.plan_observation_review.v1" },
    execution: { executed_steps: [{}], failed_steps: [], unverifiable_steps: [], policy_findings: [] },
  };
  const fetch = async (url) => {
    calls.push(url);
    if (url === "/") return { ok: true, status: 200, json: async () => ({}) };
    if (url === "/api/dbvora") return { ok: true, status: 200, json: async () => integration.dbvora };
    if (url === "/api/runs?limit=10") return {
      ok: true, status: 200,
      json: async () => ({ runs: [
        { run_id: "Gui0123456789ab", status: "completed", created_at: "2026-10-29T02:03:04.000Z",
          steps_recorded: 3, step_outcomes: { completed: 3 } },
        { run_id: "Guiabcdef123456", status: "hostile path marker", created_at: null,
          steps_recorded: 1, step_outcomes: { completed: 0 } },
      ] }),
    };
    if (url.startsWith("/api/status?")) return {
      ok: true, status: 200,
      json: async () => ({
        run_id: "Gui0123456789ab", status: "completed", steps_recorded: 3,
        step_outcomes: { completed: 3, failed: 0, running: 0, skipped: 0 },
        error_type: null, result_summary: { kind: "saved", count: 2, duplicate_count: 0 },
        integration,
      }),
    };
    if (url.startsWith("/api/audit?")) return auditAvailable
      ? { ok: true, status: 200, json: async () => audit }
      : { ok: false, status: 404, json: async () => ({ error: "not available" }) };
    throw new Error("Unexpected test request: " + url);
  };

  const appPath = path.join(__dirname, "..", "axflow", "static", "app.js");
  vm.runInNewContext(fs.readFileSync(appPath, "utf8"), {
    document, fetch,
    localStorage: {
      getItem(key) { return stored.get(key) || null; },
      setItem(key, value) { stored.set(key, value); },
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 10));

  assert.equal(elements.get("#history-run-id").value, "Gui0123456789ab");
  assert.equal(elements.get("#result-card").hidden, false);
  assert.equal(elements.get("#run-id").textContent, "Gui0123456789ab");
  assert.equal(elements.get("#row-count").textContent, "2");
  assert.equal(elements.get("#recent-runs-list").children.length, 2);
  assert.match(elements.get("#recent-runs-list").children[0].children[0].textContent, /완료.*단계 3\/3/);
  assert.match(elements.get("#recent-runs-list").children[1].children[0].textContent, /상태 확인 필요.*시각 정보 없음/);
  assert.match(elements.get("#history-state").textContent, /데이터 쓰기는 발생하지 않았습니다/);
  assert.match(elements.get("#dbvora-status").textContent, /미설정/);
  assert.doesNotMatch([...elements.values()].map((el) => el.textContent).join(" "), /ignored untrusted text|payload|customer data/i);
  assert.equal(stored.size, 1, "browser storage must contain only the execution ID");
  assert(calls.some((url) => url.startsWith("/api/status?run_id=")));
  assert(calls.some((url) => url.startsWith("/api/audit?run_id=")));
  assert(calls.includes("/api/runs?limit=10"));
  assert(!calls.some((url) => url === "/api/run" || url.startsWith("/api/run?")), "recovery must never execute a workflow");
  if (auditAvailable) {
    assert.match(elements.get("#sovia-result").textContent, /실시간 실행 차단 아님/);
  } else {
    assert.match(elements.get("#sovia-result").textContent, /기록이 없습니다/);
  }

  const previousCalls = calls.length;
  elements.get("#history-run-id").value = "../invalid";
  await elements.get("#load-run-history").listeners.click();
  assert.equal(calls.length, previousCalls, "invalid IDs must be rejected before any request");
  assert.match(elements.get("#history-state").textContent, /형식이 올바르지 않습니다/);
  await elements.get("#recent-runs-list").children[1].children[0].listeners.click();
  assert.equal(elements.get("#history-run-id").value, "Guiabcdef123456");
  assert(!calls.some((url) => url === "/api/run" || url.startsWith("/api/run?")), "selecting history must remain read-only");
}

Promise.all([scenario({ auditAvailable: true }), scenario({ auditAvailable: false })])
  .then(() => process.stdout.write("PASS: run recovery is read-only, redacted, restart-persistent, and distinguishes missing audit\n"))
  .catch((error) => {
    process.stderr.write(error.stack + "\n");
    process.exitCode = 1;
  });
