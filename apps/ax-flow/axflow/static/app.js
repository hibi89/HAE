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
const previewDetail = document.querySelector("#preview-detail");
const backendOutput = document.querySelector("#engine-backend");
const stepListOutput = document.querySelector("#step-list");
const soviaResult = document.querySelector("#sovia-result");
const historyRunId = document.querySelector("#history-run-id");
const historyLoadButton = document.querySelector("#load-run-history");
const historyCopyButton = document.querySelector("#copy-run-id");
const historyState = document.querySelector("#history-state");
const recentRunsButton = document.querySelector("#refresh-run-list");
const recentRunsState = document.querySelector("#recent-runs-state");
const recentRunsList = document.querySelector("#recent-runs-list");
const executionState = document.querySelector("#execution-state");

const LAST_RUN_KEY = "hae.last_run_id";
const RUN_ID_PATTERN = /^Gui[A-Fa-f0-9]{12}$/;

let previewKey = "";
let currentRunId = "";
let previewId = "";
let requiresApproval = true;
let historyRequestVersion = 0;
let uploadRequestVersion = 0;
let recentRunsRequestVersion = 0;
let previewRequestVersion = 0;
let uploadInProgress = false;

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
    error.status = response.status;
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
  const integration = status.integration || status;
  const partial = integration.workflow_status === "partial";
  resultStatus.textContent = status.status || "unknown";
  resultTitle.textContent = partial ? "실행 완료 · 통합 일부 확인 불가" : status.status === "completed" ? "흐름 실행 완료" :
    (status.status === "failed" ? "실행 실패" : status.status === "running" ? "실행 진행 중 또는 중단됨" : "실행 상태");
  resultCopy.textContent = status.error_type
    ? "마지막 단계에서 " + status.error_type + " 오류가 기록되었습니다. 원본 데이터와 내부 오류 내용은 표시하지 않습니다."
    : "실행 기록에는 단계 상태와 요약만 표시되며 입력 행 데이터는 포함되지 않습니다.";
  runIdOutput.textContent = status.run_id;
  const outcomes = status.step_outcomes || {};
  stepCountOutput.textContent = (outcomes.completed || 0) + " / " + (status.steps_recorded || 0);
  const summary = status.result_summary;
  if (summary && Number.isInteger(summary.count)) {
    rowCountLabel.textContent = summary.kind === "saved" ? "저장 행" :
      summary.kind === "matched" ? "일치 행" : "처리 행";
    rowCountOutput.textContent = String(summary.count);
    if (summary.kind === "saved" && Number.isInteger(summary.duplicate_count)) {
      resultCopy.textContent += " 저장 " + summary.count + "개 행 · 중복 " + summary.duplicate_count + "개.";
    }
  } else {
    rowCountLabel.textContent = "처리 행";
    rowCountOutput.textContent = "기록 없음";
  }
  executionState.textContent = partial
    ? "실행 상태와 통합 상태를 분리해 표시합니다. DBVORA는 현재 연결 상태이며 SOVIA는 저장된 사후 자문입니다."
    : status.status === "running"
      ? "이 기록이 재시작 후에도 진행 중으로 남아 있습니다. 다시 실행하지 말고 원인을 확인하세요."
      : "SOVIA 사후 자문과 DBVORA 현재 연결 상태는 아래에서 별도로 표시합니다.";
  resultCard.hidden = false;
  renderSovia(integration.sovia_audit, integration.sovia_state);
  if (integration.dbvora) renderDbvora(integration.dbvora);
  if (partial) resultCopy.textContent += " SOVIA 또는 DBVORA 통합 일부를 확인할 수 없어 부분 완료로 표시합니다.";
}

