const form = document.querySelector("#summaryForm");
const providerSelect = document.querySelector("#provider");
const modelSelect = document.querySelector("#model");
const customModelInput = document.querySelector("#customModel");
const loadModelsButton = document.querySelector("#loadModelsButton");
const modelHint = document.querySelector("#modelHint");
const baseUrlField = document.querySelector("#baseUrlField");
const apiKeyInput = document.querySelector("input[name='api_key']");
const baseUrlInput = document.querySelector("#baseUrl");
const fileInput = document.querySelector("#file");
const uploadZone = document.querySelector(".upload-zone");
const fileName = document.querySelector("#fileName");
const statusBadge = document.querySelector("#statusBadge");
const output = document.querySelector("#summaryOutput");
const metaText = document.querySelector("#metaText");
const copyResultButton = document.querySelector("#copyResultButton");
const downloadResultButton = document.querySelector("#downloadResultButton");
const submitButton = document.querySelector("#submitButton");
const clearButton = document.querySelector("#clearButton");
const placeholderResult = "Kết quả tóm tắt sẽ hiển thị tại đây.";

const defaultModels = {
  openai: ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4.1", "gpt-4.1-mini"],
  claude: ["claude-fable-5", "claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5", "claude-3-5-haiku-latest"],
  gemini: ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-pro", "gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
  custom: ["gpt-5.4-mini", "gpt-4.1-mini", "llama-3.1-8b-instruct"],
};

function setStatus(text, state = "idle") {
  statusBadge.textContent = text;
  statusBadge.dataset.state = state;
}

function populateModels(models, hintText) {
  modelSelect.innerHTML = "";
  models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    modelSelect.appendChild(option);
  });

  const customOption = document.createElement("option");
  customOption.value = "__custom__";
  customOption.textContent = "Custom...";
  modelSelect.appendChild(customOption);

  modelHint.textContent = hintText;
  syncCustomModel();
}

function syncProviderFields() {
  const provider = providerSelect.value;
  baseUrlField.classList.toggle("is-hidden", provider !== "custom");
  populateModels(defaultModels[provider] || [], "Danh sách mặc định, có thể tải model theo API key.");
}

function syncCustomModel() {
  customModelInput.classList.toggle("is-hidden", modelSelect.value !== "__custom__");
}

function updateFileName() {
  fileName.textContent = fileInput.files[0]?.name || "Chọn file .txt, .pdf hoặc .docx";
}

function clearDropState() {
  uploadZone.classList.remove("is-dragover");
}

function hasRealSummary() {
  const text = output.textContent.trim();
  return Boolean(text) && text !== placeholderResult;
}

function syncResultActions() {
  const enabled = hasRealSummary();
  copyResultButton.disabled = !enabled;
  downloadResultButton.disabled = !enabled;
}

function applyDroppedFiles(fileList) {
  if (!fileList?.length) {
    return;
  }

  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(fileList[0]);
  fileInput.files = dataTransfer.files;
  updateFileName();
}

async function loadModels() {
  loadModelsButton.disabled = true;
  setStatus("Đang tải model", "busy");

  const body = new FormData();
  body.set("provider", providerSelect.value);
  body.set("api_key", apiKeyInput.value);
  body.set("base_url", baseUrlInput.value);

  try {
    const response = await fetch("/models", {
      method: "POST",
      body,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không tải được danh sách model.");
    }

    const sourceLabel = data.source === "live" ? "Tải trực tiếp từ provider." : "Danh sách mặc định.";
    populateModels(data.models, sourceLabel);
    setStatus("Sẵn sàng");
  } catch (error) {
    output.textContent = error.message;
    syncResultActions();
    setStatus("Có lỗi", "error");
  } finally {
    loadModelsButton.disabled = false;
  }
}

function summaryFormData() {
  const formData = new FormData(form);
  if (modelSelect.value === "__custom__") {
    formData.set("model", customModelInput.value.trim());
  }
  return formData;
}

providerSelect.addEventListener("change", syncProviderFields);
modelSelect.addEventListener("change", syncCustomModel);
loadModelsButton.addEventListener("click", loadModels);
fileInput.addEventListener("change", updateFileName);

["dragenter", "dragover"].forEach((eventName) => {
  uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.add("is-dragover");
  });
});

["dragleave", "dragend"].forEach((eventName) => {
  uploadZone.addEventListener(eventName, clearDropState);
});

uploadZone.addEventListener("drop", (event) => {
  event.preventDefault();
  clearDropState();
  applyDroppedFiles(event.dataTransfer?.files);
});

clearButton.addEventListener("click", () => {
  form.reset();
  syncProviderFields();
  clearDropState();
  updateFileName();
  metaText.textContent = "";
  output.textContent = placeholderResult;
  syncResultActions();
  setStatus("Sẵn sàng");
});

copyResultButton.addEventListener("click", async () => {
  if (!hasRealSummary()) {
    return;
  }

  try {
    await navigator.clipboard.writeText(output.textContent);
    copyResultButton.textContent = "Đã chép";
    window.setTimeout(() => {
      copyResultButton.textContent = "Sao chép";
    }, 1400);
  } catch (error) {
    output.textContent = "Không thể sao chép nội dung tóm tắt.";
    syncResultActions();
    setStatus("Có lỗi", "error");
  }
});

downloadResultButton.addEventListener("click", () => {
  if (!hasRealSummary()) {
    return;
  }

  const fileBase = (fileInput.files[0]?.name || "tom-tat")
    .replace(/\.[^.]+$/, "")
    .replace(/[^\p{L}\p{N}\-_ ]/gu, "")
    .trim()
    .replace(/\s+/g, "-");
  const blob = new Blob([output.textContent], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${fileBase || "tom-tat"}-summary.txt`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!fileInput.files.length) {
    setStatus("Thiếu file", "error");
    output.textContent = "Vui lòng chọn tài liệu trước khi tóm tắt.";
    syncResultActions();
    return;
  }

  submitButton.disabled = true;
  setStatus("Đang xử lý", "busy");
  output.textContent = "Đang trích xuất nội dung và gọi AI provider...";
  syncResultActions();
  metaText.textContent = "";

  try {
    const response = await fetch("/summarize", {
      method: "POST",
      body: summaryFormData(),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không thể tóm tắt tài liệu.");
    }

    output.textContent = data.summary;
    metaText.textContent = `${data.filename} · ${data.characters.toLocaleString("vi-VN")} ký tự`;
    syncResultActions();
    setStatus("Hoàn thành", "done");
  } catch (error) {
    output.textContent = error.message;
    syncResultActions();
    setStatus("Có lỗi", "error");
  } finally {
    submitButton.disabled = false;
  }
});

syncProviderFields();
updateFileName();
syncResultActions();
