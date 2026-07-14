(function () {
  const THEME_KEY = "roomsync-theme";

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "dark" ? "☀ Light" : "🌙 Dark";
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY) || "light";
    applyTheme(saved);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        const current = document.documentElement.getAttribute("data-theme");
        const next = current === "dark" ? "light" : "dark";
        localStorage.setItem(THEME_KEY, next);
        applyTheme(next);
      });
    }
  }

  function initQuickSearch() {
    const input = document.querySelector("[data-quick-search]");
    if (!input) return;
    input.addEventListener("input", function () {
      const term = input.value.toLowerCase();
      const table = document.querySelector(input.dataset.quickSearch);
      if (!table) return;
      table.querySelectorAll("tbody tr").forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().includes(term) ? "" : "none";
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initQuickSearch();
  });
})();
