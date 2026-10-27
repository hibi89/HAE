const taskInput = document.querySelector("#task");
const csvInput = document.querySelector("#csv-path");
const csvFileInput = document.querySelector("#csv-file");
const previewButton = document.querySelector("#preview");
const runButton = document.querySelector("#run");
const approvalInput = document.querySelector("#approval");
const planOutput = document.querySelector("#plan");
const connection = document.querySelector("#connection");
const message = document.querySelector("#message");
const resultCard = document.querySelector("#result-card");
const resultStatus = document.querySelector("#result-status");
const resultTitle = document.querySelector("#result-title");
const resultCopy = document.querySelector("#result-copy");
const runIdOutput = document.querySelector("#run-id");
const rowCountOutput = document.querySelector("#row-count");
const rowCountLabel = document.querySelector("#row-count-label");
const stepCountOutput = document.querySelector("#step-count");
const refreshButton = document.querySelector("#refresh-status");
const approvalSection = document.querySelector("#approval-section");
const dbvoraStatus = document.querySelector("#dbvora-status");
const dbvoraMeta = document.querySelector("#dbvora-meta");
const dbvoraProvenance = document.querySelector("#dbvora-provenance");
const dbvoraTables = document.querySelector("#dbvora-tables");
const dbvoraRelations = document.querySelector("#dbvora-relations");
const dbvoraRefreshButton = document.querySelector("#refresh-dbvora");

let previewKey = "";
let currentRunId = "";
let previewId = "";
let requiresApproval = true;

function requestKey() {
  return JSON.stringify([taskInput.value, csvInput.value]);
}

function setMessage(text, state = "") {
  message.textContent = text;
  message.className = "message" + (state ? " " + state : "");
}

function updateRunButton() {
  approvalSection.hidden = !requiresApproval;
  runButton.disabled = !previewKey || previewKey !== requestKey() || (requiresApproval && !approvalInput.checked);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { cache: "no-store", ...options, headers });
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error || "요청 실패 (" + response.status + ")");
    error.detail = body;
    throw error;
  }
  return body;
}

async function fileToBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function showStatus(status) {
  resultStatus.textContent = status.status;
  resultTitle.textContent = status.status === "completed" ? "흐름 실행 완료" :
    (status.status === "failed" ? "실행 중단" : "실행 상태");
  resultCopy.textContent = status.error_type
    ? "마지막 단계에서 " + status.error_type + " 오류가 기록되었습니다. 입력 데이터는 실행 기록에 표시하지 않습니다."
    : "실행 기록에는 단계 상태와 계획 지문만 표시되며 입력 행 데이터는 포함되지 않습니다.";
  runIdOutput.textContent = status.run_id;
  const outcomes = status.step_outcomes || {};
  stepCountOutput.textContent = (outcomes.completed || 0) + " / " + (status.steps_recorded || 0);
  resultCard.hidden = false;
}

