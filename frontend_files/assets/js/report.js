
// --------- QWebChannel bridge ----------
let bridge = null;

function initWebChannel(onReady) {
    if (typeof QWebChannel !== "function") {
        onReady(null);
        return;
    }

    const MAX_TRIES = 200;
    let tries = 0;

    (function waitForQt() {
        if (window.qt && window.qt.webChannelTransport) {
            try {
                new QWebChannel(qt.webChannelTransport, function (ch) {
                    bridge = ch.objects.bridge || null;
                    onReady(bridge);
                });
            } catch (e) {
                console.error("QWebChannel init failed:", e);
                onReady && onReady(null);
            }
            return;
        }

        if (++tries > MAX_TRIES) {
            console.warn("qt not found");
            onReady && onReady(null);
            return;
        }

        setTimeout(waitForQt, 100);
    })();
}


// ---------- UI helpers ----------
const toast = (msg) => {
    const t = document.getElementById("toast");
    if (!t) { console.log("TOAST:", msg); return; }
    t.textContent = msg;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1400);
};

const el = (id) => document.getElementById(id);

function todayISO() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function toFileUrl(p) {
    if (!p) return "";
    // already http/file/qrc
    if (/^(file:|http:|https:|qrc:)/i.test(p)) return p;
    // windows path
    if (/^[a-zA-Z]:\\/.test(p)) return "file:///" + p.replace(/\\/g, "/");
    // linux absolute
    if (p.startsWith("/")) return "file://" + p;
    // relative -> keep as is (works if under static)
    return p;
}

function badge(val) {
    const v = String(val || "").toLowerCase();
    const cls = (v === "bad") ? "badge bad" : (v === "good") ? "badge good" : "badge";
    const txt = val || "—";
    return `<span class="${cls}">${txt}</span>`;
}

// ---------- state ----------
let PAGE = 0;
let LIMIT = 50;

function getFilters() {
    return {
        date_from: el("date_from").value || todayISO(),
        date_to: el("date_to").value || todayISO(),
        shift_id: el("shift_id").value || "",
        color_id: el("color_id").value || "",
        count_id: el("count_id").value || "",
        mode: el("mode").value || ""
    };
}

// ---------- backend calls ----------
async function loadFilterOptions() {
    if (!bridge || typeof bridge.reports_filter_options !== "function") return;

    const raw = await bridge.reports_filter_options();
    const data = JSON.parse(raw || "{}");

    const shiftSel = el("shift_id");
    const colorSel = el("color_id");
    const countSel = el("count_id");

    function fill(sel, arr) {
        const current = sel.value;
        sel.innerHTML = `<option value="">All</option>` + (arr || []).map(x =>
            `<option value="${x.id}">${x.name}</option>`
        ).join("");
        sel.value = current; // keep selection if any
    }

    fill(shiftSel, data.shifts);
    fill(colorSel, data.colors);
    fill(countSel, data.counts);
}

async function loadSummary() {
    if (!bridge || typeof bridge.reports_summary !== "function") return;

    const f = getFilters();
    const raw = await bridge.reports_summary(f.date_from, f.date_to, f.shift_id, f.color_id, f.count_id);
    const s = JSON.parse(raw || "{}");

    const total = Number(s.total_cones ?? 0);
    const good = Number(s.all_good ?? 0);
    const defective = total - good;
    el("k_total").textContent = total.toLocaleString();
    el("k_good").textContent = good.toLocaleString();
    el("k_defective").textContent = defective.toLocaleString();
    el("k_rate").textContent = total ? (defective / total * 100).toFixed(1) + "%" : "0%";

    const formatDate = date => new Date(date + "T00:00:00").toLocaleDateString("en-IN", {
        day: "numeric", month: "short", year: "numeric"
    });
    el("reportPeriod").textContent = f.date_from === f.date_to
        ? (f.date_from === todayISO() ? "Today" : formatDate(f.date_from))
        : formatDate(f.date_from) + " to " + formatDate(f.date_to);
    el("k_tip").textContent = String(s.tip_bad ?? 0);
    el("k_top").textContent = String(s.top_bad ?? 0);
    el("k_bottom").textContent = String(s.bottom_bad ?? 0);
    el("k_img").textContent = String(s.with_images ?? 0);
}

async function loadRows() {
    if (!bridge || typeof bridge.reports_list !== "function") {
        PAGE = 0;
        renderRows([], 0, true);
        return;
    }

    const f = getFilters();
    const offset = PAGE * LIMIT;

    const raw = await bridge.reports_list(
        f.date_from, f.date_to,
        f.shift_id, f.color_id, f.count_id,
        f.mode,
        LIMIT, offset
    );

    const rows = JSON.parse(raw || "[]");
    renderRows(rows, offset, PAGE === 0 && rows.length === 0);
}