function renderSovia(report, state = "") {
  if (!report) {
    soviaResult.textContent = state === "missing"
      ? "이 실행의 저장된 SOVIA 사후 자문 기록이 없습니다."
      : state === "unavailable"
        ? "SOVIA 사후 자문을 조회할 수 없습니다."
        : "SOVIA 사후 자문 기록을 아직 조회하지 않았습니다.";
    return;
  }
  if (!report.available) {
    soviaResult.textContent = "SOVIA 사후 자문을 생성할 수 없었습니다. 이는 실행 자체와 별개이며 실시간 실행 차단 기능이 아닙니다.";
    return;
  }
  const review = report.review || {};
  const execution = report.execution || {};
  const findingCount = Array.isArray(execution.policy_findings) ? execution.policy_findings.length : 0;
  soviaResult.textContent = "SOVIA 사후 자문 · 실행 단계 " +
    (execution.executed_steps || []).length + "개 관측 · 실패 " +
    (execution.failed_steps || []).length + " · 확인 불가 " +
    (execution.unverifiable_steps || []).length + " · 검토 항목 " + findingCount +
    " · 증거 인증 안 됨 · 사후 자문 전용, 실시간 실행 차단 아님 (" +
    (typeof review.schema_version === "string" ? review.schema_version.slice(0, 64) : "contract unknown") + ")";
}

function rememberRunId(runId) {
  if (!RUN_ID_PATTERN.test(runId)) return;
  currentRunId = runId;
  historyRunId.value = runId;
  historyCopyButton.disabled = false;
  try { localStorage.setItem(LAST_RUN_KEY, runId); } catch { /* Browser storage may be disabled. */ }
}

function safeFailureMessage(error) {
  const type = error?.detail?.error_type;
  if (type === "ApprovalRequired") return "승인이 만료되었거나 누락되었습니다. 미리보기를 다시 실행하고 승인하세요.";
  if (type === "PlanError" || type === "RequestError") return "요청 또는 CSV 입력을 확인하고 새 미리보기를 실행하세요.";
  if (["BackendUnavailable", "LightningExecutionError", "StepTimeout", "StepRetryExhausted"].includes(type)) {
    return "LA 실행을 완료하지 못했습니다. 실행 ID가 있으면 실행 기록을 조회하고 입력을 확인하세요.";
  }
  if (error?.status === 404) return "해당 실행 ID의 저장된 실행 기록을 찾을 수 없습니다.";
  if (error?.status === 400) return "실행 ID 형식이 올바르지 않습니다. HAE에서 표시한 실행 ID를 입력하세요.";
  return "요청을 완료하지 못했습니다. 입력을 확인하고 미리보기를 다시 실행하세요.";
}

async function loadRunHistory() {
  const requestVersion = ++historyRequestVersion;
  const runId = historyRunId.value.trim();
  if (!RUN_ID_PATTERN.test(runId)) {
    historyState.textContent = "실행 ID 형식이 올바르지 않습니다. 예: Gui0123456789ab";
    historyState.className = "history-state error";
    historyCopyButton.disabled = true;
    resultCard.hidden = true;
    return;
  }
  historyLoadButton.disabled = true;
  historyState.textContent = "저장된 실행 기록을 읽기 전용으로 조회하고 있습니다…";
  historyState.className = "history-state";
  try {
    const status = await api("/api/status?run_id=" + encodeURIComponent(runId));
    if (requestVersion !== historyRequestVersion || historyRunId.value.trim() !== runId) return;
    const integration = status.integration && typeof status.integration === "object"
      ? status.integration : {};
    try {
      integration.sovia_audit = await api("/api/audit?run_id=" + encodeURIComponent(runId));
      integration.sovia_state = "saved";
    } catch (auditError) {
      if (auditError.status === 404) {
        integration.sovia_audit = null;
        integration.sovia_state = "missing";
      } else {
        integration.sovia_audit = null;
        integration.sovia_state = "unavailable";
      }
    }
    if (requestVersion !== historyRequestVersion || historyRunId.value.trim() !== runId) return;
    status.integration = integration;
    rememberRunId(runId);
    showStatus(status);
    historyState.textContent = "저장된 실행 결과와 자문 상태를 불러왔습니다. 새 업무 실행이나 데이터 쓰기는 발생하지 않았습니다.";
    historyState.className = "history-state success";
  } catch (error) {
    if (requestVersion !== historyRequestVersion || historyRunId.value.trim() !== runId) return;
    resultCard.hidden = true;
    historyState.textContent = safeFailureMessage(error);
    historyState.className = "history-state error";
  } finally {
    if (requestVersion === historyRequestVersion) historyLoadButton.disabled = false;
  }
}

