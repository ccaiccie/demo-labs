(function () {
  "use strict";

  const POLL_INTERVAL_MS = 5000;
  const SEVERITIES = ["critical", "high", "medium", "low"];

  const state = {
    incidents: [],
    countsBySeverity: { critical: 0, high: 0, medium: 0, low: 0 },
    selectedSeverity: null,
    selectedIncidentId: null,
    isRefreshing: false,
    pollTimer: null,
  };

  const els = {
    healthBadge: document.getElementById("health-badge"),
    healthStatusText: document.getElementById("health-status-text"),
    totalEventsCount: document.getElementById("total-events-count"),
    openIncidentsCount: document.getElementById("open-incidents-count"),
    lastUpdated: document.getElementById("last-updated"),
    errorBanner: document.getElementById("error-banner"),
    errorBannerText: document.getElementById("error-banner-text"),
    errorBannerClose: document.getElementById("error-banner-close"),
    severityCards: Array.from(document.querySelectorAll(".severity-card")),
    activeFilterChip: document.getElementById("active-filter-chip"),
    activeFilterText: document.getElementById("active-filter-text"),
    clearFilterBtn: document.getElementById("clear-filter-btn"),
    refreshBtn: document.getElementById("refresh-btn"),
    incidentsTbody: document.getElementById("incidents-tbody"),
    detailModal: document.getElementById("detail-modal"),
    detailSeverityBadge: document.getElementById("detail-severity-badge"),
    detailTitle: document.getElementById("detail-title"),
    detailSummary: document.getElementById("detail-summary"),
    detailMetaGrid: document.getElementById("detail-meta-grid"),
    detailEventsCount: document.getElementById("detail-events-count"),
    detailEventsTbody: document.getElementById("detail-events-tbody"),
    detailError: document.getElementById("detail-error"),
    resolveBtn: document.getElementById("resolve-incident-btn"),
    closeModalBtn: document.getElementById("close-modal-btn"),
  };

  function normalizeSeverity(value) {
    const raw = String(value || "").toLowerCase();
    if (SEVERITIES.includes(raw)) {
      return raw;
    }
    return "neutral";
  }

  function formatTimestamp(isoValue) {
    if (!isoValue) {
      return "--";
    }
    const parsed = new Date(isoValue);
    if (Number.isNaN(parsed.getTime())) {
      return String(isoValue);
    }
    return parsed.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
  }

  function formatLocalClock(date) {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  function setHealthStatus(mode, label) {
    els.healthBadge.classList.remove("status-ok", "status-connecting", "status-error");
    els.healthBadge.classList.add(mode);
    els.healthStatusText.textContent = label;
  }

  function showBannerError(message) {
    els.errorBannerText.textContent = message;
    els.errorBanner.classList.remove("hidden");
  }

  function hideBannerError() {
    els.errorBannerText.textContent = "";
    els.errorBanner.classList.add("hidden");
  }

  function showDetailError(message) {
    els.detailError.textContent = message;
    els.detailError.classList.remove("hidden");
  }

  function hideDetailError() {
    els.detailError.textContent = "";
    els.detailError.classList.add("hidden");
  }

  function createSeverityBadge(severity) {
    const normalized = normalizeSeverity(severity);
    const badge = document.createElement("span");
    badge.className = "severity-badge badge-" + normalized;
    badge.textContent = String(severity || "unknown");
    return badge;
  }

  function updateSeverityCards() {
    for (const sev of SEVERITIES) {
      const countEl = document.getElementById("count-" + sev);
      if (countEl) {
        const count = Number(state.countsBySeverity[sev] || 0);
        countEl.textContent = String(count);
      }
    }

    for (const card of els.severityCards) {
      const sev = card.getAttribute("data-severity");
      const isActive = state.selectedSeverity === sev;
      card.classList.toggle("active", isActive);
      card.setAttribute("aria-pressed", isActive ? "true" : "false");
    }

    if (state.selectedSeverity) {
      els.activeFilterText.textContent = "Severity: " + state.selectedSeverity;
      els.activeFilterChip.classList.remove("hidden");
    } else {
      els.activeFilterText.textContent = "";
      els.activeFilterChip.classList.add("hidden");
    }
  }

  function renderIncidentsTable() {
    const filtered = state.selectedSeverity
      ? state.incidents.filter(
          (inc) => String(inc.severity || "").toLowerCase() === state.selectedSeverity
        )
      : state.incidents;

    if (filtered.length === 0) {
      const emptyRow = document.createElement("tr");
      emptyRow.className = "empty-row";
      const cell = document.createElement("td");
      cell.colSpan = 6;
      cell.textContent = state.selectedSeverity
        ? "No open " + state.selectedSeverity + " incidents."
        : "No open incidents. All systems nominal.";
      emptyRow.appendChild(cell);
      els.incidentsTbody.replaceChildren(emptyRow);
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const inc of filtered) {
      const row = document.createElement("tr");
      row.className = "incident-row";
      row.tabIndex = 0;
      row.setAttribute("data-incident-id", String(inc.id || ""));

      const openHandler = () => {
        if (inc.id) {
          openIncidentDetail(inc.id);
        }
      };

      row.addEventListener("click", openHandler);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openHandler();
        }
      });

      const sevCell = document.createElement("td");
      sevCell.appendChild(createSeverityBadge(inc.severity));
      row.appendChild(sevCell);

      const typeCell = document.createElement("td");
      typeCell.className = "incident-type";
      typeCell.textContent = String(inc.type || "--");
      row.appendChild(typeCell);

      const hostCell = document.createElement("td");
      hostCell.className = "incident-host";
      hostCell.textContent = String(inc.host || "--");
      row.appendChild(hostCell);

      const summaryCell = document.createElement("td");
      const keyDiv = document.createElement("div");
      keyDiv.className = "incident-key";
      keyDiv.textContent = String(inc.key || "");
      const summaryDiv = document.createElement("div");
      summaryDiv.className = "incident-summary";
      summaryDiv.textContent = String(inc.summary || "");
      summaryCell.appendChild(keyDiv);
      summaryCell.appendChild(summaryDiv);
      row.appendChild(summaryCell);

      const countCell = document.createElement("td");
      countCell.className = "num-col mono";
      countCell.textContent = String(inc.count != null ? inc.count : 0);
      row.appendChild(countCell);

      const lastSeenCell = document.createElement("td");
      lastSeenCell.className = "timestamp-cell";
      lastSeenCell.textContent = formatTimestamp(inc.last_seen);
      row.appendChild(lastSeenCell);

      fragment.appendChild(row);
    }

    els.incidentsTbody.replaceChildren(fragment);
  }

  function formatEventContext(ev) {
    const parts = [];
    if (ev.interface) {
      parts.push("iface=" + ev.interface);
    }
    if (ev.peer) {
      parts.push("peer=" + ev.peer);
    }
    if (ev.user) {
      parts.push("user=" + ev.user);
    }
    if (ev.src_ip) {
      parts.push("src=" + ev.src_ip);
    }
    return parts.length > 0 ? parts.join(" ") : "--";
  }

  function renderIncidentDetail(incident, events) {
    const severity = normalizeSeverity(incident.severity);
    els.detailSeverityBadge.className = "severity-badge badge-" + severity;
    els.detailSeverityBadge.textContent = String(incident.severity || "unknown");

    els.detailTitle.textContent = String(incident.type || "Incident") + " — " + String(incident.host || "");
    els.detailSummary.textContent = String(incident.summary || "");

    const metaEntries = [
      ["Incident ID", incident.id || "--", true],
      ["Status", incident.status || "--", false],
      ["Host", incident.host || "--", true],
      ["Correlation Key", incident.key || "--", true],
      ["Event Count", incident.count != null ? String(incident.count) : "0", true],
      ["First Seen", formatTimestamp(incident.first_seen), true],
      ["Last Seen", formatTimestamp(incident.last_seen), true],
    ];

    const metaFrag = document.createDocumentFragment();
    for (const [label, value, isMono] of metaEntries) {
      const wrapper = document.createElement("div");
      wrapper.className = "meta-item";
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      if (isMono) {
        dd.className = "mono";
      }
      dd.textContent = String(value);
      wrapper.appendChild(dt);
      wrapper.appendChild(dd);
      metaFrag.appendChild(wrapper);
    }
    els.detailMetaGrid.replaceChildren(metaFrag);

    const isOpen = String(incident.status || "").toLowerCase() === "open";
    els.resolveBtn.disabled = !isOpen;
    els.resolveBtn.textContent = isOpen ? "Resolve" : "Resolved";

    const list = Array.isArray(events) ? events : [];
    els.detailEventsCount.textContent = list.length + (list.length === 1 ? " event" : " events");

    if (list.length === 0) {
      const emptyRow = document.createElement("tr");
      emptyRow.className = "empty-row";
      const cell = document.createElement("td");
      cell.colSpan = 7;
      cell.textContent = "No correlated events recorded for this incident.";
      emptyRow.appendChild(cell);
      els.detailEventsTbody.replaceChildren(emptyRow);
      return;
    }

    const eventsFrag = document.createDocumentFragment();
    for (const ev of list) {
      const row = document.createElement("tr");

      const tsCell = document.createElement("td");
      tsCell.className = "timestamp-cell";
      tsCell.textContent = formatTimestamp(ev.timestamp);
      row.appendChild(tsCell);

      const hostCell = document.createElement("td");
      hostCell.className = "mono";
      hostCell.textContent = String(ev.host || "--");
      row.appendChild(hostCell);

      const vendorCell = document.createElement("td");
      vendorCell.textContent = String(ev.vendor || "--");
      row.appendChild(vendorCell);

      const kindCell = document.createElement("td");
      kindCell.className = "mono";
      kindCell.textContent = String(ev.kind || "--");
      row.appendChild(kindCell);

      const sevCell = document.createElement("td");
      sevCell.appendChild(createSeverityBadge(ev.severity));
      row.appendChild(sevCell);

      const ctxCell = document.createElement("td");
      ctxCell.className = "event-context";
      ctxCell.textContent = formatEventContext(ev);
      row.appendChild(ctxCell);

      const rawCell = document.createElement("td");
      rawCell.className = "event-raw";
      rawCell.textContent = String(ev.raw || "");
      row.appendChild(rawCell);

      eventsFrag.appendChild(row);
    }
    els.detailEventsTbody.replaceChildren(eventsFrag);
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, Object.assign({ cache: "no-store" }, options || {}));
    if (!response.ok) {
      let detail = "HTTP " + response.status;
      try {
        const body = await response.json();
        if (body && body.error) {
          detail = String(body.error);
        }
      } catch (_err) {
        // Ignore JSON parse errors on non-JSON error responses.
      }
      throw new Error(detail);
    }
    return response.json();
  }

  async function refreshDashboard() {
    if (state.isRefreshing) {
      return;
    }
    state.isRefreshing = true;

    try {
      const [healthData, incidentsData] = await Promise.all([
        fetchJson("/api/health"),
        fetchJson("/api/incidents?status=open"),
      ]);

      const healthy = healthData && healthData.status === "ok";
      setHealthStatus(healthy ? "status-ok" : "status-error", healthy ? "Healthy" : "Degraded");

      els.totalEventsCount.textContent = String(
        healthData && healthData.events_count != null ? healthData.events_count : 0
      );
      els.openIncidentsCount.textContent = String(
        healthData && healthData.open_incidents != null ? healthData.open_incidents : 0
      );

      state.incidents = Array.isArray(incidentsData && incidentsData.incidents)
        ? incidentsData.incidents
        : [];

      const counts = (incidentsData && incidentsData.counts_by_severity) || {};
      state.countsBySeverity = {
        critical: Number(counts.critical || 0),
        high: Number(counts.high || 0),
        medium: Number(counts.medium || 0),
        low: Number(counts.low || 0),
      };

      updateSeverityCards();
      renderIncidentsTable();

      els.lastUpdated.textContent = formatLocalClock(new Date());
      hideBannerError();
    } catch (err) {
      setHealthStatus("status-error", "Disconnected");
      showBannerError("Unable to reach incident API: " + (err && err.message ? err.message : "Network error"));
    } finally {
      state.isRefreshing = false;
    }
  }

  async function openIncidentDetail(incidentId) {
    state.selectedIncidentId = incidentId;
    hideDetailError();
    els.detailTitle.textContent = "Loading incident...";
    els.detailSummary.textContent = "";
    els.detailMetaGrid.replaceChildren();
    els.detailEventsTbody.replaceChildren();
    els.detailEventsCount.textContent = "0 events";
    els.resolveBtn.disabled = true;
    els.resolveBtn.textContent = "Resolve";
    els.detailModal.classList.remove("hidden");

    try {
      const data = await fetchJson("/api/incidents/" + encodeURIComponent(incidentId));
      if (state.selectedIncidentId !== incidentId) {
        return;
      }
      renderIncidentDetail(data.incident || {}, data.events || []);
    } catch (err) {
      showDetailError("Failed to load incident details: " + (err && err.message ? err.message : "Unknown error"));
    }
  }

  function closeIncidentDetail() {
    state.selectedIncidentId = null;
    hideDetailError();
    els.detailModal.classList.add("hidden");
  }

  async function resolveCurrentIncident() {
    const incidentId = state.selectedIncidentId;
    if (!incidentId) {
      return;
    }

    hideDetailError();
    els.resolveBtn.disabled = true;
    els.resolveBtn.textContent = "Resolving...";

    try {
      await fetchJson("/api/incidents/" + encodeURIComponent(incidentId) + "/resolve", {
        method: "POST",
      });
      closeIncidentDetail();
      await refreshDashboard();
    } catch (err) {
      els.resolveBtn.disabled = false;
      els.resolveBtn.textContent = "Resolve";
      showDetailError("Failed to resolve incident: " + (err && err.message ? err.message : "Unknown error"));
    }
  }

  function bindEvents() {
    for (const card of els.severityCards) {
      card.addEventListener("click", () => {
        const sev = card.getAttribute("data-severity");
        state.selectedSeverity = state.selectedSeverity === sev ? null : sev;
        updateSeverityCards();
        renderIncidentsTable();
      });
    }

    els.clearFilterBtn.addEventListener("click", () => {
      state.selectedSeverity = null;
      updateSeverityCards();
      renderIncidentsTable();
    });

    els.refreshBtn.addEventListener("click", () => {
      refreshDashboard();
    });

    els.errorBannerClose.addEventListener("click", hideBannerError);
    els.closeModalBtn.addEventListener("click", closeIncidentDetail);
    els.resolveBtn.addEventListener("click", resolveCurrentIncident);

    els.detailModal.addEventListener("click", (event) => {
      if (event.target === els.detailModal) {
        closeIncidentDetail();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !els.detailModal.classList.contains("hidden")) {
        closeIncidentDetail();
      }
    });
  }

  function init() {
    bindEvents();
    refreshDashboard();
    state.pollTimer = window.setInterval(refreshDashboard, POLL_INTERVAL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
