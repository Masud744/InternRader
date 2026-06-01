const keywordInput = document.getElementById("keyword");
const locationInput = document.getElementById("location");
const dateFromInput = document.getElementById("dateFrom");
const sortBySelect = document.getElementById("sortBy");
const perPageSelect = document.getElementById("perPage");
const loadBtn = document.getElementById("loadBtn");
const refreshBtn = document.getElementById("refreshBtn");
const exportBtn = document.getElementById("exportBtn");
const resetBtn = document.getElementById("resetBtn");
const statusEl = document.getElementById("status");
const resultsBody = document.getElementById("resultsBody");
const totalCountEl = document.getElementById("totalCount");
const showingCountEl = document.getElementById("showingCount");
const sourceCountEl = document.getElementById("sourceCount");
const paginationEl = document.getElementById("pagination");
const sourceFiltersEl = document.getElementById("sourceFilters");
const bookmarkCountEl = document.getElementById("bookmarkCount");
const userEmailEl = document.getElementById("userEmail");
const logoutBtn = document.getElementById("logoutBtn");
const authOverlay = document.getElementById("authOverlay");

const appConfig = window.INTERNRADAR_CONFIG || {};
const DEFAULT_BASE = appConfig.apiBaseUrl || "http://127.0.0.1:8000";

let currentOffset = 0;
let currentItems = [];
let availableSources = [];
let selectedSources = new Set();
let clickStats = JSON.parse(localStorage.getItem("clickStats") || "{}");
let currentUser = null;

async function checkAuth() {
  try {
    const auth = window.auth;
    if (!auth || auth.isLoading) {
      console.warn("[InternRadar] Auth not ready yet");
      authOverlay.classList.remove("hidden");
      return false;
    }
    const session = await auth.getSession();
    if (!session) {
      console.warn("[InternRadar] No active session");
      authOverlay.classList.remove("hidden");
      return false;
    }
    
    const user = await auth.getUser();
    currentUser = user;
    console.log("[InternRadar] Authenticated as:", user?.email);
    if (userEmailEl) {
      userEmailEl.textContent = user.email;
    }
    authOverlay.classList.add("hidden");
    return true;
  } catch (error) {
    console.error("[InternRadar] Auth check failed:", error);
    authOverlay.classList.remove("hidden");
    return false;
  }
}

async function handleLogout() {
  try {
    if (logoutBtn) {
      logoutBtn.innerHTML = '<span class="loading-spinner" style="border-width: 1px; width: 10px; height: 10px;"></span> OUT';
      logoutBtn.style.pointerEvents = 'none';
    }

    if (window.auth && typeof window.auth.signOut === 'function') {
      await window.auth.signOut();
    }
  } catch (error) {
    console.error("Logout error:", error);
  } finally {
    // Force clear any supabase auth tokens locally just in case
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('sb-') && key.endsWith('-auth-token')) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
    
    window.location.href = "login.html";
  }
}

async function waitForAuthReady(timeoutMs = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (window.auth && window.auth.isLoading === false) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

if (logoutBtn) {
  logoutBtn.addEventListener("click", handleLogout);
}

function getBookmarks() {
  return JSON.parse(localStorage.getItem("bookmarks") || "[]");
}

function saveBookmarks(bookmarks) {
  localStorage.setItem("bookmarks", JSON.stringify(bookmarks));
  updateBookmarkCount();
}

function updateBookmarkCount() {
  const count = getBookmarks().length;
  if (bookmarkCountEl) bookmarkCountEl.textContent = String(count);
}

function isBookmarked(id) {
  return getBookmarks().some(b => b.id === id);
}

function toggleBookmark(item) {
  const bookmarks = getBookmarks();
  const existingIndex = bookmarks.findIndex(b => b.id === item.id);
  
  if (existingIndex >= 0) {
    bookmarks.splice(existingIndex, 1);
  } else {
    bookmarks.push(item);
  }
  
  saveBookmarks(bookmarks);
  renderRows(currentItems);
}

function trackClick(id) {
  clickStats[id] = (clickStats[id] || 0) + 1;
  localStorage.setItem("clickStats", JSON.stringify(clickStats));
}

function setStatus(message, isError = false) {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#c0392b" : "var(--text-muted, #8EB69B)";
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function buildQuery() {
  const limit = parseInt(perPageSelect.value, 10) || 20;
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(currentOffset),
    sort: sortBySelect.value,
  });

  const keyword = keywordInput.value.trim();
  const location = locationInput.value.trim();
  const dateFrom = dateFromInput.value;
  
  if (keyword) params.set("keyword", keyword);
  if (location) params.set("location", location);
  if (dateFrom) params.set("date_from", dateFrom);
  if (selectedSources.size > 0) {
    params.set("source_in", Array.from(selectedSources).join(","));
  }

  return `${DEFAULT_BASE}/internships?${params.toString()}`;
}