function restoreLastRunId() {
  let saved = "";
  try { saved = localStorage.getItem(LAST_RUN_KEY) || ""; } catch { return; }
  if (!RUN_ID_PATTERN.test(saved)) return;
  historyRunId.value = saved;
  historyCopyButton.disabled = false;
  loadRunHistory();
}

function runStatusLabel(value) {
  return value === "completed" ? "완료" : value === "failed" ? "실패" :
    value === "running" ? "진행 중 또는 중단 확인 필요" : "상태 확인 필요";
}

function runTimestampLabel(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)) {
    return "시각 정보 없음";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "시각 정보 없음" : date.toLocaleString();
}

async function loadRecentRuns() {
  const requestVersion = ++recentRunsRequestVersion;
  recentRunsButton.disabled = true;
  recentRunsState.textContent = "최근 실행 목록을 읽기 전용으로 조회하고 있습니다…";
  recentRunsState.className = "history-state";
  clearChildren(recentRunsList);
  try {
    const response = await api("/api/runs?limit=10");
    if (requestVersion !== recentRunsRequestVersion) return;
    const runs = Array.isArray(response.runs) ? response.runs.slice(0, 20) : [];
    if (!runs.length) {
      recentRunsState.textContent = "표시할 최근 실행이 없습니다. 날짜 정보가 없는 이전 기록은 실행 ID를 직접 입력해 열 수 있습니다.";
      return;
    }
    for (const run of runs) {
      if (!run || typeof run.run_id !== "string" || !RUN_ID_PATTERN.test(run.run_id)) continue;
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "recent-run-button";
      const outcomes = run.step_outcomes && typeof run.step_outcomes === "object" ? run.step_outcomes : {};
      const stepTotal = Number.isInteger(run.steps_recorded) ? Math.max(0, Math.min(32, run.steps_recorded)) : 0;
      const completed = Number.isInteger(outcomes.completed) ? Math.max(0, Math.min(stepTotal, outcomes.completed)) : 0;
      button.textContent = run.run_id + " · " + runStatusLabel(run.status) + " · " +
        runTimestampLabel(run.created_at) + " · 단계 " + completed + "/" + stepTotal;
      button.addEventListener("click", () => {
        historyRunId.value = run.run_id;
        loadRunHistory();
      });
      item.appendChild(button);
      recentRunsList.appendChild(item);
    }
    recentRunsState.textContent = recentRunsList.children.length
      ? "최근 실행 최대 10건입니다. 항목을 선택하면 저장된 상태와 자문을 읽습니다."
      : "표시할 수 있는 실행 ID가 없습니다.";
    recentRunsState.className = "history-state";
  } catch {
    if (requestVersion !== recentRunsRequestVersion) return;
    recentRunsState.textContent = "실행 목록을 불러올 수 없습니다. 로컬 HAE 서비스 상태를 확인하세요.";
    recentRunsState.className = "history-state error";
  } finally {
    if (requestVersion === recentRunsRequestVersion) recentRunsButton.disabled = false;
  }
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

function renderPreviewSteps(plan) {
  clearChildren(stepListOutput);
  const labels = {
    csv_read: "CSV 파일을 읽고 확인",
    csv_normalize: "요청한 열을 변환",
    csv_filter: "조건에 맞는 행을 찾기",
    condition: "조건 분기 계산",
    branch: "조건에 따라 분기",
    sqlite_import_csv: "승인 후 SQLite에 CSV 행 저장",
    sqlite_put: "승인 후 SQLite에 결과 저장",
    sqlite_get: "SQLite 결과 조회",
  };
  for (const step of plan.steps) {
    const item = document.createElement("li");
    item.textContent = labels[step.op] || ("지원 단계 확인: " + step.op);
    stepListOutput.appendChild(item);
  }
  previewDetail.hidden = false;
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
    const code = typeof result.error_code === "string" ? result.error_code : "UNKNOWN";
    dbvoraStatus.textContent = code === "NOT_CONFIGURED" ? "DBVORA 미설정" :
      code === "UNAVAILABLE" ? "DBVORA 서비스가 꺼져 있거나 연결할 수 없습니다." :
      "DBVORA 응답 또는 계약 오류 (" + code.slice(0, 40) + ")";
    dbvoraStatus.className = "dbvora-status offline";
    dbvoraMeta.textContent = code === "NOT_CONFIGURED"
      ? "실행 시 --dbvora-url로 127.0.0.1 API 주소를 설정하세요."
      : code === "UNAVAILABLE"
        ? "DBVORA 로컬 서비스를 시작한 뒤 메타데이터를 다시 조회하세요. HAE 실행은 계속 사용할 수 있습니다."
        : "DBVORA의 읽기 전용 API 응답을 확인한 뒤 메타데이터를 다시 조회하세요.";
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
    dbvoraStatus.textContent = "HAE 로컬 서비스에서 DBVORA 상태를 확인할 수 없습니다.";
    dbvoraStatus.className = "dbvora-status offline";
    dbvoraMeta.textContent = "";
  } finally {
    dbvoraRefreshButton.disabled = false;
  }
}

