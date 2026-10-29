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
    this.checked = false;
    this.disabled = false;
    this.hidden = false;
    this.className = "";
    this._textContent = "";
  }

  get firstChild() {
    return this.children[0] || null;
  }

  get textContent() {
    return this._textContent;
  }

  set textContent(value) {
    this._textContent = String(value);
    this.children = [];
  }

  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    return child;
  }
}

async function main() {
  const elements = new Map();
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, new Element(selector));
      return elements.get(selector);
    },
    createElement(tag) {
      return new Element(tag);
    },
  };

  let payload = {
    available: true,
    db_id: "0123456789abcdef01234567",
    size_bytes: 2048,
    size_scope: "main_database_file_only_excludes_wal_and_shm",
    observed_at: "2026-10-27T00:00:00Z",
    provenance: {
      cpu_usage: "unavailable",
      relationships: "declared_sqlite_foreign_keys",
      size_bytes: "measured_local_filesystem",
      tables: "measured_sqlite_catalog",
      secret_path: "C:\\private\\customer.db",
      html_payload: "<img src=x onerror=alert(1)>",
    },
    tables: [],
    relationships: [],
  };

  const fetch = async (url) => {
    if (url === "/") return { ok: true, status: 200 };
    if (url === "/api/dbvora") {
      return { ok: true, status: 200, json: async () => payload };
    }
    throw new Error("Unexpected test request: " + url);
  };

  const appPath = path.join(__dirname, "..", "axflow", "static", "app.js");
  vm.runInNewContext(fs.readFileSync(appPath, "utf8"), { document, fetch });
  await new Promise((resolve) => setImmediate(resolve));

  const provenance = elements.get("#dbvora-provenance");
  assert.match(provenance.textContent, /CPU 사용량: 제공되지 않음/);
  assert.match(provenance.textContent, /선택 DB ID 0123456789abcdef01234567/);
  assert.doesNotMatch(provenance.textContent, /customer\.db|onerror|<img/i);
  assert.equal(provenance.children.length, 0, "untrusted provenance must not create DOM nodes");

  payload = {
    available: false,
    error_code: "UNAVAILABLE",
    message: "DBVORA service unavailable.",
  };
  await elements.get("#refresh-dbvora").listeners.click();
  assert.equal(provenance.textContent, "", "offline refresh must clear previously shown provenance");
  assert.match(elements.get("#dbvora-status").className, /offline/);
  assert.match(elements.get("#dbvora-status").textContent, /꺼져 있거나 연결할 수 없습니다/);

  payload = {
    available: false,
    error_code: "NOT_CONFIGURED",
    message: "C:\\private\\customer.db must never be displayed",
  };
  await elements.get("#refresh-dbvora").listeners.click();
  assert.match(elements.get("#dbvora-status").textContent, /미설정/);
  assert.match(elements.get("#dbvora-meta").textContent, /127\.0\.0\.1/);
  assert.doesNotMatch(elements.get("#dbvora-status").textContent + elements.get("#dbvora-meta").textContent,
    /customer\.db|private/i);

  process.stdout.write("PASS: provenance labels render safely and clear after offline refresh\n");
}

main().catch((error) => {
  process.stderr.write(error.stack + "\n");
  process.exitCode = 1;
});

