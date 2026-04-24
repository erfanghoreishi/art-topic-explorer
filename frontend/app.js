(function () {
  "use strict";

  const appEl = document.getElementById("app");
  const breadcrumbsEl = document.getElementById("breadcrumbs");
  const lastUpdatedEl = document.getElementById("last-updated");
  const datasetStatsEl = document.getElementById("dataset-stats");
  const refreshBtn = document.getElementById("refresh-btn");
  const adminLoginBtn = document.getElementById("admin-login-btn");
  const adminLogoutBtn = document.getElementById("admin-logout-btn");
  const adminControlsEl = document.getElementById("admin-controls");
  const adminRefreshBtn = document.getElementById("admin-refresh-btn");
  const scheduleBtn = document.getElementById("schedule-btn");
  const schedulePresetEl = document.getElementById("schedule-preset");
  const adminLoginDialog = document.getElementById("admin-login-dialog");
  const adminLoginForm = document.getElementById("admin-login-form");
  const adminTokenInput = document.getElementById("admin-token-input");
  const adminLoginError = document.getElementById("admin-login-error");
  const detailDialog = document.getElementById("detail-dialog");
  const detailContent = document.getElementById("detail-content");

  const state = {
    dataset: null,
    topicsById: new Map(),
    erasByKey: new Map(),
    artworksById: new Map(),
    loading: false,
    error: "",
    adminToken: "",
  };

  function setAdminUi(loggedIn) {
    adminControlsEl?.classList.toggle("hidden", !loggedIn);
    adminLogoutBtn?.classList.toggle("hidden", !loggedIn);
    adminLoginBtn?.classList.toggle("hidden", loggedIn);
  }

  function saveAdminToken(token) {
    state.adminToken = token || "";
    if (state.adminToken) {
      sessionStorage.setItem("adminToken", state.adminToken);
    } else {
      sessionStorage.removeItem("adminToken");
    }
    setAdminUi(Boolean(state.adminToken));
  }

  function initAdminToken() {
    const existing = sessionStorage.getItem("adminToken") || "";
    saveAdminToken(existing);
  }

  function escapeHtml(text) {
    return String(text ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatDate(iso) {
    if (!iso) return "--";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString();
  }

  function keyForEra(classificationId, eraId) {
    return `${classificationId}::${eraId}`;
  }

  function parseHash() {
    const hash = window.location.hash || "#/";
    const path = hash.replace(/^#/, "");
    const parts = path.split("/").filter(Boolean);

    if (parts.length === 0) return { name: "home" };
    if (parts[0] === "classification" && parts[1] && !parts[2]) {
      return { name: "classification", classificationId: decodeURIComponent(parts[1]) };
    }
    if (
      parts[0] === "classification" &&
      parts[1] &&
      parts[2] === "era" &&
      parts[3]
    ) {
      return {
        name: "era",
        classificationId: decodeURIComponent(parts[1]),
        eraId: decodeURIComponent(parts[3]),
      };
    }
    if (parts[0] === "artwork" && parts[1]) {
      return { name: "artwork", artworkId: Number(parts[1]) };
    }
    return { name: "not_found" };
  }

  function setLoadingUi() {
    appEl.innerHTML = '<section class="state">Loading dataset...</section>';
    breadcrumbsEl.innerHTML = "";
  }

  function setErrorUi(msg) {
    appEl.innerHTML = `<section class="state error">${escapeHtml(msg)}</section>`;
  }

  function buildIndexes(dataset) {
    state.topicsById.clear();
    state.erasByKey.clear();
    state.artworksById.clear();

    const topics = dataset?.topics ?? [];
    topics.forEach((topic) => {
      state.topicsById.set(topic.id, topic);
      (topic.subtopics ?? []).forEach((era) => {
        state.erasByKey.set(keyForEra(topic.id, era.id), { topic, era });
        (era.items ?? []).forEach((item) => {
          state.artworksById.set(Number(item.id), { topic, era, item });
        });
      });
    });
  }

  function countArtworks(dataset) {
    let count = 0;
    (dataset?.topics ?? []).forEach((topic) => {
      (topic.subtopics ?? []).forEach((era) => {
        count += (era.items ?? []).length;
      });
    });
    return count;
  }

  async function loadDataset() {
    state.loading = true;
    state.error = "";
    setLoadingUi();
    try {
      const url = window.APP_CONFIG?.datasetUrl || "./dataset.json";
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`Failed to fetch dataset (${res.status})`);
      const dataset = await res.json();
      state.dataset = dataset;
      buildIndexes(dataset);
      lastUpdatedEl.textContent = `Last updated: ${formatDate(dataset.lastUpdated)}`;
      datasetStatsEl.textContent = `Topics: ${(dataset.topics || []).length} | Artworks: ${countArtworks(dataset)}`;
      state.loading = false;
      renderCurrentRoute();
    } catch (err) {
      state.loading = false;
      state.error = err?.message || "Failed to load dataset";
      setErrorUi(state.error);
    }
  }

  function renderBreadcrumbs(items) {
    breadcrumbsEl.innerHTML = items
      .map((item) =>
        item.href
          ? `<a href="${item.href}">${escapeHtml(item.label)}</a>`
          : `<span>${escapeHtml(item.label)}</span>`
      )
      .join('<span class="sep">/</span>');
  }

  function pickCoverImage(topic) {
    for (const era of topic.subtopics ?? []) {
      const first = era.items?.[0];
      if (first?.imageUrl) return first.imageUrl;
    }
    return "";
  }

  function renderHome() {
    const topics = state.dataset?.topics ?? [];
    renderBreadcrumbs([{ label: "Home" }]);

    if (topics.length === 0) {
      appEl.innerHTML = '<section class="state">No classifications available.</section>';
      return;
    }

    appEl.innerHTML = `
      <section>
        <h2>Classifications</h2>
        <div class="card-grid">
          ${topics
            .map((topic) => {
              const cover = pickCoverImage(topic);
              return `
                <a class="card" href="#/classification/${encodeURIComponent(topic.id)}">
                  <div class="thumb-wrap">
                    ${
                      cover
                        ? `<img class="thumb" src="${escapeHtml(cover)}" alt="${escapeHtml(topic.name)}" loading="lazy" />`
                        : `<div class="thumb placeholder">No image</div>`
                    }
                  </div>
                  <div class="card-body">
                    <h3>${escapeHtml(topic.name)}</h3>
                    <p>${topic.count || 0} artworks</p>
                  </div>
                </a>
              `;
            })
            .join("")}
        </div>
      </section>
    `;
  }

  function renderClassification(classificationId) {
    const topic = state.topicsById.get(classificationId);
    if (!topic) return renderNotFound("Classification not found.");

    renderBreadcrumbs([
      { label: "Home", href: "#/" },
      { label: topic.name },
    ]);

    const eras = topic.subtopics ?? [];
    if (eras.length === 0) {
      appEl.innerHTML = `
        <section class="state">
          No eras available for ${escapeHtml(topic.name)}.
        </section>
      `;
      return;
    }
    appEl.innerHTML = `
      <section>
        <h2>${escapeHtml(topic.name)}: Eras</h2>
        <div class="card-grid">
          ${eras
            .map((era) => {
              const cover = era.items?.[0]?.imageUrl || "";
              return `
                <a class="card" href="#/classification/${encodeURIComponent(
                  topic.id
                )}/era/${encodeURIComponent(era.id)}">
                  <div class="thumb-wrap">
                    ${
                      cover
                        ? `<img class="thumb" src="${escapeHtml(cover)}" alt="${escapeHtml(era.name)}" loading="lazy" />`
                        : `<div class="thumb placeholder">No image</div>`
                    }
                  </div>
                  <div class="card-body">
                    <h3>${escapeHtml(era.name)}</h3>
                    <p>${era.count || 0} artworks</p>
                    <small>Source: ${escapeHtml(era.eraSource || "unknown")}</small>
                  </div>
                </a>
              `;
            })
            .join("")}
        </div>
      </section>
    `;
  }

  function artistLabel(item) {
    if (!item.people || item.people.length === 0) return "Unknown artist";
    return item.people[0];
  }

  function renderEra(classificationId, eraId) {
    const pair = state.erasByKey.get(keyForEra(classificationId, eraId));
    if (!pair) return renderNotFound("Era not found.");
    const { topic, era } = pair;

    renderBreadcrumbs([
      { label: "Home", href: "#/" },
      { label: topic.name, href: `#/classification/${encodeURIComponent(topic.id)}` },
      { label: era.name },
    ]);

    const items = era.items ?? [];
    if (items.length === 0) {
      appEl.innerHTML = `
        <section class="state">
          No artworks available in ${escapeHtml(era.name)}.
        </section>
      `;
      return;
    }
    appEl.innerHTML = `
      <section>
        <h2>${escapeHtml(topic.name)} -> ${escapeHtml(era.name)}</h2>
        <div class="art-grid">
          ${items
            .map(
              (item) => `
                <article class="art-card">
                  ${
                    item.imageUrl
                      ? `<img class="art-img" src="${escapeHtml(item.imageUrl)}" alt="${escapeHtml(item.title)}" loading="lazy" />`
                      : `<div class="art-img placeholder">No image</div>`
                  }
                  <div class="art-meta">
                    <h3>${escapeHtml(item.title || "Untitled")}</h3>
                    <p>${escapeHtml(artistLabel(item))}</p>
                    <p>${escapeHtml(item.dated || "—")}</p>
                    <a class="link" href="#/artwork/${item.id}">View details</a>
                  </div>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
    `;
  }

  function renderArtworkDetail(artworkId) {
    const entry = state.artworksById.get(Number(artworkId));
    if (!entry) return renderNotFound("Artwork not found.");
    const { topic, era, item } = entry;

    renderBreadcrumbs([
      { label: "Home", href: "#/" },
      { label: topic.name, href: `#/classification/${encodeURIComponent(topic.id)}` },
      {
        label: era.name,
        href: `#/classification/${encodeURIComponent(topic.id)}/era/${encodeURIComponent(era.id)}`,
      },
      { label: item.title || "Artwork" },
    ]);

    appEl.innerHTML = `
      <section class="detail-page">
        <h2>${escapeHtml(item.title || "Untitled")}</h2>
        <button id="open-detail-modal" class="btn">Open detail modal</button>
      </section>
    `;

    detailContent.innerHTML = `
      <section class="detail-layout">
        <div>
          ${
            item.imageUrl
              ? `<img class="detail-image" src="${escapeHtml(item.imageUrl)}" alt="${escapeHtml(item.title)}" />`
              : `<div class="detail-image placeholder">No image</div>`
          }
        </div>
        <div class="facts">
          <h3>${escapeHtml(item.title || "Untitled")}</h3>
          <p><strong>Artist:</strong> ${escapeHtml((item.people || []).join(", ") || "Unknown artist")}</p>
          <p><strong>Dated:</strong> ${escapeHtml(item.dated || "—")}</p>
          <p><strong>Medium:</strong> ${escapeHtml(item.medium || "—")}</p>
          <p><strong>Culture:</strong> ${escapeHtml(item.culture || "—")}</p>
          <p><strong>Classification:</strong> ${escapeHtml(item.classification || "—")}</p>
          <p><strong>Era:</strong> ${escapeHtml(item.era || "Unknown Era")} (${escapeHtml(
      item.eraSource || "unknown"
    )})</p>
          ${
            item.museumUrl
              ? `<p><a class="link" href="${escapeHtml(item.museumUrl)}" target="_blank" rel="noopener noreferrer">View on Harvard site</a></p>`
              : ""
          }
        </div>
      </section>
    `;

    const modalBtn = document.getElementById("open-detail-modal");
    modalBtn?.addEventListener("click", () => {
      if (typeof detailDialog.showModal === "function") detailDialog.showModal();
    });
  }

  function renderNotFound(message) {
    renderBreadcrumbs([{ label: "Home", href: "#/" }, { label: "Not found" }]);
    appEl.innerHTML = `<section class="state error">${escapeHtml(message)}</section>`;
  }

  function renderCurrentRoute() {
    if (state.loading) return;
    if (!state.dataset) return setErrorUi(state.error || "Dataset not loaded");

    const route = parseHash();
    if (route.name === "home") return renderHome();
    if (route.name === "classification") return renderClassification(route.classificationId);
    if (route.name === "era") return renderEra(route.classificationId, route.eraId);
    if (route.name === "artwork") return renderArtworkDetail(route.artworkId);
    return renderNotFound("Page not found.");
  }

  refreshBtn.addEventListener("click", () => {
    loadDataset();
  });

  async function callAdminApi(payload) {
    const adminApiUrl = window.APP_CONFIG?.adminApiUrl || "";
    if (!adminApiUrl) {
      alert("Admin API URL is not configured. Set APP_CONFIG.adminApiUrl in frontend/config.js");
      return null;
    }

    if (!state.adminToken) {
      openAdminLoginDialog();
      return null;
    }

    const res = await fetch(adminApiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-admin-token": state.adminToken,
      },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = { raw: text };
    }

    if (res.status === 401) {
      saveAdminToken("");
      alert("Admin token was rejected.");
      return null;
    }
    if (!res.ok) {
      alert(`Admin action failed (${res.status}): ${parsed?.message || text}`);
      return null;
    }
    return parsed;
  }

  adminRefreshBtn?.addEventListener("click", async () => {
    const result = await callAdminApi({ action: "refresh-now" });
    if (result) {
      const msg =
        result.status === "cooldown"
          ? `Cooldown active. Retry in ${result.retryAfterSeconds}s`
          : "Refresh request accepted.";
      alert(msg);
    }
  });

  scheduleBtn?.addEventListener("click", async () => {
    const preset = schedulePresetEl?.value || "hourly";
    const result = await callAdminApi({ action: "set-schedule", preset });
    if (result) {
      alert(`Schedule updated to ${result.scheduleExpression || preset}`);
    }
  });

  function setLoginError(msg) {
    if (!msg) {
      adminLoginError?.classList.add("hidden");
      adminLoginError.textContent = "";
      return;
    }
    adminLoginError?.classList.remove("hidden");
    adminLoginError.textContent = msg;
  }

  function openAdminLoginDialog() {
    setLoginError("");
    adminTokenInput.value = "";
    if (typeof adminLoginDialog.showModal === "function") {
      adminLoginDialog.showModal();
    }
  }

  async function verifyAdminToken(token) {
    const adminApiUrl = window.APP_CONFIG?.adminApiUrl || "";
    if (!adminApiUrl) {
      throw new Error("Admin API URL is not configured.");
    }
    const res = await fetch(adminApiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-admin-token": token,
      },
      body: JSON.stringify({ action: "auth-check" }),
    });
    if (!res.ok) {
      if (res.status === 401) {
        throw new Error("Invalid admin token.");
      }
      throw new Error(`Login failed (${res.status}).`);
    }
    return true;
  }

  adminLoginBtn?.addEventListener("click", () => {
    openAdminLoginDialog();
  });

  adminLogoutBtn?.addEventListener("click", () => {
    saveAdminToken("");
    alert("Admin logged out.");
  });

  adminLoginForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const token = (adminTokenInput?.value || "").trim();
    if (!token) {
      setLoginError("Please enter admin token.");
      return;
    }
    try {
      await verifyAdminToken(token);
      saveAdminToken(token);
      adminLoginDialog.close();
      alert("Admin login successful.");
    } catch (err) {
      setLoginError(err?.message || "Login failed.");
    }
  });

  window.addEventListener("hashchange", renderCurrentRoute);
  initAdminToken();
  loadDataset();
})();