previewButton.addEventListener("click", async () => {
  const submittedTask = taskInput.value;
  const submittedCsvPath = csvInput.value;
  const submittedKey = JSON.stringify([submittedTask, submittedCsvPath]);
  const requestVersion = ++previewRequestVersion;
  previewButton.disabled = true;
  approvalInput.checked = false;
  setMessage("CSV 파일·구조·요청한 변환과 실행 범위를 읽기 전용으로 검증하고 있습니다…");
  previewKey = "";
  previewId = "";
  requiresApproval = true;
  updateRunButton();
  try {
    const response = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({ task: submittedTask, csv_path: submittedCsvPath }),
    });
    if (requestVersion !== previewRequestVersion || submittedKey !== requestKey()) {
      setMessage("미리보기 중 입력이 변경되었습니다. 현재 입력으로 다시 미리보기를 실행하세요.", "error");
      return;
    }
    planOutput.textContent = JSON.stringify(response.plan, null, 2);
    renderPreviewSteps(response.plan);
    const backend = response.engine_backend || {};
    backendOutput.textContent = backend.name === "Lightning Azent"
      ? `실행 엔진: Lightning Azent ${backend.package_version} · 개발 모드 · 계약 확인 완료`
      : "실행 엔진: HAE 기본 엔진";
    previewKey = submittedKey;
    previewId = response.preview_id;
    requiresApproval = response.requires_approval;
    const descriptions = {
      csv_to_sqlite: "CSV 전체를 로컬 SQLite에 저장하는 흐름입니다.",
      csv_normalize_import: "지정한 CSV 열을 정규화하고 중복 행을 보고한 뒤 로컬 SQLite에 저장합니다.",
      csv_filtered_import: "조건에 맞는 CSV 행만 로컬 SQLite에 저장합니다.",
      csv_conditional_import: "조건이 맞을 때만 CSV 행을 로컬 SQLite에 저장합니다.",
      csv_lookup: "읽기 전용으로 일치 행 수와 원본 행 번호만 확인합니다.",
    };
    const input = response.input;
    const csvSummary = input
      ? ` · ${input.row_count.toLocaleString()}행 · ${input.headers.length}열 · ${Number(input.size_bytes).toLocaleString()} bytes`
      : "";
    setMessage((descriptions[response.workflow] || "지원되는 CSV 흐름입니다.") + csvSummary, "success");
  } catch (error) {
    if (requestVersion !== previewRequestVersion || submittedKey !== requestKey()) {
      setMessage("미리보기 중 입력이 변경되었습니다. 현재 입력으로 다시 미리보기를 실행하세요.", "error");
      return;
    }
    planOutput.textContent = "요청을 IR로 변환할 수 없습니다.";
    previewDetail.hidden = true;
    setMessage(safeFailureMessage(error), "error");
  } finally {
    if (requestVersion === previewRequestVersion) previewButton.disabled = uploadInProgress;
    updateRunButton();
  }
});

