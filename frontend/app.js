const API_BASE = "/api/v1";

let activeCategory = "";
let activeSeverity = "";
let activeLocation = "";
let searchQuery = "";
let activeView = "cards";
let calendarYear, calendarMonth;
let debounceTimer = null;

// --- Init ---
document.addEventListener("DOMContentLoaded", () => {
    const now = new Date();
    calendarYear = now.getFullYear();
    calendarMonth = now.getMonth();

    setupChips("category-chips", (val) => { activeCategory = val; refresh(); });
    setupChips("severity-chips", (val) => { activeSeverity = val; refresh(); });
    setupChips("view-chips", (val) => {
        activeView = val;
        document.getElementById("event-grid").style.display = val === "cards" ? "" : "none";
        document.getElementById("calendar-container").style.display = val === "calendar" ? "" : "none";
        document.getElementById("trending-container").style.display = val === "trending" ? "" : "none";
        refresh();
    });

    document.getElementById("cal-prev").addEventListener("click", () => {
        calendarMonth--;
        if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
        loadCalendar();
    });
    document.getElementById("cal-next").addEventListener("click", () => {
        calendarMonth++;
        if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
        loadCalendar();
    });

    const locationSelect = document.getElementById("location-select");
    locationSelect.addEventListener("change", () => {
        activeLocation = locationSelect.value;
        refresh();
    });

    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = searchInput.value.trim();
            refresh();
        }, 300);
    });

    // Close day modal when clicking outside
    const dayModal = document.getElementById("day-modal");
    dayModal.addEventListener("click", (e) => {
        if (e.target === dayModal) {
            closeDayModal();
        }
    });

    loadLocations();
    refresh();
    loadStats();
    setInterval(loadStats, 5 * 60 * 1000);
});

function refresh() {
    if (activeView === "cards") loadEvents();
    else if (activeView === "calendar") loadCalendar();
    else if (activeView === "trending") loadTrending();
}

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

// --- Load locations for dropdown ---
async function loadLocations() {
    try {
        const resp = await fetch(`${API_BASE}/locations`);
        const locations = await resp.json();
        const select = document.getElementById("location-select");
        for (const loc of locations) {
            const opt = document.createElement("option");
            opt.value = loc;
            opt.textContent = loc;
            select.appendChild(opt);
        }
    } catch { /* silently fail */ }
}

