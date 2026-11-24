let bridge = null;
let bridgeReady = false;
let liveMode = false;
const whiteFieldPrefix = "White_Field";
const uvLightPrefix = "UV_Light";
let captureStage = "idle";
let captureRequest = false;
let captureRevision = 0;
let jobLookupRevision = 0;
let jobLoading = false;
let jobBlocked = false;
let activeJob = "";
let countTimer = null;
let selectedImage = "";
let galleryImages = [];
let galleryItems = [];
let captureSlideIndex = 0;
let captureRenderToken = 0;

function $(id) {
  return document.getElementById(id);
}

function toast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  window.setTimeout(() => el.classList.remove("show"), 1500);
}

function initBridge() {
  if (bridgeReady) return Promise.resolve(bridge);

  return new Promise((resolve) => {
    if (typeof QWebChannel === "undefined" || typeof qt === "undefined") {
      resolve(null);
      return;
    }

    new QWebChannel(qt.webChannelTransport, (channel) => {
      bridge = channel.objects.bridge;
      bridgeReady = Boolean(bridge);

      if (bridgeReady && bridge.frame_signal) {
        bridge.frame_signal.connect(updateCameraFrame);
      }

      resolve(bridge);
    });
  });
}

function callBridge(methodName, ...args) {
  return new Promise((resolve) => {
    if (!bridge || !bridge[methodName]) {
      resolve(null);
      return;
    }
    bridge[methodName](...args, resolve);
  });
}

function updateCameraFrame(base64Data) {
  const img = $("cameraFeed");
  const stage = $("previewStage");
  if (!img || !stage || !base64Data) return;

  img.src = base64Data.startsWith("data:")
    ? base64Data
    : `data:image/jpeg;base64,${base64Data}`;
  stage.classList.add("active");
}

function setButtons() {
  const sessionActive = ["white", "white_stopping", "awaiting_uv", "uv", "uv_stopping"].includes(captureStage);
  $("btnLiveStart").disabled = liveMode || sessionActive || captureRequest;
  $("btnLiveStop").disabled = !liveMode || captureRequest;
  $("btnStartTraining").disabled = liveMode || sessionActive || captureRequest;
  $("btnStopTraining").disabled = captureRequest || !["white", "uv"].includes(captureStage);
  $("btnCollectUV").disabled = captureRequest || captureStage !== "awaiting_uv";
  $("btnJobSave").disabled = captureRequest || jobLoading || jobBlocked;
  $("jobSelect").disabled = captureRequest;
  $("jobIdInput").disabled = captureRequest;
  $("whiteFieldName").disabled = captureRequest || jobLoading || jobBlocked;
  $("uvLightName").disabled = captureRequest || jobLoading || jobBlocked;
  document.querySelectorAll(".sidebar-btn").forEach((button) => {
    button.disabled = sessionActive || captureRequest;
  });
}

function currentJob() {
  return String(activeJob || "").trim();
}

function ensureJobOption(jobId) {
  const select = $("jobSelect");
  const safeJob = String(jobId || "").trim();
  if (!safeJob || !select) return;

  if (!Array.from(select.options).some((option) => option.value === safeJob)) {
    const option = document.createElement("option");
    option.value = safeJob;
    option.textContent = safeJob;
    select.appendChild(option);
  }

  select.value = safeJob;
}

function openJobModal() {
  const modal = $("jobModal");
  const input = $("jobIdInput");
  const select = $("jobSelect");
  select.value = activeJob || "";
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  loadJobFolders(select.value);
  window.setTimeout(() => {
    if (select.options.length > 1) select.focus();
    else input.focus();
  }, 0);
}