async function checkConnection() {
  try {
    const response = await fetch("/", { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    connection.textContent = "로컬 서버 연결됨";
    connection.className = "connection online";
  } catch {
    connection.textContent = "로컬 서버 연결을 확인할 수 없습니다";
    connection.className = "connection offline";
  }
}

function clearChildren(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function describeDbvoraProvenance(result) {
  const parts = [];
  const dbId = typeof result.db_id === "string" && /^[a-f0-9]{24}$/.test(result.db_id)
    ? result.db_id
    : "";
  const provenance = result.provenance && typeof result.provenance === "object" &&
    !Array.isArray(result.provenance) ? result.provenance : {};

  if (dbId) parts.push("선택 DB ID " + dbId);
  if (provenance.cpu_usage === "unavailable") {
    parts.push("CPU 사용량: 제공되지 않음");
  }
  if (provenance.size_bytes === "measured_local_filesystem") {
    parts.push("크기: 로컬 파일시스템 측정");
  }
  if (provenance.tables === "measured_sqlite_catalog") {
    parts.push("테이블: SQLite catalog");
  }
  if (provenance.relationships === "declared_sqlite_foreign_keys") {
    parts.push("관계: SQLite 선언 FK");
  }

  return parts.length ? "출처: " + parts.join(" · ") : "출처 메타데이터를 사용할 수 없습니다.";
}

function renderDbvora(result) {
  clearChildren(dbvoraTables);
  clearChildren(dbvoraRelations);
  if (!result.available) {
    dbvoraStatus.textContent = result.message || "DBVORA 로컬 서비스를 사용할 수 없습니다.";
    dbvoraStatus.className = "dbvora-status offline";
    dbvoraMeta.textContent = result.error_code === "NOT_CONFIGURED"
      ? "실행 시 --dbvora-url로 127.0.0.1 API 주소를 설정하세요."
      : "DBVORA API가 실행 중인지 확인한 뒤 새로고침하세요.";
    dbvoraProvenance.textContent = "";
    return;
  }

  dbvoraStatus.textContent = "DBVORA 로컬 읽기 전용 API 연결됨";
  dbvoraStatus.className = "dbvora-status online";
  dbvoraMeta.textContent = "SQLite 파일 " + Number(result.size_bytes).toLocaleString() + " bytes · " +
    result.size_scope + " · 관측 " + result.observed_at;
  dbvoraProvenance.textContent = describeDbvoraProvenance(result);

  for (const table of result.tables) {
    const article = document.createElement("article");
    article.className = "dbvora-table";
    const title = document.createElement("h3");
    title.textContent = table.name;
    article.appendChild(title);
    const columnList = document.createElement("ul");
    for (const column of table.columns) {
      const item = document.createElement("li");
      const primaryKey = column.pk_position > 0 ? " · PK " + column.pk_position : "";
      item.textContent = column.name + (column.type ? " · " + column.type : "") + primaryKey;
      columnList.appendChild(item);
    }
    article.appendChild(columnList);
    dbvoraTables.appendChild(article);
  }

  if (result.relationships.length === 0) {
    dbvoraRelations.textContent = "선언된 외래 키 관계가 없습니다.";
    return;
  }
  const relationTitle = document.createElement("h3");
  relationTitle.textContent = "선언된 관계";
  dbvoraRelations.appendChild(relationTitle);
  const relationList = document.createElement("ul");
  for (const relation of result.relationships) {
    const item = document.createElement("li");
    item.textContent = relation.from_table + "." + relation.from_columns.join(", ") +
      " → " + relation.to_table + "." + relation.to_columns.join(", ");
    relationList.appendChild(item);
  }
  dbvoraRelations.appendChild(relationList);
}

async function loadDbvora() {
  dbvoraRefreshButton.disabled = true;
  dbvoraStatus.textContent = "DBVORA 읽기 전용 메타데이터 조회 중…";
  dbvoraStatus.className = "dbvora-status";
  try {
    renderDbvora(await api("/api/dbvora"));
  } catch {
    dbvoraStatus.textContent = "AX FLOW 로컬 서비스에서 DBVORA 상태를 확인할 수 없습니다.";
    dbvoraStatus.className = "dbvora-status offline";
    dbvoraMeta.textContent = "";
  } finally {
    dbvoraRefreshButton.disabled = false;
  }
}

previewButton.addEventListener("click", async () => {
  previewButton.disabled = true;
  setMessage("지원 범위와 IR을 검증하고 있습니다…");
  previewKey = "";
  previewId = "";
  requiresApproval = true;
  updateRunButton();
  try {
    const response = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({ task: taskInput.value, csv_path: csvInput.value }),
    });
    planOutput.textContent = JSON.stringify(response.plan, null, 2);
    previewKey = requestKey();
    previewId = response.preview_id;
    requiresApproval = response.requires_approval;
    const descriptions = {
      csv_to_sqlite: "CSV 전체를 로컬 SQLite에 저장하는 흐름입니다.",
      csv_normalize_import: "지정한 CSV 열을 정규화하고 중복 행을 보고한 뒤 로컬 SQLite에 저장합니다.",
      csv_filtered_import: "조건에 맞는 CSV 행만 로컬 SQLite에 저장합니다.",
      csv_conditional_import: "조건이 맞을 때만 CSV 행을 로컬 SQLite에 저장합니다.",
      csv_lookup: "읽기 전용으로 일치 행 수와 원본 행 번호만 확인합니다.",
    };
    setMessage(descriptions[response.workflow] || "지원되는 CSV 흐름입니다.", "success");
  } catch (error) {
    planOutput.textContent = "요청을 IR로 변환할 수 없습니다.";
    setMessage(error.message, "error");
  } finally {
    previewButton.disabled = false;
    updateRunButton();
  }
});

for (const input of [taskInput, csvInput]) {
  input.addEventListener("input", () => {
    previewKey = "";
    previewId = "";
    requiresApproval = true;
    updateRunButton();
    resultCard.hidden = true;
  });
}
csvFileInput.addEventListener("change", async () => {
  const file = csvFileInput.files?.[0];
  if (!file) return;
  previewKey = "";
  previewId = "";
  requiresApproval = true;
  resultCard.hidden = true;
  csvInput.value = "";
  updateRunButton();
  if (!file.name.toLowerCase().endsWith(".csv")) {
    setMessage("UTF-8 CSV 파일만 선택할 수 있습니다.", "error");
    return;
  }
  if (file.size === 0 || file.size > 512 * 1024) {
    setMessage("CSV 파일은 비어 있지 않아야 하며 512 KiB 이하여야 합니다.", "error");
    return;
  }
  previewButton.disabled = true;
  setMessage("CSV를 이 PC의 임시 폴더에 복사하고 있습니다…");
  try {
    const response = await api("/api/upload", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_base64: await fileToBase64(file),
      }),
    });
    csvInput.value = response.csv_path;
    setMessage(
      file.name + " · " + Number(response.size_bytes).toLocaleString() +
      " bytes를 임시 저장했습니다. 서버 종료 때 삭제됩니다.",
      "success",
    );
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    previewButton.disabled = false;
    updateRunButton();
  }
});

