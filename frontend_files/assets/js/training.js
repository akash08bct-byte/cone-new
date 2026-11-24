let bridge = null;
let bridgeReady = false;
let liveMode = false;
let captureStage = "idle";
let captureRequest = false;
let captureRevision = 0;
let jobLookupRevision = 0;
let jobLoading = false;
let jobBlocked = false;
let activeJob = "";
let countTimer = null;
let selectedImage = "";
let galleryItems = [];
let captureSlideIndex = 0;
let captureSelectedImage = "";
let captureFolders = {};
let captureModalRevision = 0;
let galleryRevision = 0;

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
  const sessionActive = ["capturing", "stopping"].includes(captureStage);
  $("btnLiveStart").disabled = liveMode || sessionActive || captureRequest;
  $("btnLiveStop").disabled = !liveMode || captureRequest;
  $("btnStartTraining").disabled = liveMode || sessionActive || captureRequest;
  $("btnStopTraining").disabled = captureRequest || captureStage !== "capturing";
  $("btnJobSave").disabled = captureRequest || jobLoading || jobBlocked;
  $("jobSelect").disabled = captureRequest;
  $("jobIdInput").disabled = captureRequest;
  $("jobMaterial").disabled = captureRequest || jobLoading || jobBlocked;
  $("jobCount").disabled = captureRequest || jobLoading || jobBlocked;
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
  $("jobMaterial").value = "";
  $("jobCount").value = "";
  $("jobError").hidden = true;
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
    refreshCounts(job, revision);
    $("jobMaterial").value = data.material || "";
    $("jobCount").value = data.count || "";
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

async function refreshCounts(jobId = currentJob(), lookupRevision = jobLookupRevision) {
  if (captureRequest || !bridge) return;
  const revision = captureRevision;
  try {
    const raw = await callBridge("getTrainingCaptureStatus", jobId);
    const data = JSON.parse(raw || "{}");
    if (data.ok && revision === captureRevision && lookupRevision === jobLookupRevision && !captureRequest) {
      applyCaptureStatus(data);
    }
  } catch (error) {
    console.error("Count refresh failed:", error);
  }
}

