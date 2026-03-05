const API_BASE = "/api/v1";

let activeCategory = "";
let activeSeverity = "";
let searchQuery = "";
let debounceTimer = null;

// --- Init ---
document.addEventListener("DOMContentLoaded", () => {
    setupChips("category-chips", (val) => { activeCategory = val; loadEvents(); });
    setupChips("severity-chips", (val) => { activeSeverity = val; loadEvents(); });

    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = searchInput.value.trim();
            loadEvents();
        }, 300);
    });

    loadEvents();
    loadStats();
    setInterval(loadStats, 5 * 60 * 1000);
});

// --- Chip setup ---
function setupChips(containerId, onChange) {
    const container = document.getElementById(containerId);
    container.addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        container.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        onChange(chip.dataset.value);
    });
}

// --- Load events ---
async function loadEvents() {
    const params = new URLSearchParams();
    if (activeCategory) params.set("category", activeCategory);
    if (activeSeverity) params.set("severity", activeSeverity);
    if (searchQuery) params.set("q", searchQuery);
    params.set("limit", "100");

    const grid = document.getElementById("event-grid");
    try {
        const resp = await fetch(`${API_BASE}/events?${params}`);
        const events = await resp.json();
        renderCards(events);
    } catch (err) {
        grid.innerHTML = `<p class="loading">Failed to load events.</p>`;
    }
}

// --- Load related events for a card ---
async function loadRelated(eventId) {
    const panel = document.getElementById(`related-${CSS.escape(eventId)}`);
    if (!panel) return;

    if (panel.style.display === "block") {
        panel.style.display = "none";
        return;
    }

    panel.innerHTML = "Loading...";
    panel.style.display = "block";

    try {
        const resp = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}/related`);
        const related = await resp.json();
        if (!related.length) {
            panel.innerHTML = `<span class="related-empty">No related events</span>`;
            return;
        }
        panel.innerHTML = related.map(ev =>
            `<a class="related-link" href="#" onclick="event.preventDefault(); loadEvents()">${escapeHtml(ev.name)} <span class="meta-tag category">${ev.category}</span></a>`
        ).join("");
    } catch {
        panel.innerHTML = `<span class="related-empty">Failed to load</span>`;
    }
}

// --- Render cards ---
function renderCards(events) {
    const grid = document.getElementById("event-grid");

    if (!events.length) {
        grid.innerHTML = `<p class="loading">No events found.</p>`;
        return;
    }

    grid.innerHTML = events.map(ev => {
        const dateStr = ev.start_date ? formatDate(ev.start_date) : "";
        const locationStr = ev.location || "";
        const metaParts = [];

        metaParts.push(`<span class="meta-tag category">${ev.category}</span>`);
        metaParts.push(`<span class="meta-tag severity severity-${ev.severity}">${ev.severity}</span>`);
        if (ev.subcategory) metaParts.push(`<span class="meta-tag">${ev.subcategory}</span>`);
        if (locationStr) metaParts.push(`<span class="meta-tag">${locationStr}</span>`);
        if (dateStr) metaParts.push(`<span class="meta-tag">${dateStr}</span>`);

        const sourceLink = ev.source_url
            ? `<a class="source-link" href="${escapeHtml(ev.source_url)}" target="_blank" rel="noopener">Source</a>`
            : "";

        const escapedId = escapeAttr(ev.id);

        return `
        <div class="event-card severity-${ev.severity}">
            <div class="card-header">
                <span class="event-name">${escapeHtml(ev.name)}</span>
                <span class="importance-badge">${Math.round(ev.importance)}</span>
            </div>
            ${ev.summary ? `<p class="event-summary">${escapeHtml(ev.summary)}</p>` : ""}
            <div class="event-meta">${metaParts.join("")}</div>
            <div class="card-actions">
                ${sourceLink}
                <button class="related-btn" onclick="loadRelated('${escapedId}')">Related</button>
            </div>
            <div class="related-panel" id="related-${escapedId}" style="display:none"></div>
        </div>`;
    }).join("");
}

// --- Load stats ---
async function loadStats() {
    try {
        const resp = await fetch(`${API_BASE}/stats`);
        const stats = await resp.json();

        const bar = document.getElementById("stats-bar");
        const parts = [
            `<span class="stat-item"><strong>${stats.total_events}</strong> events</span>`,
            `<span class="stat-item"><strong>${stats.total_entities}</strong> entities</span>`,
            `<span class="stat-item"><strong>${stats.total_relations}</strong> relations</span>`,
        ];
        for (const [cat, count] of Object.entries(stats.by_category)) {
            parts.push(`<span class="stat-item">${capitalize(cat)}: <strong>${count}</strong></span>`);
        }
        bar.innerHTML = parts.join("");

        document.getElementById("last-updated").textContent = `Updated: ${new Date().toLocaleTimeString()}`;
    } catch (err) {
        // Silently fail stats refresh
    }
}

// --- Helpers ---
function formatDate(isoStr) {
    try {
        const d = new Date(isoStr);
        return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    } catch {
        return isoStr;
    }
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