approvalInput.addEventListener("change", updateRunButton);

runButton.addEventListener("click", async () => {
  if ((requiresApproval && !approvalInput.checked) || previewKey !== requestKey()) return;
  runButton.disabled = true;
  setMessage(requiresApproval
    ? "합성 CSV를 검사한 뒤 로컬 SQLite에 저장합니다…"
    : "합성 CSV를 읽기 전용으로 검색합니다…");
  try {
    const response = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({
        task: taskInput.value, csv_path: csvInput.value,
        preview_id: previewId, approve_writes: requiresApproval && approvalInput.checked,
      }),
    });
    currentRunId = response.run_id;
    showStatus(response.status);
    if (Number.isInteger(response.result.imported_rows)) {
      rowCountLabel.textContent = "저장 행";
      rowCountOutput.textContent = String(response.result.imported_rows);
      const duplicateCount = Number.isInteger(response.result.duplicate_count) ? response.result.duplicate_count : 0;
      const duplicateRows = Array.isArray(response.result.duplicate_row_numbers)
        ? " (원본 행 " + response.result.duplicate_row_numbers.join(", ") + ")"
        : "";
      const duplicateSummary = duplicateCount
        ? " 중복 행 " + duplicateCount + "개" + duplicateRows + "도 삭제하지 않고 저장했습니다."
        : " 중복 행은 없습니다.";
      resultCopy.textContent = response.result.imported_rows + "개 행을 이 PC의 선택된 합성 데이터 SQLite 파일에 저장했습니다." + duplicateSummary;
    } else if (Number.isInteger(response.result.matched_count)) {
      rowCountLabel.textContent = "일치 행";
      rowCountOutput.textContent = String(response.result.matched_count);
      const lines = Array.isArray(response.result.matched_row_numbers)
        ? " (원본 데이터 행 " + response.result.matched_row_numbers.join(", ") + ")"
        : "";
      resultCopy.textContent = response.result.matched_count + "개 행이 조건과 일치했습니다." + lines +
        ". 원본 행 데이터는 실행 기록이나 화면 응답에 포함하지 않습니다.";
    } else {
      rowCountLabel.textContent = "처리 행";
      rowCountOutput.textContent = "0";
      resultCopy.textContent = "조건에 맞는 행이 없어 저장을 건너뛰었습니다.";
    }
    setMessage("실행 영수증을 만들었습니다.", "success");
  } catch (error) {
    if (error.detail && error.detail.status && error.detail.run_id) {
      currentRunId = error.detail.run_id;
      showStatus(error.detail.status);
      resultCopy.textContent = error.message + " · 실패 원인을 실행 기록에 저장했습니다.";
    }
    setMessage(error.message, "error");
  } finally {
    updateRunButton();
  }
});

refreshButton.addEventListener("click", async () => {
  if (!currentRunId) return;
  try {
    showStatus(await api("/api/status?run_id=" + encodeURIComponent(currentRunId)));
  } catch (error) {
    setMessage(error.message, "error");
  }
});

dbvoraRefreshButton.addEventListener("click", loadDbvora);

checkConnection();
loadDbvora();