const sampleEntries = [
    { id: "S-001", created_at: "2026-11-26 08:15", shift: "", cone_color: "White", cone_count: "30", tip: "good", top: "good", bottom: "good" },
    { id: "S-002", created_at: "2026-11-26 08:32", shift: "", cone_color: "Blue", cone_count: "40", tip: "bad", top: "good", bottom: "good" },
    { id: "S-003", created_at: "2026-11-26 09:04", shift: "", cone_color: "White", cone_count: "30", tip: "good", top: "bad", bottom: "good" },
    { id: "S-004", created_at: "2026-11-26 14:12", shift: "", cone_color: "Green", cone_count: "50", tip: "good", top: "good", bottom: "bad" },
    { id: "S-005", created_at: "2026-11-26 14:27", shift: "", cone_color: "Blue", cone_count: "40", tip: "good", top: "good", bottom: "good" }
];

function renderRows(rows, offset, showSamples = false) {
    const tbody = el("rows");
    const entries = showSamples ? sampleEntries : rows;
    const headers = tbody.closest("table").querySelectorAll("th[data-field]");
    const visibleFields = [];

    for (const header of headers) {
        const field = header.dataset.field;
        header.hidden = entries.length > 0 && field !== "id"
            && !entries.some(entry => hasFieldValue(entry[field]));
        if (!header.hidden) visibleFields.push(field);
    }

    el("btnPrev").disabled = PAGE === 0;
    el("btnNext").disabled = rows.length < LIMIT;

    if (!entries.length) {
        tbody.innerHTML = `<tr><td colspan="${visibleFields.length}" class="table-message">No inspections match these filters.</td></tr>`;
        el("resultInfo").textContent = `0 results`;
        el("pageInfo").textContent = `Page ${PAGE + 1}`;
        return;
    }

    tbody.innerHTML = entries.map(entry => {
        const cells = visibleFields.map(field => `<td>${renderEntryCell(entry, field)}</td>`);
        return `<tr>${cells.join("")}</tr>`;
    }).join("");

    // bind thumbnail clicks
    tbody.querySelectorAll(".thumb-button").forEach(button => {
        button.addEventListener("click", () => {
            previewTrigger = button;
            el("imgFull").src = button.dataset.full || "";
            el("imgTitle").textContent = button.dataset.title || "Preview";
            el("imgModal").style.display = "flex";
            el("imgClose").focus();
        });
    });

    el("resultInfo").textContent = showSamples
        ? "No live results to display. Showing 5 sample entries."
        : `Showing entries ${offset + 1} to ${offset + rows.length}`;
    el("pageInfo").textContent = `Page ${PAGE + 1}`;
}

function hasFieldValue(value) {
    const text = String(value ?? "").trim();
    return !/^(?:null|nil|nill|[-–—])?$/i.test(text);
}

function renderEntryCell(entry, field) {
    const value = entry[field];
    if (!hasFieldValue(value)) return '<span class="muted">—</span>';
    if (field === "tip" || field === "top" || field === "bottom") return badge(value);
    if (field === "img") {
        const imgUrl = toFileUrl(value);
        return `<button type="button" class="thumb-button" data-full="${imgUrl}" data-title="Inspection ${entry.id}" aria-label="Preview image for inspection ${entry.id}"><img class="thumb" src="${imgUrl}" alt="" /></button>`;
    }
    return value;
}

async function refreshAll(resetPage = false) {
    if (resetPage) PAGE = 0;
    const [summary, rows] = await Promise.allSettled([loadSummary(), loadRows()]);
    if (summary.status === "rejected") {
        console.error(summary.reason);
        toast("Report summary failed to load");
    }
    if (rows.status === "rejected") {
        console.error(rows.reason);
        PAGE = 0;
        renderRows([], 0, true);
        toast("Live inspection entries failed to load");
    }
}


let previewTrigger = null;

function closePreview() {
    el("imgModal").style.display = "none";
    el("imgFull").removeAttribute("src");
    previewTrigger?.focus();
}

// ---------- boot ----------
document.addEventListener("DOMContentLoaded", () => {
    // default dates: today
    el("date_from").value = todayISO();
    el("date_to").value = todayISO();

    el("limit").addEventListener("change", async () => {
        LIMIT = parseInt(el("limit").value || "50", 10);
        await refreshAll(true);
    });

    el("btnRefresh").addEventListener("click", () => refreshAll(true));

    el("btnDownloadPDF").addEventListener("click", async () => {
        if (!bridge || typeof bridge.openInvoiceViewer !== "function") {
            toast("Invoice export is available in the desktop app");
            return;
        }
        try {
            const error = await bridge.openInvoiceViewer();
            if (error) toast(error);
        } catch (error) {
            console.error(error);
            toast("Could not open invoice preview");
        }
    });

    el("btnApply").addEventListener("click", async () => {
        await refreshAll(true);
        toast("Applied");
    });

    el("btnPrev").addEventListener("click", async () => {
        if (PAGE <= 0) return;
        PAGE--;
        await refreshAll(false);
    });

    el("btnNext").addEventListener("click", async () => {
        PAGE++;
        await refreshAll(false);
    });

    el("imgClose").addEventListener("click", closePreview);
    el("imgModal").addEventListener("keydown", event => {
        if (event.key === "Escape") closePreview();
        if (event.key === "Tab") event.preventDefault();
    });

    // connect bridge and load
    initWebChannel(async () => {
        try {
            await loadFilterOptions();
        } catch (e) {
            console.error(e);
            toast("Report filters failed to load");
        }
        await refreshAll(true);
    });
});