function renderSourceFilters(sources) {
  if (!sources.length) return;
  availableSources = sources;
  sourceFiltersEl.innerHTML = sources.map(source => `
    <button class="source-toggle ${selectedSources.has(source) ? 'active' : ''}" data-source="${escapeHtml(source)}">
      ${escapeHtml(source)}
    </button>
  `).join("");
  
  sourceFiltersEl.querySelectorAll(".source-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const source = btn.dataset.source;
      if (selectedSources.has(source)) {
        selectedSources.delete(source);
        btn.classList.remove("active");
      } else {
        selectedSources.add(source);
        btn.classList.add("active");
      }
      currentOffset = 0;
      loadInternships();
    });
  });
}

function renderRows(items) {
  if (!items.length) {
    resultsBody.innerHTML = '<tr><td colspan="8" class="empty">No internships found. Try adjusting your filters.</td></tr>';
    return;
  }

  const bookmarks = getBookmarks();
  
  const rows = items
    .map((item) => {
      const link = item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer" class="btn-ghost" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="trackClick('${item.id}')">Open</a>` : "—";
      const aiBtn = `<button class="btn-primary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; margin-left: 0.25rem;" onclick='openCoverLetterModal(${JSON.stringify(item).replace(/'/g, "&#39;")})'>✨ AI</button>`;
      const title = item.title || "—";
      const company = item.company || "—";
      const location = item.location || "—";
      const source = item.source || "—";
      const keyword = item.keyword || "—";
      const postedDate = item.posted_date || "—";
      const bookmarked = bookmarks.some(b => b.id === item.id);
      
      return `
        <tr>
          <td><button class="bookmark-btn ${bookmarked ? 'active' : ''}" onclick='toggleBookmark(${JSON.stringify(item).replace(/'/g, "&#39;")})'>★</button></td>
          <td>${escapeHtml(title)}</td>
          <td>${escapeHtml(company)}</td>
          <td>${escapeHtml(location)}</td>
          <td><span class="source-tag">${escapeHtml(source)}</span></td>
          <td>${escapeHtml(keyword)}</td>
          <td>${escapeHtml(postedDate)}</td>
          <td style="white-space: nowrap;">${link}${aiBtn}</td>
        </tr>
      `;
    })
    .join("");

  resultsBody.innerHTML = rows;
}

function renderPagination(total, limit, offset) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;
  
  let html = "";
  
  html += `<button ${currentPage <= 1 ? "disabled" : ""} onclick="goToPage(1)">First</button>`;
  html += `<button ${currentPage <= 1 ? "disabled" : ""} onclick="goToPage(${currentPage - 1})">Prev</button>`;
  html += `<span>Page ${currentPage} of ${totalPages}</span>`;
  html += `<button ${currentPage >= totalPages ? "disabled" : ""} onclick="goToPage(${currentPage + 1})">Next</button>`;
  html += `<button ${currentPage >= totalPages ? "disabled" : ""} onclick="goToPage(${totalPages})">Last</button>`;
  
  paginationEl.innerHTML = html;
}

