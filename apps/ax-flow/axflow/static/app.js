const taskInput = document.querySelector("#task");
const csvInput = document.querySelector("#csv-path");
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
const stepCountOutput = document.querySelector("#step-count");
const refreshButton = document.querySelector("#refresh-status");

let previewKey = "";
let currentRunId = "";
let previewId = "";

function requestKey() {
  return JSON.stringify([taskInput.value, csvInput.value]);
}

function setMessage(text, state = "") {
  message.textContent = text;
  message.className = "message" + (state ? " " + state : "");
}

function updateRunButton() {
  runButton.disabled = !previewKey || previewKey !== requestKey() || !approvalInput.checked;
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

previewButton.addEventListener("click", async () => {
  previewButton.disabled = true;
  setMessage("지원 범위와 IR을 검증하고 있습니다…");
  previewKey = "";
  previewId = "";
  updateRunButton();
  try {
    const response = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({ task: taskInput.value, csv_path: csvInput.value }),
    });
    planOutput.textContent = JSON.stringify(response.plan, null, 2);
    previewKey = requestKey();
    previewId = response.preview_id;
    setMessage("지원되는 CSV → SQLite 흐름입니다. 파일 검사는 실행 시 수행합니다.", "success");
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
    updateRunButton();
    resultCard.hidden = true;
  });
}
approvalInput.addEventListener("change", updateRunButton);

runButton.addEventListener("click", async () => {
  if (!approvalInput.checked || previewKey !== requestKey()) return;
  runButton.disabled = true;
  setMessage("합성 CSV를 검사한 뒤 로컬 SQLite에 저장합니다…");
  try {
    const response = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({
        task: taskInput.value, csv_path: csvInput.value,
        preview_id: previewId, approve_writes: true,
      }),
    });
    currentRunId = response.run_id;
    showStatus(response.status);
    rowCountOutput.textContent = String(response.result.imported_rows);
    resultCopy.textContent = response.result.imported_rows + "개 행을 이 PC의 선택된 합성 데이터 SQLite 파일에 저장했습니다.";
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

checkConnection();