// --- Load events (card view) ---
async function loadEvents() {
    const params = new URLSearchParams();
    if (activeCategory) params.set("category", activeCategory);
    if (activeSeverity) params.set("severity", activeSeverity);
    if (activeLocation) params.set("location", activeLocation);
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

// --- Load related events ---
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
        panel.innerHTML = related.map(ev => {
            const catTags = (ev.categories || []).map(c =>
                `<span class="meta-tag category cat-${c}">${c}</span>`
            ).join("");
            return `<a class="related-link" href="#" onclick="event.preventDefault()">${escapeHtml(ev.name)} ${catTags}</a>`;
        }).join("");
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
        const cats = ev.categories || [];
        const metaParts = [];

        // Render all category tags
        for (const cat of cats) {
            metaParts.push(`<span class="meta-tag category cat-${cat}">${cat}</span>`);
        }
        metaParts.push(`<span class="meta-tag severity severity-${ev.severity}">${ev.severity}</span>`);
        if (ev.subcategory) metaParts.push(`<span class="meta-tag">${ev.subcategory}</span>`);
        if (locationStr) metaParts.push(`<span class="meta-tag">${locationStr}</span>`);
        if (dateStr) metaParts.push(`<span class="meta-tag">${dateStr}</span>`);

        const sourceLink = ev.source_url
            ? `<a class="source-link" href="${escapeHtml(ev.source_url)}" target="_blank" rel="noopener">Source</a>`
            : "";

        const escapedId = escapeAttr(ev.id);

        // Use first category for the card border color
        const primaryCat = cats[0] || "situation";

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

// --- Calendar view ---
async function loadCalendar() {
    const label = document.getElementById("cal-month-label");
    const monthNames = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    label.textContent = `${monthNames[calendarMonth]} ${calendarYear}`;

    // Get first/last day of month for timeline query
    const startDate = `${calendarYear}-${String(calendarMonth + 1).padStart(2, "0")}-01`;
    const lastDay = new Date(calendarYear, calendarMonth + 1, 0).getDate();
    const endDate = `${calendarYear}-${String(calendarMonth + 1).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;

    let events = [];
    try {
        const params = new URLSearchParams({ start: startDate, end: endDate });
        const resp = await fetch(`${API_BASE}/timeline?${params}`);
        events = await resp.json();
    } catch {
        events = [];
    }

    // Filter by active category/severity/location
    if (activeCategory) events = events.filter(e => (e.categories || []).includes(activeCategory));
    if (activeSeverity) events = events.filter(e => e.severity === activeSeverity);
    if (activeLocation) events = events.filter(e => (e.location || "").includes(activeLocation));
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        events = events.filter(e =>
            (e.name || "").toLowerCase().includes(q) || (e.summary || "").toLowerCase().includes(q)
        );
    }

    // Group events by day
    const eventsByDay = {};
    for (const ev of events) {
        const sd = ev.start_date || "";
        if (!sd) continue;
        const day = parseInt(sd.substring(8, 10), 10);
        if (!eventsByDay[day]) eventsByDay[day] = [];
        eventsByDay[day].push(ev);
    }

    renderCalendar(lastDay, eventsByDay);
}

// Store calendar events globally so we can access them from click handlers
let calendarEventsByDay = {};

function renderCalendar(daysInMonth, eventsByDay) {
    const grid = document.getElementById("calendar-grid");
    const firstDow = new Date(calendarYear, calendarMonth, 1).getDay();
    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    // Store events globally for access in click handlers
    calendarEventsByDay = eventsByDay;

    let html = dayNames.map(d => `<div class="cal-header">${d}</div>`).join("");

    // Empty cells before first day
    for (let i = 0; i < firstDow; i++) {
        html += `<div class="cal-cell empty"></div>`;
    }

    const today = new Date();
    const isCurrentMonth = today.getFullYear() === calendarYear && today.getMonth() === calendarMonth;

    for (let day = 1; day <= daysInMonth; day++) {
        const dayEvents = eventsByDay[day] || [];
        const isToday = isCurrentMonth && today.getDate() === day;
        const hasEvents = dayEvents.length > 0;

        let cellClass = "cal-cell";
        if (isToday) cellClass += " today";
        if (hasEvents) cellClass += " has-events clickable";

        let eventsHtml = "";
        for (const ev of dayEvents.slice(0, 3)) {
            const primaryCat = (ev.categories || [])[0] || "situation";
            eventsHtml += `<div class="cal-event cat-${primaryCat} severity-${ev.severity}" title="${escapeHtml(ev.summary || ev.name)}">${escapeHtml(ev.name)}</div>`;
        }
        if (dayEvents.length > 3) {
            eventsHtml += `<div class="cal-more">+${dayEvents.length - 3} more</div>`;
        }

        const clickHandler = hasEvents ? `onclick="expandDay(${day})"` : "";
        html += `<div class="${cellClass}" ${clickHandler}><span class="cal-day-num">${day}</span>${eventsHtml}</div>`;
    }

    grid.innerHTML = html;
}

function expandDay(day) {
    const events = calendarEventsByDay[day] || [];
    if (events.length === 0) return;

    const monthNames = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    const dateStr = `${monthNames[calendarMonth]} ${day}, ${calendarYear}`;

    const modal = document.getElementById("day-modal");
    document.getElementById("day-modal-title").textContent = dateStr;

    const eventsContainer = document.getElementById("day-modal-events");
    eventsContainer.innerHTML = events.map(ev => {
        const cats = ev.categories || [];
        const catTags = cats.map(c =>
            `<span class="meta-tag category cat-${c}">${c}</span>`
        ).join("");
        const sourceLink = ev.source_url
            ? `<a class="source-link" href="${escapeHtml(ev.source_url)}" target="_blank" rel="noopener">Source</a>`
            : "";

        return `
        <div class="day-event-card severity-${ev.severity}">
            <div class="day-event-header">
                <h4>${escapeHtml(ev.name)}</h4>
                <span class="importance-badge">${Math.round(ev.importance)}</span>
            </div>
            ${ev.summary ? `<p class="day-event-summary">${escapeHtml(ev.summary)}</p>` : ""}
            <div class="day-event-meta">
                ${catTags}
                <span class="meta-tag severity severity-${ev.severity}">${ev.severity}</span>
                ${ev.subcategory ? `<span class="meta-tag">${ev.subcategory}</span>` : ""}
                ${ev.location ? `<span class="meta-tag">${ev.location}</span>` : ""}
            </div>
            <div class="day-event-actions">
                ${sourceLink}
            </div>
        </div>`;
    }).join("");

    modal.style.display = "flex";
}

function renderEditingSuggestion(s) {
    const chips = [];

    if (s.filterPreset && s.filterPreset !== "none")
        chips.push(`<span class="edit-chip filter">${s.filterPreset}</span>`);

    if (Array.isArray(s.effects))
        s.effects.forEach(e => chips.push(`<span class="edit-chip effect">${e.name}</span>`));

    if (s.speed !== undefined && s.speed !== 1)
        chips.push(`<span class="edit-chip playback">${s.speed}x speed</span>`);

    if (s.vignette === true)
        chips.push(`<span class="edit-chip effect">vignette</span>`);

    const ca = s.colorAdjustments || {};
    if (ca.brightness !== undefined && ca.brightness !== 0)
        chips.push(`<span class="edit-chip color">brightness ${ca.brightness > 0 ? "+" : ""}${ca.brightness}</span>`);
    if (ca.saturation !== undefined && ca.saturation !== 1)
        chips.push(`<span class="edit-chip color">saturation ${ca.saturation}</span>`);
    if (ca.contrast !== undefined && ca.contrast !== 1)
        chips.push(`<span class="edit-chip color">contrast ${ca.contrast}</span>`);

    const texts = s.textLayers || [];
    texts.forEach(t => chips.push(`<span class="edit-chip text">"${t.text}"</span>`));

    if (!chips.length) return "";

    return `<div class="editing-suggestion">
        <span class="editing-suggestion-label">Editing</span>
        <div class="edit-chips">${chips.join("")}</div>
    </div>`;
}

function closeDayModal() {
    document.getElementById("day-modal").style.display = "none";
}

// --- Trending view ---
async function loadTrending() {
    const grid = document.getElementById("trending-grid");
    grid.innerHTML = `<p class="loading">Analyzing events with Gemini...</p>`;

    try {
        const resp = await fetch(`${API_BASE}/trending?max_count=10`);
        const events = await resp.json();
        renderTrending(events);
    } catch (err) {
        grid.innerHTML = `<p class="loading">Failed to load trending events.</p>`;
    }
}

function renderTrending(events) {
    const grid = document.getElementById("trending-grid");

    if (!events.length) {
        grid.innerHTML = `<p class="loading">No trending events found.</p>`;
        return;
    }

    grid.innerHTML = events.map((ev, i) => {
        const cats = ev.categories || [];
        const catTags = cats.map(c =>
            `<span class="meta-tag category cat-${c}">${c}</span>`
        ).join("");

        const dateStr = ev.start_date ? formatDate(ev.start_date) : "";
        const sourceLink = ev.source_url
            ? `<a class="source-link" href="${escapeHtml(ev.source_url)}" target="_blank" rel="noopener">Source</a>`
            : "";

        const scoreDots = Array.from({length: 10}, (_, j) =>
            `<span class="score-dot ${j < ev.virality_score ? 'active' : ''}"></span>`
        ).join("");

        return `
        <div class="trending-card">
            <div class="trending-rank">#${i + 1}</div>
            <div class="trending-body">
                <div class="trending-title">
                    <span class="event-name">${escapeHtml(ev.name)}</span>
                    ${ev.trend_name ? `<span class="trend-name-badge">${escapeHtml(ev.trend_name)}</span>` : ""}
                </div>
                ${ev.summary ? `<p class="trending-summary">${escapeHtml(ev.summary)}</p>` : ""}
                <div class="trending-idea">
                    <span class="trending-idea-label">Trend Idea</span>
                    <p>${escapeHtml(ev.trend_idea || "")}</p>
                </div>
                <div class="trending-hook">
                    <span class="trending-hook-label">Hook</span>
                    <p>${escapeHtml(ev.hook || "")}</p>
                </div>
                <div class="trending-score">
                    <span class="trending-score-label">Virality</span>
                    <div class="score-dots">${scoreDots}</div>
                    <span class="score-num">${ev.virality_score}/10</span>
                </div>
                ${ev.editing_suggestion ? renderEditingSuggestion(ev.editing_suggestion) : ""}
                <div class="trending-meta">
                    ${catTags}
                    ${dateStr ? `<span class="meta-tag">${dateStr}</span>` : ""}
                    ${ev.location ? `<span class="meta-tag">${ev.location}</span>` : ""}
                    ${sourceLink}
                </div>
            </div>
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