window.goToPage = function(page) {
  const limit = parseInt(perPageSelect.value, 10) || 20;
  currentOffset = (page - 1) * limit;
  loadInternships();
};

function updateStats(items, total) {
  const limit = parseInt(perPageSelect.value, 10) || 20;
  const showing = items.length;
  const start = total > 0 ? currentOffset + 1 : 0;
  const end = currentOffset + showing;
  
  showingCountEl.textContent = total > 0 ? `${start}-${end}` : "0-0";
  totalCountEl.textContent = String(total);
  
  const sources = new Set(items.map((item) => item.source).filter(Boolean));
  sourceCountEl.textContent = String(sources.size);
}

// Chart.js instances
let chartInstances = {};

function destroyCharts() {
  Object.values(chartInstances).forEach(c => { if (c) c.destroy(); });
  chartInstances = {};
}

const CHART_COLORS = ['#3b82f6','#8b5cf6','#f59e0b','#10b981','#ef4444','#ec4899','#06b6d4','#84cc16','#f97316','#6366f1'];

function renderAnalytics(stats) {
  destroyCharts();
  const bySource = stats.by_source || {};
  const byLocation = stats.by_location || {};
  const byKeyword = stats.by_keyword || {};
  const byDate = stats.by_date || {};

  // 1. Doughnut – Jobs by Source
  const srcCtx = document.getElementById("sourceChartCanvas");
  if (srcCtx) {
    chartInstances.source = new Chart(srcCtx, {
      type: "doughnut",
      data: {
        labels: Object.keys(bySource),
        datasets: [{ data: Object.values(bySource), backgroundColor: CHART_COLORS, borderWidth: 0 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim(), font: { size: 11 } } } } }
    });
  }

  // 2. Bar – Top Locations
  const locCtx = document.getElementById("locationChartCanvas");
  if (locCtx) {
    chartInstances.location = new Chart(locCtx, {
      type: "bar",
      data: {
        labels: Object.keys(byLocation),
        datasets: [{ label: "Jobs", data: Object.values(byLocation), backgroundColor: "#3b82f6", borderRadius: 4 }]
      },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim() }, grid: { color: "rgba(255,255,255,0.05)" } }, y: { ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim(), font: { size: 10 } }, grid: { display: false } } } }
    });
  }

  // 3. Bar – In-Demand Skills/Keywords
  const kwCtx = document.getElementById("keywordChartCanvas");
  if (kwCtx) {
    chartInstances.keyword = new Chart(kwCtx, {
      type: "bar",
      data: {
        labels: Object.keys(byKeyword),
        datasets: [{ label: "Jobs", data: Object.values(byKeyword), backgroundColor: CHART_COLORS, borderRadius: 4 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim(), font: { size: 9 }, maxRotation: 45 }, grid: { display: false } }, y: { ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim() }, grid: { color: "rgba(255,255,255,0.05)" } } } }
    });
  }

  // 4. Line – Jobs Over Time
  const timeCtx = document.getElementById("timelineChartCanvas");
  if (timeCtx) {
    chartInstances.timeline = new Chart(timeCtx, {
      type: "line",
      data: {
        labels: Object.keys(byDate),
        datasets: [{ label: "New Jobs", data: Object.values(byDate), borderColor: "#8b5cf6", backgroundColor: "rgba(139,92,246,0.1)", fill: true, tension: 0.4, pointRadius: 2 }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim(), font: { size: 9 }, maxRotation: 45 }, grid: { display: false } }, y: { ticks: { color: getComputedStyle(document.body).getPropertyValue('--text-muted').trim() }, grid: { color: "rgba(255,255,255,0.05)" } } } }
    });
  }
}

