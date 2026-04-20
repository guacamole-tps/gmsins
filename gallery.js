/* ===================================================
   GMS Gallery — Dynamic Gallery Engine
   Reads gallery-data.json, renders date-grouped photos
   =================================================== */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────
  let allData = [];          // full dataset from JSON
  let visibleData = [];      // filtered dataset currently being rendered
  let flatImages = [];       // [{src, date, idx}] for lightbox
  let lightboxIndex = 0;
  let sortAsc = false;       // default: newest first
  let currentPage = 1;       // current page number
  let itemsPerPage = 10;     // dates per page
  let commentsOpen = false;
  let currentDiscussionTerm = "";

  const defaultGiscusConfig = {
    repo: "",
    repoId: "",
    category: "",
    categoryId: "",
    mapping: "specific",
    reactionsEnabled: "1",
    emitMetadata: "0",
    inputPosition: "top",
    theme: "dark_dimmed",
    lang: "en",
  };

  // ── DOM refs ───────────────────────────────────────
  const gallery      = document.getElementById("gallery");
  const emptyState   = document.getElementById("empty-state");
  const loadingState = document.getElementById("loading-state");
  const statDates    = document.getElementById("stat-dates");
  const statImages   = document.getElementById("stat-images");
  const statLatest   = document.getElementById("stat-latest");
  const searchInput  = document.getElementById("search-input");
  const sortBtn      = document.getElementById("sort-btn");
  const lightbox     = document.getElementById("lightbox");
  const lightboxImg  = document.getElementById("lightbox-img");
  const lightboxCap  = document.getElementById("lightbox-caption");
  const lightboxCtr  = document.getElementById("lightbox-counter");
  const lbClose      = document.getElementById("lightbox-close");
  const lbPrev       = document.getElementById("lightbox-prev");
  const lbNext       = document.getElementById("lightbox-next");
  const scrollTop    = document.getElementById("scroll-top");
  const pagination   = document.getElementById("pagination");
  const pageInfo     = document.getElementById("page-info");
  const pageNumbers  = document.getElementById("page-numbers");
  const prevPageBtn  = document.getElementById("prev-page");
  const nextPageBtn  = document.getElementById("next-page");
  const commentsToggleBtn = document.getElementById("lightbox-comments-toggle");
  const commentsPanel = document.getElementById("lightbox-comments-panel");
  const commentsCloseBtn = document.getElementById("lightbox-comments-close");
  const commentsStatus = document.getElementById("comments-status");
  const giscusContainer = document.getElementById("giscus-container");

  // ── Boot ───────────────────────────────────────────
  async function init() {
    try {
      const res = await fetch("gallery-data.json?" + Date.now());
      if (!res.ok) throw new Error("HTTP " + res.status);
      allData = await res.json();
      visibleData = allData;
      loadingState.style.display = "none";
      buildFlatList();
      updateStats();
      render(allData);
      bindEvents();
    } catch (err) {
      loadingState.textContent = "Could not load gallery data — run scan.py first.";
      console.error(err);
    }
  }

  // ── Build flat image list for lightbox nav ─────────
  function buildFlatList() {
    flatImages = [];
    const data = sortAsc ? [...allData].reverse() : allData;
    data.forEach((entry) => {
      entry.images.forEach((src) => {
        flatImages.push({ src, date: entry.date });
      });
    });
  }

  // ── Stats ──────────────────────────────────────────
  function updateStats() {
    const total = allData.reduce((s, d) => s + d.images.length, 0);
    statDates.textContent  = allData.length;
    statImages.textContent = total;
    statLatest.textContent = allData.length ? allData[0].date : "—";
  }

  // ── Render gallery ─────────────────────────────────
  function render(data) {
    visibleData = data;
    gallery.innerHTML = "";
    const ordered = sortAsc ? [...data].reverse() : data;

    if (!ordered.length) {
      emptyState.style.display = "block";
      pagination.style.display = "none";
      return;
    }
    emptyState.style.display = "none";

    // Calculate pagination
    const totalPages = Math.ceil(ordered.length / itemsPerPage);
    if (currentPage > totalPages) currentPage = totalPages;
    const startIdx = (currentPage - 1) * itemsPerPage;
    const endIdx = startIdx + itemsPerPage;
    const pageData = ordered.slice(startIdx, endIdx);

    // Update pagination UI
    updatePaginationUI(totalPages, ordered.length);

    pageData.forEach((entry, sectionIdx) => {
      const section = document.createElement("section");
      section.className = "date-section";
      section.style.animationDelay = sectionIdx * 60 + "ms";

      const dateHeader = document.createElement("div");
      dateHeader.className = "date-header";

      const dateLabel = document.createElement("span");
      dateLabel.className = "date-label";
      dateLabel.textContent = formatDate(entry.date);

      const dateCount = document.createElement("span");
      dateCount.className = "date-count";
      dateCount.textContent = entry.images.length + (entry.images.length === 1 ? " story" : " stories");

      dateHeader.appendChild(dateLabel);
      dateHeader.appendChild(dateCount);

      const grid = document.createElement("div");
      const count = entry.images.length;
      const layoutClass = count === 1 ? "layout-1" : count === 2 ? "layout-2" : count === 3 ? "layout-3" : "layout-many";
      grid.className = "photo-grid " + layoutClass;

      entry.images.forEach((src, imgIdx) => {
        const flatIdx = flatImages.findIndex((f) => f.src === src);
        const card = buildCard(src, entry.date, flatIdx, count > 1 ? imgIdx + 1 : 0, count);
        grid.appendChild(card);
      });

      section.appendChild(dateHeader);
      section.appendChild(grid);
      gallery.appendChild(section);
    });
  }

  // ── Build photo card ───────────────────────────────
  function buildCard(src, date, flatIdx, imgNum, totalInDate) {
    const card = document.createElement("div");
    card.className = "photo-card";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", "Open story from " + date);

    const img = document.createElement("img");
    img.src = src;
    img.alt = "Instagram story — " + date;
    img.loading = "lazy";
    img.decoding = "async";
    img.onload = function () { this.classList.add("loaded"); };

    const overlay = document.createElement("div");
    overlay.className = "card-overlay";
    const overlayText = document.createElement("span");
    overlayText.className = "card-overlay-text";
    overlayText.textContent = "View";
    overlay.appendChild(overlayText);

    card.appendChild(img);
    card.appendChild(overlay);

    if (imgNum > 0 && totalInDate > 1) {
      const badge = document.createElement("span");
      badge.className = "card-index";
      badge.textContent = imgNum + "/" + totalInDate;
      card.appendChild(badge);
    }

    // Add inline comments section
    const commentsSection = document.createElement("div");
    commentsSection.className = "card-comments";
    
    const commentsHeader = document.createElement("div");
    commentsHeader.className = "comments-header";
    commentsHeader.innerHTML = `
      <span class="comments-count">Comments</span>
      <button class="comments-toggle-btn" aria-expanded="false">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
    `;
    
    const commentsContent = document.createElement("div");
    commentsContent.className = "comments-content";
    
    const commentsContainer = document.createElement("div");
    commentsContainer.className = "giscus-inline-container";
    
    const commentsStatus = document.createElement("p");
    commentsStatus.className = "comments-status";
    commentsStatus.textContent = "Loading comments...";
    
    commentsContent.appendChild(commentsStatus);
    commentsContent.appendChild(commentsContainer);
    commentsSection.appendChild(commentsHeader);
    commentsSection.appendChild(commentsContent);
    card.appendChild(commentsSection);

    // Smart comments loading - check for existing comments and auto-expand
    const toggleBtn = commentsHeader.querySelector(".comments-toggle-btn");
    const commentsCount = commentsHeader.querySelector(".comments-count");
    let commentsLoaded = false;
    
    // Set initial collapsed state
    toggleBtn.setAttribute("aria-expanded", "false");
    toggleBtn.style.transform = "rotate(0deg)";
    commentsContent.style.display = "none";
    commentsStatus.textContent = "Add a comment";
    
    // Check if discussion has comments using GitHub API
    async function checkDiscussionComments() {
      const config = getGiscusConfig();
      if (!hasRequiredGiscusConfig(config)) return false;
      
      const item = { src };
      const term = buildDiscussionTerm(item);
      
      try {
        const apiUrl = `https://api.github.com/repos/${config.repo}/discussions?per_page=100`;
        const response = await fetch(apiUrl);
        if (!response.ok) return false;
        
        const discussions = await response.json();
        const discussion = discussions.find(d => 
          d.title.includes(term) && d.comments > 0
        );
        
        return discussion && discussion.comments > 0;
      } catch (error) {
        return false;
      }
    }
    
    // Auto-expand if comments exist
    async function autoExpandIfComments() {
      const hasComments = await checkDiscussionComments();
      
      if (hasComments) {
        // Auto-expand and load comments
        commentsLoaded = true;
        toggleBtn.setAttribute("aria-expanded", "true");
        toggleBtn.style.transform = "rotate(180deg)";
        commentsSection.classList.add("open");
        commentsContent.style.display = "block";
        commentsStatus.textContent = "Loading comments...";
        loadInlineComments(commentsContainer, src, commentsStatus);
      }
    }
    
    // Toggle functionality
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation(); // Prevent opening lightbox
      const isExpanded = toggleBtn.getAttribute("aria-expanded") === "true";
      toggleBtn.setAttribute("aria-expanded", !isExpanded);
      toggleBtn.style.transform = isExpanded ? "rotate(0deg)" : "rotate(180deg)";
      
      if (!isExpanded) {
        commentsSection.classList.add("open");
        commentsContent.style.display = "block";
      } else {
        commentsSection.classList.remove("open");
        commentsContent.style.display = "none";
      }
      
      // Load comments only when user expands
      if (!commentsLoaded && !isExpanded) {
        commentsLoaded = true;
        commentsStatus.textContent = "Loading comments...";
        loadInlineComments(commentsContainer, src, commentsStatus);
      }
    });
    
    // Start checking for comments
    autoExpandIfComments();
    
    
    card.addEventListener("click", () => openLightbox(flatIdx));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") openLightbox(flatIdx);
    });

    return card;
  }

  // ── Date formatter ─────────────────────────────────
  function formatDate(dateStr) {
    try {
      const [y, m, d] = dateStr.split("-").map(Number);
      const date = new Date(y, m - 1, d);
      return date.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  }

  // ── Pagination UI ──────────────────────────────────
  function updatePaginationUI(totalPages, totalItems) {
    if (totalPages <= 1) {
      pagination.style.display = "none";
      return;
    }
    pagination.style.display = "flex";
    
    const startItem = (currentPage - 1) * itemsPerPage + 1;
    const endItem = Math.min(currentPage * itemsPerPage, totalItems);
    pageInfo.textContent = `${startItem}-${endItem} of ${totalItems} dates`;
    
    prevPageBtn.disabled = currentPage === 1;
    nextPageBtn.disabled = currentPage === totalPages;
    renderPageNumbers(totalPages);
  }

  function renderPageNumbers(totalPages) {
    pageNumbers.innerHTML = "";

    for (let page = 1; page <= totalPages; page++) {
      const button = document.createElement("button");
      button.className = "page-number-btn" + (page === currentPage ? " active" : "");
      button.type = "button";
      button.textContent = page;
      button.setAttribute("aria-label", "Go to page " + page);
      button.setAttribute("aria-current", page === currentPage ? "page" : "false");
      button.addEventListener("click", () => goToPage(page));
      pageNumbers.appendChild(button);
    }
  }

  // ── Pagination navigation ──────────────────────────
  function goToPage(page) {
    currentPage = page;
    render(visibleData);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function prevPage() {
    if (currentPage > 1) goToPage(currentPage - 1);
  }

  function nextPage() {
    const totalPages = Math.ceil(visibleData.length / itemsPerPage);
    if (currentPage < totalPages) goToPage(currentPage + 1);
  }

  // ── Search ─────────────────────────────────────────
  function handleSearch(query) {
    const q = query.trim().toLowerCase();
    currentPage = 1;  // Reset to first page
    if (!q) {
      render(allData);
      return;
    }
    const filtered = allData.filter((d) => d.date.includes(q) || formatDate(d.date).toLowerCase().includes(q));
    render(filtered);
  }

  // ── Sort toggle ────────────────────────────────────
  function toggleSort() {
    sortAsc = !sortAsc;
    currentPage = 1;  // Reset to first page
    sortBtn.classList.toggle("active", sortAsc);
    sortBtn.querySelector(".sort-label").textContent = sortAsc ? "Oldest First" : "Newest First";
    buildFlatList();
    render(allData);
  }

  function getGiscusConfig() {
    const userConfig = window.GMS_GISCUS_CONFIG || {};
    return { ...defaultGiscusConfig, ...userConfig };
  }

  function hasRequiredGiscusConfig(config) {
    return Boolean(config.repo && config.repoId && config.category && config.categoryId);
  }

  function buildDiscussionTerm(item) {
    const cleanedSrc = item.src
      .replace(/^pics\//, "")
      .replace(/\.[^.]+$/, "")
      .replace(/[^a-zA-Z0-9/_-]/g, "")
      .replace(/[\/]/g, "-");
    return `story-${cleanedSrc}`;
  }

  function setCommentsStatus(text) {
    commentsStatus.textContent = text || "";
  }

  function clearCommentsEmbed() {
    currentDiscussionTerm = "";
    giscusContainer.innerHTML = "";
    setCommentsStatus("");
  }

  function setCommentsPanelOpen(open) {
    commentsOpen = open;
    commentsPanel.classList.toggle("open", open);
    commentsToggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) return;
    syncCommentsForCurrentImage();
  }

  function mountGiscus(term) {
    const config = getGiscusConfig();
    if (!hasRequiredGiscusConfig(config)) {
      giscusContainer.innerHTML = "";
      setCommentsStatus("Comments are not configured yet. Add Giscus repo/category IDs to enable this panel.");
      return;
    }

    giscusContainer.innerHTML = "";
    setCommentsStatus("Loading comments...");

    const script = document.createElement("script");
    script.src = "https://giscus.app/client.js";
    script.async = true;
    script.crossOrigin = "anonymous";
    script.setAttribute("data-repo", config.repo);
    script.setAttribute("data-repo-id", config.repoId);
    script.setAttribute("data-category", config.category);
    script.setAttribute("data-category-id", config.categoryId);
    script.setAttribute("data-mapping", config.mapping);
    script.setAttribute("data-term", term);
    script.setAttribute("data-reactions-enabled", config.reactionsEnabled);
    script.setAttribute("data-emit-metadata", config.emitMetadata);
    script.setAttribute("data-input-position", config.inputPosition);
    script.setAttribute("data-theme", config.theme);
    script.setAttribute("data-lang", config.lang);
    script.addEventListener("load", () => setCommentsStatus(""));
    giscusContainer.appendChild(script);
  }

  
  function loadInlineComments(container, src, statusElement) {
    const config = getGiscusConfig();
    if (!hasRequiredGiscusConfig(config)) {
      container.innerHTML = "";
      statusElement.textContent = "Comments not configured";
      return;
    }

    container.innerHTML = "";
    statusElement.textContent = "Loading comments...";

    const item = { src };
    const term = buildDiscussionTerm(item);

    const script = document.createElement("script");
    script.src = "https://giscus.app/client.js";
    script.async = true;
    script.crossOrigin = "anonymous";
    script.setAttribute("data-repo", config.repo);
    script.setAttribute("data-repo-id", config.repoId);
    script.setAttribute("data-category", config.category);
    script.setAttribute("data-category-id", config.categoryId);
    script.setAttribute("data-mapping", config.mapping);
    script.setAttribute("data-term", term);
    script.setAttribute("data-reactions-enabled", config.reactionsEnabled);
    script.setAttribute("data-emit-metadata", config.emitMetadata);
    script.setAttribute("data-input-position", "top");
    script.setAttribute("data-theme", config.theme);
    script.setAttribute("data-lang", config.lang);
    script.addEventListener("load", () => statusElement.textContent = "");
    container.appendChild(script);
  }

  function syncCommentsForCurrentImage() {
    if (!commentsOpen) return;
    const item = flatImages[lightboxIndex];
    if (!item) return;

    const nextTerm = buildDiscussionTerm(item);
    if (nextTerm === currentDiscussionTerm) return;

    currentDiscussionTerm = nextTerm;
    mountGiscus(nextTerm);
  }

  // ── Lightbox ───────────────────────────────────────
  function openLightbox(idx) {
    if (idx < 0 || idx >= flatImages.length) return;
    lightboxIndex = idx;
    updateLightboxImage();
    lightbox.classList.add("open");
    document.body.style.overflow = "hidden";
    lightboxImg.focus();
    if (commentsOpen) syncCommentsForCurrentImage();
  }

  function closeLightbox() {
    setCommentsPanelOpen(false);
    clearCommentsEmbed();
    lightbox.classList.remove("open");
    document.body.style.overflow = "";
  }

  function updateLightboxImage() {
    const item = flatImages[lightboxIndex];
    lightboxImg.src = item.src;
    lightboxImg.alt = "Story — " + item.date;
    lightboxCap.textContent = formatDate(item.date);
    lightboxCtr.textContent = (lightboxIndex + 1) + " / " + flatImages.length;
    lbPrev.style.opacity = lightboxIndex === 0 ? "0.3" : "1";
    lbNext.style.opacity = lightboxIndex === flatImages.length - 1 ? "0.3" : "1";
  }

  function lightboxStep(delta) {
    const next = lightboxIndex + delta;
    if (next >= 0 && next < flatImages.length) openLightbox(next);
  }

  // ── Event bindings ─────────────────────────────────
  function bindEvents() {
    searchInput.addEventListener("input", (e) => handleSearch(e.target.value));
    sortBtn.addEventListener("click", toggleSort);
    
    // Pagination events
    prevPageBtn.addEventListener("click", prevPage);
    nextPageBtn.addEventListener("click", nextPage);

    lbClose.addEventListener("click", closeLightbox);
    lbPrev.addEventListener("click", () => lightboxStep(-1));
    lbNext.addEventListener("click", () => lightboxStep(1));

    commentsToggleBtn.addEventListener("click", () => {
      setCommentsPanelOpen(!commentsOpen);
    });
    commentsCloseBtn.addEventListener("click", () => setCommentsPanelOpen(false));

    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) closeLightbox();
    });

    document.addEventListener("keydown", (e) => {
      if (!lightbox.classList.contains("open")) return;
      if (e.key === "Escape")      closeLightbox();
      if (e.key === "ArrowLeft")   lightboxStep(-1);
      if (e.key === "ArrowRight")  lightboxStep(1);
    });

    // Touch swipe support for lightbox
    let touchStartX = 0;
    lightbox.addEventListener("touchstart", (e) => { touchStartX = e.touches[0].clientX; }, { passive: true });
    lightbox.addEventListener("touchend", (e) => {
      const delta = touchStartX - e.changedTouches[0].clientX;
      if (Math.abs(delta) > 50) lightboxStep(delta > 0 ? 1 : -1);
    });

    // Scroll-to-top button
    window.addEventListener("scroll", () => {
      scrollTop.classList.toggle("visible", window.scrollY > 400);
    });
    scrollTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  // ── Start ──────────────────────────────────────────
  init();
})();
