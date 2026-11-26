function startStorageIndicator(bridge) {
  if (!bridge || !bridge.getStorageStatus) return;
  const indicator = document.getElementById("storageIndicator");
  const percent = document.getElementById("storagePct");
  const bar = document.getElementById("storageBarFill");
  if (!indicator || !percent || !bar) return;

  const gigabytes = (bytes) => (Number(bytes) / 1024 ** 3).toFixed(1) + " GB";
  function refresh() {
    bridge.getStorageStatus((raw) => {
      try {
        const data = JSON.parse(raw);
        if (!data || data.error || !data.total || !Number.isFinite(data.used_percent)) {
          throw new Error("Storage status unavailable");
        }
        const used = Math.max(0, Math.min(100, data.used_percent));
        percent.textContent = Math.round(used) + "%";
        bar.style.width = used + "%";
        indicator.title = gigabytes(data.free) + " free of " + gigabytes(data.total);
      } catch (error) {
        percent.textContent = "—";
        bar.style.width = "0%";
        indicator.title = "Storage status unavailable";
      }
    });
  }

  refresh();
  const timer = window.setInterval(refresh, 30_000);
  window.addEventListener("pagehide", () => window.clearInterval(timer), { once: true });
}