async function loadInternships() {
  const url = buildQuery();
  console.log("[InternRadar] Fetching:", url);
  setStatus("Loading internships...");
  if (loadBtn) {
    loadBtn.disabled = true;
    loadBtn.innerHTML = '<span class="loading-spinner"></span> LOADING...';
  }

  try {
    const response = await fetch(url);
    const responseText = await response.text();
    console.log("[InternRadar] Response status:", response.status, "length:", responseText.length);
    
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${responseText}`);
    }

    let payload;
    try {
      payload = JSON.parse(responseText);
    } catch {
      throw new Error(`Invalid JSON: ${responseText.slice(0, 100)}`);
    }
    
    const items = Array.isArray(payload.items) ? payload.items : (Array.isArray(payload) ? payload : []);
    const total = payload.total || items.length;
    currentItems = items;
    console.log("[InternRadar] Loaded", items.length, "items, total:", total);
    
    renderRows(items);
    updateStats(items, total);
    renderPagination(total, parseInt(perPageSelect.value, 10) || 20, currentOffset);
    setStatus(`Showing ${items.length} of ${total} internships`);
    
    if (items.length > 0 && availableSources.length === 0) {
      loadSources();
    }
  } catch (error) {
    console.error("[InternRadar] loadInternships failed:", error);
    currentItems = [];
    renderRows([]);
    updateStats([], 0);
    paginationEl.innerHTML = "";
    setStatus(`Failed: ${error.message}`, true);
  } finally {
    if (loadBtn) {
      loadBtn.disabled = false;
      loadBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> LOAD INTERNSHIPS';
    }
  }
}

async function loadSources() {
  try {
    const response = await fetch(`${DEFAULT_BASE}/internships/sources`);
    if (!response.ok) return;
    const data = await response.json();
    if (data.sources) {
      renderSourceFilters(data.sources);
    }
  } catch (e) {}
}

async function loadAnalytics() {
  try {
    const response = await fetch(`${DEFAULT_BASE}/analytics`);
    if (!response.ok) return;
    const data = await response.json();
    renderAnalytics(data);
  } catch (e) {
    console.error("Analytics load failed:", e);
  }
}

function exportToCSV(items, filename = "internships.csv") {
  if (!items.length) {
    setStatus("No data to export", true);
    return;
  }
  
  const headers = ["Title", "Company", "Location", "Source", "Keyword", "Posted Date", "Link"];
  const rows = items.map(item => [
    item.title || "",
    item.company || "",
    item.location || "",
    item.source || "",
    item.keyword || "",
    item.posted_date || "",
    item.link || ""
  ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(","));
  
  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  
  setStatus(`Exported ${items.length} internships to CSV`);
}

function showTab(tabName) {
  document.querySelectorAll(".nav-btn").forEach(t => t.classList.remove("active"));
  const activeBtn = document.querySelector(`.nav-btn[data-tab="${tabName}"]`);
  if (activeBtn) activeBtn.classList.add("active");
  
  document.querySelectorAll(".tab-content").forEach(c => {
    c.classList.remove("active");
    c.classList.add("hidden");
  });
  const activeContent = document.getElementById(`${tabName}Tab`);
  if (activeContent) {
    activeContent.classList.remove("hidden");
    activeContent.classList.add("active");
  }

  const pageTitle = document.getElementById("pageTitle");
  if(pageTitle) {
    if (tabName === "internships") pageTitle.textContent = "DASHBOARD OVERVIEW";
    else if (tabName === "bookmarks") pageTitle.textContent = "SAVED INTERNSHIPS";
    else if (tabName === "analytics") pageTitle.textContent = "ANALYTICS OVERVIEW";
    else if (tabName === "tracker") pageTitle.textContent = "APPLICATION TRACKER";
  }
  
  if (tabName === "bookmarks") {
    renderBookmarksTab();
  } else if (tabName === "analytics") {
    loadAnalytics();
  } else if (tabName === "tracker") {
    loadTrackerBoard();
  }
}

function renderBookmarksTab() {
  const bookmarks = getBookmarks();
  const bookmarksBody = document.getElementById("bookmarksBody");
  if (!bookmarksBody) return;

  if (!bookmarks.length) {
    bookmarksBody.innerHTML = '<tr><td colspan="8" class="empty-state">No bookmarks saved yet. Use the ★ button to save listings.</td></tr>';
    return;
  }

  const rows = bookmarks.map((item) => {
    const link = item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer" class="btn-ghost" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="trackClick('${item.id}')">Open</a>` : "—";
    const aiBtn = `<button class="btn-primary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; margin-left: 0.25rem;" onclick='openCoverLetterModal(${JSON.stringify(item).replace(/'/g, "&#39;")})'>✨ AI</button>`;
    return `
      <tr>
        <td><button class="bookmark-btn active" onclick='toggleBookmark(${JSON.stringify(item).replace(/'/g, "&#39;")})'>★</button></td>
        <td>${escapeHtml(item.title || "—")}</td>
        <td>${escapeHtml(item.company || "—")}</td>
        <td>${escapeHtml(item.location || "—")}</td>
        <td><span class="source-tag">${escapeHtml(item.source || "—")}</span></td>
        <td>${escapeHtml(item.keyword || "—")}</td>
        <td>${escapeHtml(item.posted_date || "—")}</td>
        <td style="white-space: nowrap;">${link}${aiBtn}</td>
      </tr>
    `;
  }).join("");

  bookmarksBody.innerHTML = rows;
}