function closeJobModal() {
  if (captureRequest) return;
  jobLookupRevision += 1;
  const modal = $("jobModal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

async function loadJobFolders(job) {
  const revision = ++jobLookupRevision;
  const jobInput = $("jobIdInput");
  jobInput.value = job;
  jobInput.readOnly = Boolean(job);
  $("whiteFieldName").value = job ? "" : whiteFieldPrefix;
  $("uvLightName").value = job ? "" : uvLightPrefix;
  $("jobError").hidden = true;
  $("jobFolderHint").hidden = true;
  jobBlocked = false;
  jobLoading = Boolean(job);
  setButtons();
  if (!job) return;

  let data;
  try {
    data = JSON.parse(await callBridge("getTrainingJobFolders", job) || "{}");
  } catch (error) {
    data = {};
  }
  if (revision !== jobLookupRevision) return;

  jobLoading = false;
  jobBlocked = !data.ok;
  if (data.ok) {
    $("whiteFieldName").value = data.white_name;
    $("uvLightName").value = data.uv_name;
    if (data.message) {
      $("jobFolderHint").textContent = data.message;
      $("jobFolderHint").hidden = false;
    }
  } else {
    showJobError(data.message || "Unable to load the saved job folders.");
  }
  setButtons();
}

function setSelectedJob(jobId) {
  activeJob = String(jobId || "").trim();
  const label = $("selectedJobText");
  if (label) {
    label.textContent = activeJob || "Not selected";
  }
}

async function refreshCounts(jobId = currentJob()) {
  if (captureRequest || !bridge) return;
  const revision = captureRevision;
  try {
    const raw = await callBridge("getTrainingCaptureStatus", jobId);
    const data = JSON.parse(raw || "{}");
    if (data.ok && revision === captureRevision && !captureRequest) applyCaptureStatus(data);
  } catch (error) {
    console.error("Count refresh failed:", error);
  }
}

function applyCaptureStatus(data) {
  const previous = captureStage;
  captureStage = data.stage;
  if (data.job_id) setSelectedJob(data.job_id);
  $("whiteCount").textContent = data.white_count;
  $("uvCount").textContent = data.uv_count;
  $("folderCount").textContent = data.folder_count;
  const messages = {
    idle: "Ready to capture.",
    white: "Collecting White Field images…",
    white_stopping: "Saving the last White Field image…",
    awaiting_uv: "Switch the lighting, then click Collect UV Images.",
    uv: "Collecting UV Light images…",
    uv_stopping: "Saving the last UV Light image…",
    completed: `Job ${data.job_id} completed. White Field: ${data.white_count}. UV Light: ${data.uv_count}.`,
    failed: data.message || "Capture failed.",
  };
  if ($("captureStatus").textContent !== messages[captureStage]) {
    $("captureStatus").textContent = messages[captureStage];
  }
  setButtons();

  window.clearTimeout(countTimer);
  if (["white", "white_stopping", "uv", "uv_stopping"].includes(captureStage)) {
    countTimer = window.setTimeout(() => refreshCounts(), 500);
  }
  if (captureStage !== previous && ["awaiting_uv", "completed", "failed"].includes(captureStage)) {
    const galleryReady = refreshGallery();
    if (captureStage !== "awaiting_uv") {
      $("previewStage").classList.remove("active");
      $("cameraFeed").removeAttribute("src");
      if (captureStage === "completed" && ["uv", "uv_stopping"].includes(previous)) {
        const revision = captureRevision;
        galleryReady.then(() => {
          if (revision === captureRevision) openCaptureModal();
        });
      }
    }
  }
}

async function startLive() {
  const b = await initBridge();
  if (!b || !b.startCamera) {
    toast("Bridge not connected");
    return;
  }

  const result = await callBridge("startCamera");
  if (result !== "ok" && result !== "already_running") {
    toast("Unable to start the camera");
    return;
  }
  liveMode = true;
  setButtons();
  toast("Live camera started");
}

async function stopLive() {
  const b = await initBridge();
  if (b && b.stopCamera) {
    await callBridge("stopCamera");
  }

  liveMode = false;
  $("previewStage").classList.remove("active");
  $("cameraFeed").removeAttribute("src");
  setButtons();
  toast("Live camera stopped");
}

function startTraining() {
  openJobModal();
}

function normalizeFolderInput(id, prefix) {
  const input = $(id);
  const name = input.value.trim();
  if (!name || name.endsWith(".") || /[<>:"/\\|?*\x00-\x1f]/.test(name)
    || /^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$/i.test(name.split(".")[0].trimEnd())) {
    input.value = name;
    return null;
  }

  const hasPrefix = name.slice(0, prefix.length).toLowerCase() === prefix.toLowerCase();
  const suffix = (hasPrefix ? name.slice(prefix.length) : name).replace(/^[_\s]+/, "");
  input.value = suffix ? prefix + "_" + suffix : prefix;
  return input.value;
}

async function confirmJobAndStartTraining() {
  if (captureRequest || jobLoading || jobBlocked) return;
  const typedJob = String($("jobIdInput").value || "").trim();
  const selectedJob = String($("jobSelect").value || "").trim();
  const job = selectedJob || typedJob;
  if (!job) {
    showJobError("Choose or enter a Job ID.");
    if ($("jobSelect").options.length > 1) $("jobSelect").focus();
    else $("jobIdInput").focus();
    return;
  }

  const white = normalizeFolderInput("whiteFieldName", whiteFieldPrefix);
  const uv = normalizeFolderInput("uvLightName", uvLightPrefix);
  if (!white || !uv) {
    showJobError("Enter valid White Field and UV Light folder names.");
    return;
  }
  const data = await requestCapture("startTraining", job, Boolean(selectedJob), white, uv);
  if (!data.ok) {
    showJobError(data.message);
    return;
  }
  applyCaptureStatus(data);
  ensureJobOption(activeJob);
  closeJobModal();
  refreshGallery();
}

function showJobError(message) {
  $("jobError").textContent = message;
  $("jobError").hidden = false;
}

async function requestCapture(method, ...args) {
  captureRevision += 1;
  captureRequest = true;
  window.clearTimeout(countTimer);
  setButtons();
  try {
    const result = JSON.parse(await callBridge(method, ...args) || "{}");
    return result.ok ? result : { ok: false, message: result.message || "Capture controls are unavailable." };
  } catch (error) {
    return { ok: false, message: "Unable to communicate with the training camera." };
  } finally {
    captureRequest = false;
    setButtons();
  }
}

async function changeCaptureStage(method) {
  if (captureRequest) return;
  const data = await requestCapture(method);
  if (data.ok) applyCaptureStatus(data);
  else {
    toast(data.message);
    refreshCounts();
  }
}

async function refreshJobs() {
  const select = $("jobSelect");
  const current = activeJob;
  select.innerHTML = '<option value="">Create new job</option>';

  const b = await initBridge();
  if (!b || !b.training_job_options) return;

  try {
    const raw = await callBridge("training_job_options");
    const data = JSON.parse(raw || "[]");
    const jobs = new Set(activeJob ? [activeJob] : []);
    data.forEach((job) => {
      const jobId = String(job.job_id || "").trim();
      if (jobId) jobs.add(jobId);
    });

    jobs.forEach((jobId) => {
      const option = document.createElement("option");
      option.value = jobId;
      option.textContent = jobId;
      select.appendChild(option);
    });

    if (current && Array.from(select.options).some((option) => option.value === current)) {
      select.value = current;
    }
  } catch (error) {
    console.error("Job refresh failed:", error);
  }
}

async function refreshGallery(jobId = currentJob()) {
  const gallery = $("gallery");
  galleryImages = [];
  galleryItems = [];
  selectedImage = "";
  $("btnDeleteImage").disabled = true;

  if (!jobId) {
    gallery.innerHTML = "<p>Select a job to view images.</p>";
    return;
  }

  galleryItems = await fetchTrainingImageItems(jobId);
  galleryImages = galleryItems.map((item) => item.filename);

  if (!galleryImages.length) {
    gallery.innerHTML = "<p>No images found for this job.</p>";
    return;
  }

  gallery.innerHTML = "";
  galleryItems.forEach(async (item, index) => {
    const button = document.createElement("button");
    button.className = "thumb";
    button.type = "button";
    button.innerHTML = `<img alt="">`;
    button.addEventListener("click", () => selectImage(button, item.filename));
    gallery.appendChild(button);

    if (index === 0) {
      selectImage(button, item.filename);
    }

    const img = button.querySelector("img");
    img.src = item.url || await imageDataFor(jobId, item.filename);
  });
}

async function fetchTrainingImageItems(jobId) {
  const b = await initBridge();

  if (b && b.getTrainingImageItems) {
    try {
      const raw = await callBridge("getTrainingImageItems", jobId);
      const data = JSON.parse(raw || "{}");
      if (data.ok && Array.isArray(data.items)) {
        return data.items
          .map((item) => ({
            filename: String(item.filename || "").trim(),
            url: String(item.url || "").trim(),
          }))
          .filter((item) => item.filename);
      }
    } catch (error) {
      console.error("Training image items failed:", error);
    }
  }

  const names = await fetchTrainingImageNames(jobId);
  return names.map((filename) => ({ filename, url: "" }));
}

async function fetchTrainingImageNames(jobId) {
  const b = await initBridge();
  if (!b || !b.getTrainingImageFilenames) return [];

  try {
    const raw = await callBridge("getTrainingImageFilenames", jobId);
    const data = JSON.parse(raw || "{}");
    return data.ok ? data.filenames || [] : [];
  } catch (error) {
    console.error("Training image names failed:", error);
    return [];
  }
}

function selectImage(button, filename) {
  document.querySelectorAll(".thumb.active").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  selectedImage = filename;
  $("btnDeleteImage").disabled = false;
}

async function imageDataFor(jobId, filename) {
  try {
    const imageRaw = await Promise.race([
      callBridge("getTrainingImage", jobId, filename),
      new Promise((resolve) => window.setTimeout(() => resolve(null), 8000)),
    ]);
    const imageData = JSON.parse(imageRaw || "{}");
    return imageData.ok ? imageData.data || "" : "";
  } catch (error) {
    console.error("Training image load failed:", error);
    return "";
  }
}

async function imageSrcFor(jobId, filename) {
  const item = galleryItems.find((entry) => entry.filename === filename);
  if (item && item.url) return item.url;

  if (bridge && bridge.getTrainingImageUrl) {
    try {
      const raw = await Promise.race([
        callBridge("getTrainingImageUrl", jobId, filename),
        new Promise((resolve) => window.setTimeout(() => resolve(null), 4000)),
      ]);
      const data = JSON.parse(raw || "{}");
      if (data.ok && data.url) return data.url;
    } catch (error) {
      console.error("Training image URL failed:", error);
    }
  }

  return imageDataFor(jobId, filename);
}

function closeCaptureModal() {
  const modal = $("captureModal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

async function renderCaptureSlide(jobId = currentJob()) {
  const renderToken = ++captureRenderToken;
  const gallery = $("captureGallery");
  const counter = $("captureCounter");
  const prev = $("btnCapturePrev");
  const next = $("btnCaptureNext");
  const deleteButton = $("btnCaptureDeleteImage");
  const safeJob = String(jobId || "").trim();
  const total = galleryImages.length;

  captureSlideIndex = Math.max(0, Math.min(captureSlideIndex, Math.max(0, total - 1)));
  counter.textContent = `${total ? captureSlideIndex + 1 : 0} / ${total}`;
  prev.disabled = total <= 1 || captureSlideIndex <= 0;
  next.disabled = total <= 1 || captureSlideIndex >= total - 1;
  deleteButton.disabled = !safeJob || !total;

  if (!safeJob || !total) {
    gallery.innerHTML = "<p>No images found for this job.</p>";
    return;
  }

  const hasImage = Boolean(gallery.querySelector(".capture-image"));
  if (!hasImage) {
    gallery.innerHTML = "<p>Loading image...</p>";
  }

  const data = await imageSrcFor(safeJob, galleryImages[captureSlideIndex]);
  if (!data) {
    if (!hasImage) {
      gallery.innerHTML = "<p>Unable to load image.</p>";
    }
    return;
  }

  if (renderToken !== captureRenderToken) return;

  const img = document.createElement("img");
  img.className = "capture-image";
  img.alt = "";
  img.onerror = () => {
    if (renderToken !== captureRenderToken) return;
    gallery.innerHTML = "<p>Unable to load image.</p>";
  };
  img.src = data;
  gallery.innerHTML = "";
  gallery.appendChild(img);
}

async function openCaptureModal(jobId = currentJob()) {
  const modal = $("captureModal");
  const gallery = $("captureGallery");
  const trainButton = $("btnCaptureTrainModel");
  const safeJob = String(jobId || "").trim();

  trainButton.disabled = !safeJob;
  gallery.innerHTML = "<p>Loading images...</p>";
  captureSlideIndex = 0;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");

  galleryItems = safeJob ? await fetchTrainingImageItems(safeJob) : [];
  galleryImages = galleryItems.map((item) => item.filename);
  await renderCaptureSlide(safeJob);
}

async function showPreviousCaptureImage() {
  if (captureSlideIndex <= 0) return;
  captureSlideIndex -= 1;
  await renderCaptureSlide(currentJob());
}

async function showNextCaptureImage() {
  if (captureSlideIndex >= galleryImages.length - 1) return;
  captureSlideIndex += 1;
  await renderCaptureSlide(currentJob());
}

async function deleteCurrentCaptureImage() {
  const job = currentJob();
  const filename = galleryImages[captureSlideIndex];
  if (!job || !filename) return;

  const b = await initBridge();
  if (!b || !b.deleteTrainingImage) return;

  const raw = await callBridge("deleteTrainingImage", job, filename);
  const data = JSON.parse(raw || "{}");
  if (!data.ok) {
    toast(data.message || "Delete failed");
    return;
  }

  galleryImages.splice(captureSlideIndex, 1);
  galleryItems.splice(captureSlideIndex, 1);
  if (captureSlideIndex >= galleryImages.length) {
    captureSlideIndex = Math.max(0, galleryImages.length - 1);
  }

  selectedImage = "";
  await renderCaptureSlide(job);
  await refreshGallery(job);
  await refreshCounts(job);
  toast(data.message || "Image deleted");
}

async function deleteSelectedImage() {
  const job = currentJob();
  if (!job || !selectedImage) return;

  const b = await initBridge();
  if (!b || !b.deleteTrainingImage) return;

  const raw = await callBridge("deleteTrainingImage", job, selectedImage);
  const data = JSON.parse(raw || "{}");
  toast(data.message || (data.ok ? "Image deleted" : "Delete failed"));
  await refreshGallery(job);
  await refreshCounts(job);
}

async function trainModel() {
  const job = currentJob();
  if (!job) {
    toast("Select a Job ID");
    return;
  }

  const b = await initBridge();
  if (!b || !b.startModelTraining) {
    toast("Model training is not available");
    return;
  }

  const raw = await callBridge("startModelTraining", job);
  const data = JSON.parse(raw || "{}");
  toast(data.message || "Model training request sent");
}

function openHomePage() {
  if (bridge && bridge.showHome) bridge.showHome();
}

function openReportPage() {
  if (bridge && bridge.showReport) bridge.showReport();
}

function openControllerPage() {
  if (bridge && bridge.showController) bridge.showController();
}

function openTrainingPage() {
  if (bridge && bridge.showTraining) bridge.showTraining();
}

function openSettingPage() {
  if (bridge && bridge.showSetting) bridge.showSetting();
}

window.addEventListener("load", async () => {
  await initBridge();
  await refreshCounts();
  await refreshJobs();
  if (activeJob && captureStage !== "completed") await refreshGallery();
  setButtons();

  $("btnLiveStart").addEventListener("click", startLive);
  $("btnLiveStop").addEventListener("click", stopLive);
  $("btnStartTraining").addEventListener("click", startTraining);
  $("btnStopTraining").addEventListener("click", () => changeCaptureStage("stopTraining"));
  $("btnCollectUV").addEventListener("click", () => changeCaptureStage("startTrainingUV"));
  $("btnDeleteImage").addEventListener("click", deleteSelectedImage);
  $("btnCaptureTrainModel").addEventListener("click", trainModel);
  $("btnCaptureModalClose").addEventListener("click", closeCaptureModal);
  $("btnCapturePrev").addEventListener("click", showPreviousCaptureImage);
  $("btnCaptureNext").addEventListener("click", showNextCaptureImage);
  $("btnCaptureDeleteImage").addEventListener("click", deleteCurrentCaptureImage);
  $("captureModal").addEventListener("click", (event) => {
    if (event.target === $("captureModal")) closeCaptureModal();
  });
  $("btnJobSave").addEventListener("click", confirmJobAndStartTraining);
  $("btnJobCancel").addEventListener("click", closeJobModal);
  $("btnJobModalClose").addEventListener("click", closeJobModal);
  $("jobModal").addEventListener("click", (event) => {
    if (event.target === $("jobModal")) closeJobModal();
  });
  $("jobModal").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.target.matches("input")) confirmJobAndStartTraining();
  });
  $("jobSelect").addEventListener("change", (event) => {
    loadJobFolders(event.target.value);
  });
  $("whiteFieldName").addEventListener("blur", () => normalizeFolderInput("whiteFieldName", whiteFieldPrefix));
  $("uvLightName").addEventListener("blur", () => normalizeFolderInput("uvLightName", uvLightPrefix));
});
