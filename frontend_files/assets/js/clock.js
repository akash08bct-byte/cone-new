(() => {
  const date = document.getElementById("dateValue");
  const time = document.getElementById("timeValue");
  if (!date || !time) return;

  const dateFormat = new Intl.DateTimeFormat("en-IN", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
  const timeFormat = new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
  function updateClock() {
    const now = new Date();
    date.textContent = dateFormat.format(now);
    time.textContent = timeFormat.format(now);
  }

  updateClock();
  const timer = window.setInterval(updateClock, 1000);
  window.addEventListener("pagehide", () => window.clearInterval(timer), { once: true });
})();