function resetFilters() {
  keywordInput.value = "";
  locationInput.value = "";
  dateFromInput.value = "";
  sortBySelect.value = "latest";
  perPageSelect.value = "20";
  selectedSources.clear();
  document.querySelectorAll(".source-toggle").forEach(btn => btn.classList.remove("active"));
  currentOffset = 0;
  setStatus("Filters reset");
  loadInternships();
}

document.querySelectorAll(".nav-btn").forEach(btn => {
  if (btn.dataset.tab) {
    btn.addEventListener("click", () => showTab(btn.dataset.tab));
  }
});

loadBtn.addEventListener("click", loadInternships);
refreshBtn.addEventListener("click", () => {
  loadInternships();
  loadSources();
});

exportBtn.addEventListener("click", () => exportToCSV(currentItems));
resetBtn.addEventListener("click", resetFilters);

document.getElementById("exportBookmarksBtn")?.addEventListener("click", () => {
  exportToCSV(getBookmarks(), "bookmarks.csv");
});

document.getElementById("clearBookmarksBtn")?.addEventListener("click", () => {
  if (confirm("Clear all bookmarks?")) {
    saveBookmarks([]);
    renderBookmarksTab();
    setStatus("Bookmarks cleared");
  }
});

// State
let allInternships = [];
let currentPage = 1;
const itemsPerPage = 20;

// ══════════════════════════════════════════
// KANBAN BOARD (Application Tracker)
// ══════════════════════════════════════════

function loadTrackerBoard() {
  const bookmarks = getBookmarks();
  const statuses = ["Saved", "Applied", "Interviewing", "Accepted", "Rejected"];

  statuses.forEach(status => {
    const container = document.getElementById(`items${status}`);
    const countEl = document.getElementById(`count${status}`);
    if (!container) return;

    const items = bookmarks.filter(b => (b.status || "Saved") === status);
    if (countEl) countEl.textContent = items.length;

    if (!items.length) {
      container.innerHTML = `<p style="color: var(--text-dim); font-size: 0.7rem; text-align: center; padding: 1rem 0;">No items</p>`;
      return;
    }

    container.innerHTML = items.map(item => `
      <div class="kanban-card" style="background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 0.6rem; margin-bottom: 0.5rem; cursor: default;">
        <p style="color: var(--text); font-size: 0.75rem; font-weight: 500; margin-bottom: 0.25rem; line-height: 1.3;">${escapeHtml(item.title || "Untitled")}</p>
        <p style="color: var(--text-muted); font-size: 0.65rem; margin-bottom: 0.5rem;">${escapeHtml(item.company || "—")}</p>
        <select class="kanban-status-select" data-id="${escapeHtml(item.id || item.link)}" style="width: 100%; padding: 0.25rem; font-size: 0.65rem; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 4px; cursor: pointer;">
          ${statuses.map(s => `<option value="${s}" ${s === status ? "selected" : ""}>${s}</option>`).join("")}
        </select>
      </div>
    `).join("");
  });

  // Bind status change events
  document.querySelectorAll(".kanban-status-select").forEach(sel => {
    sel.addEventListener("change", (e) => {
      const itemId = e.target.dataset.id;
      const newStatus = e.target.value;
      const bookmarks = getBookmarks();
      const idx = bookmarks.findIndex(b => (b.id || b.link) === itemId);
      if (idx !== -1) {
        bookmarks[idx].status = newStatus;
        saveBookmarks(bookmarks);
        loadTrackerBoard();
      }
    });
  });
}