for (const input of [taskInput, csvInput]) {
  input.addEventListener("input", () => {
    uploadRequestVersion += 1;
    previewRequestVersion += 1;
    uploadInProgress = false;
    previewButton.disabled = false;
    previewKey = "";
    previewId = "";
    requiresApproval = true;
    approvalInput.checked = false;
    updateRunButton();
    resultCard.hidden = true;
    previewDetail.hidden = true;
  });
}
csvFileInput.addEventListener("change", async () => {
  const uploadVersion = ++uploadRequestVersion;
  previewRequestVersion += 1;
  uploadInProgress = false;
  previewButton.disabled = false;
  const file = csvFileInput.files?.[0];
  if (!file) return;
  previewKey = "";
  previewId = "";
  requiresApproval = true;
  approvalInput.checked = false;
  resultCard.hidden = true;
  csvInput.value = "";
  updateRunButton();
  if (!file.name.toLowerCase().endsWith(".csv")) {
    setMessage("UTF-8 CSV 파일만 선택할 수 있습니다.", "error");
    return;
  }
  if (file.size === 0 || file.size > 256 * 1024) {
    setMessage("CSV 파일은 비어 있지 않아야 하며 256 KiB 이하여야 합니다.", "error");
    return;
  }
  uploadInProgress = true;
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
    if (uploadVersion !== uploadRequestVersion || csvFileInput.files?.[0] !== file || csvInput.value) return;
    csvInput.value = response.csv_path;
    setMessage(
      file.name + " · " + Number(response.size_bytes).toLocaleString() +
      " bytes를 임시 저장했습니다. 서버 종료 때 삭제됩니다.",
      "success",
    );
  } catch (error) {
    if (uploadVersion === uploadRequestVersion && csvFileInput.files?.[0] === file && !csvInput.value) {
      setMessage(safeFailureMessage(error), "error");
    }
  } finally {
    if (uploadVersion === uploadRequestVersion) {
      uploadInProgress = false;
      previewButton.disabled = false;
    }
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
    rememberRunId(response.run_id);
    showStatus({ ...response.status, integration: {
      sovia_audit: response.sovia_audit, dbvora: response.dbvora,
      workflow_status: response.workflow_status,
    } });
    const auditCount = Array.isArray(response.audit?.events) ? response.audit.events.length : 0;
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
    if (auditCount) {
      resultCopy.textContent += ` Lightning Azent 감사 기록 ${auditCount}개를 조회했습니다. 기록에는 CSV 행 내용이 없습니다.`;
    }
    const workflowStatus = response.workflow_status || "completed";
    setMessage(workflowStatus === "partial"
      ? "LA 실행은 끝났지만 사후 감사 또는 DBVORA 조회가 완료되지 않았습니다. 부분 완료입니다."
      : "실행·사후 감사·DBVORA 조회를 완료했습니다.", workflowStatus === "partial" ? "error" : "success");
    if (!response.dbvora) loadDbvora();
  } catch (error) {
    if (error.detail && error.detail.status && error.detail.run_id) {
      rememberRunId(error.detail.run_id);
      showStatus(error.detail.status);
      resultCopy.textContent = safeFailureMessage(error) + " 실행 기록에 내부 오류 유형만 저장했습니다.";
    }
    setMessage(safeFailureMessage(error), "error");
  } finally {
    updateRunButton();
    loadRecentRuns();
  }
});

refreshButton.addEventListener("click", async () => {
  if (!currentRunId) return;
  historyRunId.value = currentRunId;
  await loadRunHistory();
});

recentRunsButton.addEventListener("click", loadRecentRuns);
historyLoadButton.addEventListener("click", loadRunHistory);
historyRunId.addEventListener("input", () => {
  historyRequestVersion += 1;
  historyLoadButton.disabled = false;
  historyCopyButton.disabled = !RUN_ID_PATTERN.test(historyRunId.value.trim());
});
historyRunId.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadRunHistory();
});
historyCopyButton.addEventListener("click", async () => {
  const runId = historyRunId.value.trim();
  if (!RUN_ID_PATTERN.test(runId)) return;
  try {
    await navigator.clipboard.writeText(runId);
    historyState.textContent = "실행 ID를 복사했습니다.";
    historyState.className = "history-state success";
  } catch {
    historyState.textContent = "실행 ID 복사에 실패했습니다. 화면의 ID를 직접 선택해 복사하세요.";
    historyState.className = "history-state error";
  }
});

dbvoraRefreshButton.addEventListener("click", loadDbvora);

checkConnection();
loadDbvora();
loadRecentRuns();
restoreLastRunId();

