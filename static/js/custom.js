// Sidebar + theme picker interactivity.
(function () {
  const THEME_KEY = "adminlte-shiny-theme";

  const themes = {
    "light-blue":   { label: "Ocean Blue", mode: "Light", color: "#2563eb" },
    "light-green":  { label: "Fresh Green", mode: "Light", color: "#16a34a" },
    "light-purple": { label: "Soft Purple", mode: "Light", color: "#7c3aed" },
    "light-orange": { label: "Warm Orange", mode: "Light", color: "#ea580c" },
    "light-teal":   { label: "Calm Teal", mode: "Light", color: "#0f766e" },
    "light-rose":   { label: "Elegant Rose", mode: "Light", color: "#e11d48" },
    "dark-slate":   { label: "Midnight Slate", mode: "Dark", color: "#3b82f6" },
    "dark-ocean":   { label: "Deep Ocean", mode: "Dark", color: "#06b6d4" },
    "dark-emerald": { label: "Emerald Night", mode: "Dark", color: "#22c55e" },
    "dark-purple":  { label: "Royal Night", mode: "Dark", color: "#a78bfa" },
    "dark-amber":   { label: "Amber Night", mode: "Dark", color: "#f59e0b" },
    "dark-rose":    { label: "Rose Night", mode: "Dark", color: "#fb7185" }
  };

  function applyTheme(name) {
    if (!themes[name]) name = "light-blue";
    document.documentElement.setAttribute("data-theme", name);
    localStorage.setItem(THEME_KEY, name);

    document.querySelectorAll(".theme-option").forEach((el) => {
      el.classList.toggle("active", el.dataset.theme === name);
    });

    const current = themes[name];
    const label = document.querySelector("#theme-current-label");
    const swatch = document.querySelector("#theme-current-swatch");
    if (label) label.textContent = current.label;
    if (swatch) swatch.style.background = current.color;
  }

  function buildThemePicker() {
    const picker = document.querySelector(".theme-picker");
    if (!picker || picker.dataset.ready === "true") return;
    picker.dataset.ready = "true";

    const menu = picker.querySelector(".theme-menu");
    const button = picker.querySelector(".theme-button");

    const lightContainer = menu.querySelector(".theme-options-light");
    const darkContainer = menu.querySelector(".theme-options-dark");

    Object.entries(themes).forEach(([name, theme]) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "theme-option";
      option.dataset.theme = name;
      option.innerHTML = `
        <span class="theme-dot" style="background:${theme.color}"></span>
        <span class="theme-meta">
          <span>${theme.label}</span>
          <small>${theme.mode} theme</small>
        </span>`;
      option.addEventListener("click", () => {
        applyTheme(name);
        menu.classList.remove("open");
      });
      (theme.mode === "Light" ? lightContainer : darkContainer).appendChild(option);
    });

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      menu.classList.toggle("open");
    });

    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) menu.classList.remove("open");
    });

    const saved = localStorage.getItem(THEME_KEY) || "light-blue";
    applyTheme(saved);
  }

  function submitLoginForm() {
    // Push current field values to Shiny first, then fire a dedicated login trigger.
    // This avoids the race where the login handler runs before username/password update.
    if (!window.Shiny) return;

    const userEl = document.getElementById("login_username");
    const passEl = document.getElementById("login_password");
    const captchaEl = document.getElementById("login_captcha");
    const username = userEl ? userEl.value : "";
    const password = passEl ? passEl.value : "";
    const captcha = captchaEl ? captchaEl.value : "";

    Shiny.setInputValue("login_username", username, { priority: "event" });
    Shiny.setInputValue("login_password", password, { priority: "event" });
    Shiny.setInputValue("login_captcha", captcha, { priority: "event" });
    // Unique timestamp forces the reactive event to run every attempt.
    Shiny.setInputValue("login_submit", Date.now(), { priority: "event" });
  }

  function bindLoginEnterKey() {
    // Allow pressing Enter in the username/password fields to trigger Sign in.
    const card = document.querySelector(".login-card");
    if (!card || card.dataset.enterBound === "true") return;
    card.dataset.enterBound = "true";

    card.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;

      const target = event.target;
      if (!target || !target.matches("input")) return;

      event.preventDefault();
      submitLoginForm();
    });
  }

  function bindLoginButtonFlush() {
    // Intercept Sign in clicks so values are flushed before authentication runs.
    if (window.__loginButtonBound) return;
    window.__loginButtonBound = true;

    document.addEventListener(
      "click",
      function (event) {
        const button = event.target.closest("#login_button");
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();
        submitLoginForm();
      },
      true
    );
  }

  function init() {
    buildThemePicker();
    bindLoginEnterKey();
    bindLoginButtonFlush();

    // Shiny replaces the login/dashboard DOM dynamically. Re-run the theme
    // picker and login Enter-key binder whenever the root UI changes.
    if (!window.__themeObserverInstalled) {
      const observer = new MutationObserver(() => {
        buildThemePicker();
        bindLoginEnterKey();
      });
      observer.observe(document.body, { childList: true, subtree: true });
      window.__themeObserverInstalled = true;
    }

    // Actual tab links: tell the Shiny server which panel to show.
    document.addEventListener("click", function (event) {
      const link = event.target.closest(".sidebar-link[data-nav-id]");
      if (!link) return;

      event.preventDefault();
      document.querySelectorAll(".sidebar-link[data-nav-id]")
        .forEach((el) => el.classList.remove("active"));
      link.classList.add("active");

      const navId = link.getAttribute("data-nav-id");
      if (window.Shiny) {
        Shiny.setInputValue("sidebar_nav", navId, { priority: "event" });
      }
    });

    // CAPTCHA refresh button on the login form.
    if (!window.__captchaRefreshBound) {
      window.__captchaRefreshBound = true;
      document.addEventListener("click", function (event) {
        const btn = event.target.closest("#captcha_refresh_btn");
        if (!btn || !window.Shiny) return;
        event.preventDefault();
        Shiny.setInputValue("captcha_refresh", Date.now(), { priority: "event" });
      });
    }

    // User table actions: Change opens edit modal, Delete confirms then removes.
    if (!window.__userActionsBound) {
      window.__userActionsBound = true;
      document.addEventListener("click", function (event) {
        const editBtn = event.target.closest(".user-action-edit");
        if (editBtn && window.Shiny) {
          event.preventDefault();
          const userId = editBtn.getAttribute("data-user-id");
          Shiny.setInputValue("user_action_edit", userId, { priority: "event" });
          return;
        }

        const deleteBtn = event.target.closest(".user-action-delete");
        if (deleteBtn && window.Shiny) {
          event.preventDefault();
          const userId = deleteBtn.getAttribute("data-user-id");
          const username = deleteBtn.getAttribute("data-username") || userId;
          if (!window.confirm("Delete user \"" + username + "\"? This cannot be undone.")) {
            return;
          }
          Shiny.setInputValue("user_action_delete", userId, { priority: "event" });
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