// ══════════════════════════════════════════
// AI COVER LETTER GENERATOR
// ══════════════════════════════════════════

let currentCoverLetterJob = null;

function openCoverLetterModal(job) {
  currentCoverLetterJob = job;
  const modal = document.getElementById("coverLetterModal");
  const titleEl = document.getElementById("coverLetterJobTitle");
  const loadingEl = document.getElementById("coverLetterLoading");
  const contentEl = document.getElementById("coverLetterContent");
  const actionsEl = document.getElementById("coverLetterActions");

  if (!modal) return;

  titleEl.textContent = `For: ${job.title} at ${job.company}`;
  loadingEl.classList.remove("hidden");
  contentEl.classList.add("hidden");
  actionsEl.classList.add("hidden");
  modal.classList.remove("hidden");

  generateCoverLetter(job);
}

async function generateCoverLetter(job) {
  const loadingEl = document.getElementById("coverLetterLoading");
  const contentEl = document.getElementById("coverLetterContent");
  const actionsEl = document.getElementById("coverLetterActions");

  try {
    const profileName = document.getElementById("profileFullName")?.value || "";
    const profileResume = document.getElementById("profileResumeText")?.value || "";
    
    const resp = await fetch(`${DEFAULT_BASE}/generate-cover-letter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: job.title || "",
        company: job.company || "",
        location: job.location || "",
        user_name: profileName || localStorage.getItem("userName") || "Applicant",
        user_skills: profileResume || localStorage.getItem("userSkills") || "",
      }),
    });
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    const data = await resp.json();

    contentEl.textContent = data.cover_letter || "No content generated.";
    loadingEl.classList.add("hidden");
    contentEl.classList.remove("hidden");
    actionsEl.classList.remove("hidden");
  } catch (err) {
    loadingEl.innerHTML = `<div style="color: #ef4444;">❌ Failed to generate: ${err.message}</div>`;
  }
}

// Cover Letter modal event listeners
document.getElementById("closeCoverLetterModal")?.addEventListener("click", () => {
  document.getElementById("coverLetterModal")?.classList.add("hidden");
});

document.getElementById("copyCoverLetter")?.addEventListener("click", () => {
  const text = document.getElementById("coverLetterContent")?.textContent || "";
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById("copyCoverLetter");
    btn.textContent = "✅ Copied!";
    setTimeout(() => btn.textContent = "📋 Copy to Clipboard", 2000);
  });
});

document.getElementById("regenerateCoverLetter")?.addEventListener("click", () => {
  if (currentCoverLetterJob) {
    document.getElementById("coverLetterLoading").classList.remove("hidden");
    document.getElementById("coverLetterContent").classList.add("hidden");
    document.getElementById("coverLetterActions").classList.add("hidden");
    generateCoverLetter(currentCoverLetterJob);
  }
});

// Make openCoverLetterModal globally accessible
window.openCoverLetterModal = openCoverLetterModal;


// ══════════════════════════════════════════
// THEME TOGGLE
// ══════════════════════════════════════════

function initThemeToggle() {
  const toggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  if (!toggleBtn || !themeIcon) return;

  const currentTheme = localStorage.getItem('theme') || 'light';
  if (currentTheme === 'dark') {
    document.body.classList.add('dark-theme');
    themeIcon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
  }

  toggleBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark-theme');
    if (document.body.classList.contains('dark-theme')) {
      localStorage.setItem('theme', 'dark');
      themeIcon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    } else {
      localStorage.setItem('theme', 'light');
      themeIcon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
});

perPageSelect.addEventListener("change", () => {
  currentOffset = 0;
  loadInternships();
});

sortBySelect.addEventListener("change", loadInternships);

async function initAuthListeners() {
  const ready = await waitForAuthReady();
  if (!ready || !window.auth) {
    return;
  }

  window.auth.onAuthStateChange(async (event, session) => {
    if (event === "SIGNED_OUT") {
      window.location.href = "login.html";
    } else if (event === "SIGNED_IN") {
      await checkAuth();
    }
  });
}

initAuthListeners();
initThemeToggle();

(async function init() {
  console.log("[InternRadar] Initializing...");
  const ready = await waitForAuthReady();
  
  if (!ready) {
    console.warn("[InternRadar] Auth timeout, loading internships anyway");
    setStatus("Auth is still loading, but fetching internships...");
    loadInternships();
    return;
  }

  const isAuthenticated = await checkAuth();
  console.log("[InternRadar] Auth result:", isAuthenticated);
  
  // Always load internships regardless of auth status
  // (internships table has no RLS restrictions)
  updateBookmarkCount();
  loadInternships();
  if (isAuthenticated) {
    loadProfile();
  }
})();

// ══════════════════════════════════════════
// PROFILE LOGIC
// ══════════════════════════════════════════

async function loadProfile() {
  if (!window.supabaseClient) return;
  const user = await window.auth.getUser();
  if (!user) return;

  try {
    const { data, error } = await window.supabaseClient
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single();

    if (error && error.code !== 'PGRST116') {
      console.error("Error loading profile:", error);
      return;
    }
    
    if (data) {
      if (document.getElementById("profileFullName")) document.getElementById("profileFullName").value = data.full_name || "";
      if (document.getElementById("profileUniversity")) document.getElementById("profileUniversity").value = data.university || "";
      if (document.getElementById("profileExperience")) document.getElementById("profileExperience").value = data.experience_level || "Student";
      if (document.getElementById("profileResumeText")) document.getElementById("profileResumeText").value = data.resume_text || "";
    }
  } catch (err) {
    console.error("Profile load exception:", err);
  }
}

document.getElementById("saveProfileBtn")?.addEventListener("click", async () => {
  if (!window.supabaseClient) return;
  const user = await window.auth.getUser();
  if (!user) {
    alert("You must be logged in to save your profile.");
    return;
  }

  const btn = document.getElementById("saveProfileBtn");
  const statusEl = document.getElementById("profileSaveStatus");
  btn.disabled = true;
  btn.textContent = "Saving...";
  statusEl.style.display = "none";

  const profileData = {
    id: user.id,
    email: user.email,
    full_name: document.getElementById("profileFullName")?.value || "",
    university: document.getElementById("profileUniversity")?.value || "",
    experience_level: document.getElementById("profileExperience")?.value || "Student",
    resume_text: document.getElementById("profileResumeText")?.value || "",
    updated_at: new Date().toISOString()
  };

  try {
    const { error } = await window.supabaseClient
      .from('profiles')
      .upsert(profileData);
      
    if (error) throw error;
    
    statusEl.style.display = "inline";
    setTimeout(() => { statusEl.style.display = "none"; }, 3000);
  } catch (err) {
    console.error("Error saving profile:", err);
    alert("Failed to save profile: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "💾 Save Profile";
  }
});