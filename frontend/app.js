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
    
    // Force clear any supabase auth tokens locally just in case
    for (let key in localStorage) {
      if (key.startsWith('sb-') && key.endsWith('-auth-token')) {
        localStorage.removeItem(key);
      }
    }

    if (window.auth && typeof window.auth.signOut === 'function') {
      await window.auth.signOut();
    }
  } catch (error) {
    console.error("Logout error:", error);
  } finally {
    window.location.replace("login.html");
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
      const link = item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer" onclick="trackClick('${item.id}')">Open</a>` : "—";
      const title = item.title || "—";
      const company = item.company || "—";
      const location = item.location || "—";
      const source = item.source || "—";
      const keyword = item.keyword || "—";
      const postedDate = item.posted_date || "—";
      const bookmarked = bookmarks.some(b => b.id === item.id);
      
      return `
        <tr>
          <td><button class="bookmark-btn ${bookmarked ? 'active' : ''}" onclick='toggleBookmark(${JSON.stringify(item)})'>★</button></td>
          <td>${escapeHtml(title)}</td>
          <td>${escapeHtml(company)}</td>
          <td>${escapeHtml(location)}</td>
          <td><span class="source-tag">${escapeHtml(source)}</span></td>
          <td>${escapeHtml(keyword)}</td>
          <td>${escapeHtml(postedDate)}</td>
          <td>${link}</td>
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

function renderAnalytics(stats) {
  const total = stats.total || 0;
  const bySource = stats.by_source || {};
  
  let chartHtml = "";
  
  Object.entries(bySource)
    .sort((a, b) => b[1] - a[1])
    .forEach(([source, count]) => {
      const percent = total > 0 ? (count / total) * 100 : 0;
      chartHtml += `
        <div class="chart-bar">
          <span class="chart-label">${escapeHtml(source)}</span>
          <div class="chart-bar-inner" style="width: ${percent}%"></div>
          <span class="chart-value">${count}</span>
        </div>
      `;
    });
  
  if (!chartHtml) {
    chartHtml = "<p style='color: var(--text-muted);'>No data available</p>";
  }
  
  document.getElementById("sourceChart").innerHTML = chartHtml;
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
    const response = await fetch(`${DEFAULT_BASE}/internships/stats`);
    if (!response.ok) return;
    const data = await response.json();
    renderAnalytics(data);
  } catch (e) {
    document.getElementById("sourceChart").innerHTML = "<p style='color: var(--text-muted);'>Failed to load analytics</p>";
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
  }
  
  if (tabName === "bookmarks") {
    renderBookmarksTab();
  } else if (tabName === "analytics") {
    loadAnalytics();
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
    const link = item.link ? `<a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer">Open</a>` : "—";
    return `
      <tr>
        <td><button class="bookmark-btn active" onclick='toggleBookmark(${JSON.stringify(item)})'>★</button></td>
        <td>${escapeHtml(item.title || "—")}</td>
        <td>${escapeHtml(item.company || "—")}</td>
        <td>${escapeHtml(item.location || "—")}</td>
        <td><span class="source-tag">${escapeHtml(item.source || "—")}</span></td>
        <td>${escapeHtml(item.keyword || "—")}</td>
        <td>${escapeHtml(item.posted_date || "—")}</td>
        <td>${link}</td>
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
})();