function applyCaptureStatus(data) {
  const previous = captureStage;
  const previousJob = currentJob();
  captureStage = data.stage;
  if (data.job_id) setSelectedJob(data.job_id);
  const counts = [
    ["whiteCount", data.white_count],
    ["uvCount", data.uv_count],
    ["folderCount", data.white_count + data.uv_count],
  ];
  const countsChanged = counts.some(([id, count]) => $(id).textContent !== String(count));
  counts.forEach(([id, count]) => { $(id).textContent = count; });
  const phases = {
    initializing: "Initializing capture?",
    waiting: "Waiting for the next object?",
    white: "Capturing White Field image?",
    uv: "Capturing UV Light image?",
    paired: "Image pair captured successfully.",
    clear: "Waiting for the next object?",
  };
  const messages = {
    idle: "Ready to capture.",
    capturing: phases[data.phase] || phases.initializing,
    stopping: data.phase === "closing" ? "Turning off the lights?" : "Finishing the current image pair?",
    completed: `Capture stopped successfully. Job ${data.job_id}. White Field: ${data.white_count}. UV Light: ${data.uv_count}.`,
    failed: data.message || "Capture failed. Check the camera and light connection.",
  };
  $("captureStatus").textContent = messages[captureStage];
  setButtons();

  window.clearTimeout(countTimer);
  if (["capturing", "stopping"].includes(captureStage)) {
    countTimer = window.setTimeout(() => refreshCounts(), 300);
  }
  const ended = ["capturing", "stopping"].includes(previous)
    && ["completed", "failed"].includes(captureStage);
  if (ended) {
    $("previewStage").classList.remove("active");
    $("cameraFeed").removeAttribute("src");
  }
  if (countsChanged || previousJob !== currentJob() || ended || previous !== captureStage) {
    const galleryReady = refreshGallery();
    if (ended && captureStage === "completed") {
      const revision = captureRevision;
      galleryReady.then(() => {
        if (revision === captureRevision && currentJob() === data.job_id) openCaptureModal();
      });
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

async function confirmJobAndStartTraining() {
  if (captureRequest || jobLoading || jobBlocked) return;
  const typedJob = String($("jobIdInput").value || "").trim();
  const selectedJob = String($("jobSelect").value || "").trim();
  const job = selectedJob || typedJob;
  if (!/^[\p{L}\p{N}-][\p{L}\p{N}_-]*[\p{L}\p{N}-]$|^[\p{L}\p{N}-]$/u.test(job)) {
    showJobError("Enter a valid Job ID using letters, numbers, hyphens or underscores.");
    if ($("jobSelect").options.length > 1) $("jobSelect").focus();
    else $("jobIdInput").focus();
    return;
  }

  const material = $("jobMaterial").value.trim();
  const count = $("jobCount").value.trim();
  if (!material || !count) {
    showJobError("Enter a Material and Count.");
    $(material ? "jobCount" : "jobMaterial").focus();
    return;
  }
  const data = await requestCapture("startTraining", job, Boolean(selectedJob), material, count);
  if (!data.ok) {
    showJobError(data.message);
    return;
  }
  applyCaptureStatus(data);
  ensureJobOption(activeJob);
  closeJobModal();
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
  const revision = ++galleryRevision;
  const gallery = $("gallery");
  const items = jobId ? await fetchTrainingImageItems(jobId) : [];
  if (revision !== galleryRevision || jobId !== currentJob()) return;
  const previousSelection = selectedImage;
  galleryItems = items;
  selectedImage = "";
  $("btnDeleteImage").disabled = true;
  if (!items.length) {
    gallery.innerHTML = jobId ? "<p>No images found for this job.</p>" : "<p>Select a job to view images.</p>";
    return;
  }

  gallery.innerHTML = "";
  let firstButton;
  let firstFilename;
  for (const slots of groupTrainingImages(items)) {
    const row = document.createElement("div");
    row.className = "image-pair";
    for (const item of slots) {
      if (!item) {
        row.appendChild(document.createElement("span"));
        continue;
      }
      const button = document.createElement("button");
      button.className = "thumb";
      button.type = "button";
      const label = item.light === "white" ? "White Field" : item.light === "uv" ? "UV Light" : "";
      const img = document.createElement("img");
      img.loading = "lazy";
      loadTrainingPreview(img, jobId, item);
      button.appendChild(img);
      if (label) {
        const caption = document.createElement("span");
        caption.textContent = label;
        button.appendChild(caption);
      }
      button.addEventListener("click", () => selectImage(button, item.filename));
      row.appendChild(button);
      if (!firstButton) {
        firstButton = button;
        firstFilename = item.filename;
      }
      if (item.filename === previousSelection) selectImage(button, item.filename);
    }
    gallery.appendChild(row);
  }
  if (!selectedImage && firstButton) selectImage(firstButton, firstFilename);
}

function groupTrainingImages(items) {
  const groups = new Map();
  for (const item of items) {
    const basename = item.filename.split("/").pop();
    const key = item.light ? basename : item.filename;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return Array.from(groups.values(), (group) => group.some((item) => item.light)
    ? ["white", "uv"].map((light) => group.find((item) => item.light === light))
    : group);
}

function loadTrainingPreview(img, jobId, item) {
  const label = item.light === "white" ? "White Field" : item.light === "uv" ? "UV Light" : "";
  img.alt = label ? `${label} ${item.filename.split("/").pop()}` : item.filename;
  const fallback = async () => {
    img.onerror = null;
    const src = await imageDataFor(jobId, item.filename);
    if (src) img.src = src;
  };
  if (item.url) {
    img.onerror = fallback;
    img.src = item.url;
  } else {
    fallback();
  }
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
            filename: String(item.filename || ""),
            light: item.light || "",
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

function closeCaptureModal() {
  captureModalRevision += 1;
  const modal = $("captureModal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function captureSlides() {
  const items = galleryItems.map((item) => {
    const separator = item.filename.lastIndexOf("/");
    const folder = separator < 0 ? "" : item.filename.slice(0, separator);
    const light = folder && Object.keys(captureFolders).find((kind) => captureFolders[kind] === folder);
    return light ? { ...item, light } : item;
  });
  return groupTrainingImages(items.filter((item) => item.light === "white" || item.light === "uv"));
}

function renderCaptureSlide(jobId = currentJob()) {
  const slides = captureSlides();
  const total = slides.length;
  captureSlideIndex = Math.max(0, Math.min(captureSlideIndex, total - 1));
  $("captureCounter").textContent = `Pair ${total ? captureSlideIndex + 1 : 0} / ${total}`;
  $("btnCapturePrev").disabled = captureSlideIndex <= 0;
  $("btnCaptureNext").disabled = captureSlideIndex >= total - 1;
  $("btnCaptureDeleteImage").disabled = !jobId || !total;
  const slide = slides[captureSlideIndex] || [];
  if (!slide.some((item) => item && item.filename === captureSelectedImage)) {
    captureSelectedImage = slide.find(Boolean)?.filename || "";
  }

  for (const [index, light, panel, label] of [
    [0, "white", "captureWhite", "White Field"],
    [1, "uv", "captureUV", "UV Light"],
  ]) {
    const item = slide[index];
    const folderPath = galleryItems.find((entry) => entry.light === light)?.filename;
    $(panel + "Folder").textContent = captureFolders[light]
      || (folderPath ? folderPath.slice(0, folderPath.lastIndexOf("/")) : "") || "Folder unavailable";
    $(panel + "Filename").textContent = item ? item.filename.split("/").pop() : "—";
    const viewport = $(panel + "Image");
    viewport.innerHTML = "";
    if (!item) {
      const placeholder = document.createElement("p");
      placeholder.textContent = `No ${label} image for this ${total ? "pair" : "job"}.`;
      viewport.appendChild(placeholder);
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "capture-image-option";
    button.setAttribute("aria-pressed", String(item.filename === captureSelectedImage));
    const img = document.createElement("img");
    img.className = "capture-image";
    loadTrainingPreview(img, jobId, item);
    button.appendChild(img);
    button.addEventListener("click", () => {
      captureSelectedImage = item.filename;
      $("captureModal").querySelectorAll(".capture-image-option").forEach((option) => {
        option.setAttribute("aria-pressed", String(option === button));
      });
    });
    viewport.appendChild(button);
  }
}

async function openCaptureModal(jobId = currentJob()) {
  const revision = ++captureModalRevision;
  const modal = $("captureModal");
  $("btnCaptureTrainModel").disabled = !jobId;
  captureSlideIndex = 0;
  captureSelectedImage = "";
  captureFolders = {};
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  renderCaptureSlide(jobId);
  if (!jobId) return;

  try {
    const data = JSON.parse(await callBridge("getTrainingJobFolders", jobId) || "{}");
    if (data.ok && revision === captureModalRevision && jobId === currentJob()) {
      captureFolders = { white: data.white_name, uv: data.uv_name };
      renderCaptureSlide(jobId);
    }
  } catch (error) {
    console.error("Collected image folder lookup failed:", error);
  }
}

function showPreviousCaptureImage() {
  if (captureSlideIndex <= 0) return;
  captureSlideIndex -= 1;
  renderCaptureSlide();
}

function showNextCaptureImage() {
  if (captureSlideIndex >= captureSlides().length - 1) return;
  captureSlideIndex += 1;
  renderCaptureSlide();
}

async function deleteCurrentCaptureImage() {
  const job = currentJob();
  const filename = captureSelectedImage;
  if (!job || !filename) return;

  const b = await initBridge();
  if (!b || !b.deleteTrainingImage) return;

  const raw = await callBridge("deleteTrainingImage", job, filename);
  const data = JSON.parse(raw || "{}");
  if (!data.ok) {
    toast(data.message || "Delete failed");
    return;
  }

  captureSelectedImage = "";
  await refreshGallery(job);
  renderCaptureSlide(job);
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
  setButtons();

  $("btnLiveStart").addEventListener("click", startLive);
  $("btnLiveStop").addEventListener("click", stopLive);
  $("btnStartTraining").addEventListener("click", startTraining);
  $("btnStopTraining").addEventListener("click", () => changeCaptureStage("stopTraining"));
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
});
