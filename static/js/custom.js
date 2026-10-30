// Sidebar + theme picker interactivity.
(function () {
  const THEME_KEY = "adminlte-shiny-theme";

  // localStorage can be missing or throw (private mode, blocked site data).
  // The page must keep working without it, so every access goes through these.
  function storeGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function storeSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* ignore */ }
  }

  // Translated UI strings injected by app.py as window.APP_I18N (see i18n.py).
  // Every lookup falls back to the English text, so the script still works
  // when APP_I18N is missing.
  function i18n(key, fallback) {
    const bundle = window.APP_I18N || {};
    return bundle[key] !== undefined ? bundle[key] : fallback;
  }

  function themeLabel(name, theme) {
    const names = (window.APP_I18N && window.APP_I18N.themes) || {};
    return names[name] || theme.label;
  }

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
    const root = document.documentElement;
    root.setAttribute("data-theme", name);
    // Bootstrap 5.3 has a built-in dark palette for every component (forms,
    // modals, cards, dropdowns, close buttons ...). Switching it together with
    // our theme means widgets we did not style by hand still follow the theme.
    root.setAttribute("data-bs-theme", themes[name].mode === "Dark" ? "dark" : "light");
    storeSet(THEME_KEY, name);

    document.querySelectorAll(".theme-option").forEach((el) => {
      el.classList.toggle("active", el.dataset.theme === name);
    });

    const current = themes[name];
    const label = document.querySelector("#theme-current-label");
    const swatch = document.querySelector("#theme-current-swatch");
    if (label) label.textContent = themeLabel(name, current);
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
          <span>${themeLabel(name, theme)}</span>
          <small>${theme.mode === "Light"
            ? i18n("theme_light_suffix", "Light theme")
            : i18n("theme_dark_suffix", "Dark theme")}</small>
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

    const saved = storeGet(THEME_KEY) || "light-blue";
    applyTheme(saved);
  }

  // ---- Top bar clock --------------------------------------------------------
  // Date, weekday and time (hours:minutes, no seconds) of the DEVICE clock (the
  // browser's system time), checked every second so the minute flips on time:
  //   Persian (window.APP_LANG === "fa")  ->  Jalali date, weekday name, time
  //   English                              ->  Gregorian date, weekday, time
  // The Jalali calendar comes from the browser's own Intl support
  // ("fa-IR-u-ca-persian"), so no library or server round-trip is needed.
  let clockFormatters = null;

  function getClockFormatters() {
    if (clockFormatters) return clockFormatters;
    const isFa = (window.APP_LANG || "en") === "fa";
    const time = { hour: "2-digit", minute: "2-digit", hourCycle: "h23" };  // minutes only
    clockFormatters = isFa
      ? {
          weekday: new Intl.DateTimeFormat("fa-IR-u-ca-persian", { weekday: "long" }),
          date: new Intl.DateTimeFormat("fa-IR-u-ca-persian",
            { year: "numeric", month: "2-digit", day: "2-digit" }),
          time: new Intl.DateTimeFormat("fa-IR", time)
        }
      : {
          weekday: new Intl.DateTimeFormat("en-US", { weekday: "long" }),
          // en-CA prints the Gregorian date as YYYY-MM-DD (unambiguous).
          date: new Intl.DateTimeFormat("en-CA",
            { year: "numeric", month: "2-digit", day: "2-digit" }),
          time: new Intl.DateTimeFormat("en-GB", time)
        };
    return clockFormatters;
  }

  function updateClock() {
    const el = document.getElementById("topbar-datetime-text");
    if (!el) return;
    try {
      const f = getClockFormatters();
      const now = new Date();
      const text = [f.weekday.format(now), f.date.format(now), f.time.format(now)].join(" \u00b7 ");
      if (el.textContent !== text) el.textContent = text;
    } catch (e) {
      el.textContent = "";  // very old browser without Intl calendars: show nothing
    }
  }

  function startClock() {
    if (window.__clockTimer) return;
    window.__clockTimer = setInterval(updateClock, 1000);
    updateClock();
  }

  // ---- Sidebar toggle -------------------------------------------------------
  // The menu is a plain element (<aside id="app-sidebar">); collapsing it is a
  // CSS class on .app-shell ("sidebar-collapsed"). Desktop remembers the choice;
  // on phones the menu starts closed and slides over the content.
  const SIDEBAR_KEY = "adminlte-shiny-sidebar";
  const mobileQuery = window.matchMedia("(max-width: 767.98px)");

  function setSidebarCollapsed(collapsed, persist) {
    const shell = document.querySelector(".app-shell");
    if (!shell) return;
    shell.classList.toggle("sidebar-collapsed", collapsed);
    const btn = document.getElementById("sidebar-toggle-btn");
    if (btn) {
      btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      btn.classList.toggle("is-collapsed", collapsed);
    }
    if (persist && !mobileQuery.matches) {
      storeSet(SIDEBAR_KEY, collapsed ? "closed" : "open");
    }
  }

  function setupSidebarToggle() {
    const btn = document.getElementById("sidebar-toggle-btn");
    if (!btn || btn.dataset.ready === "true") return;
    btn.dataset.ready = "true";

    const saved = storeGet(SIDEBAR_KEY);
    setSidebarCollapsed(mobileQuery.matches ? true : saved === "closed", false);

    btn.addEventListener("click", () => {
      const shell = document.querySelector(".app-shell");
      if (shell) setSidebarCollapsed(!shell.classList.contains("sidebar-collapsed"), true);
    });

    if (!window.__sidebarGlobalsBound) {
      window.__sidebarGlobalsBound = true;
      // Tap outside the menu (phones) closes it; so does choosing a page.
      document.addEventListener("click", (event) => {
        if (!mobileQuery.matches) return;
        if (event.target.closest("#sidebar-backdrop") || event.target.closest(".sidebar-link[data-nav-id]")) {
          setSidebarCollapsed(true, false);
        }
      });
      // Rotating a tablet / resizing the window switches between the two modes.
      mobileQuery.addEventListener("change", (event) => {
        const pref = storeGet(SIDEBAR_KEY);
        setSidebarCollapsed(event.matches ? true : pref === "closed", false);
      });
    }
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


  // ---------- Font picker (Body / Headings / Navigation) ----------
  const FONT_KEY = "adminlte-shiny-fonts";

  const FONTS_RTL = [
    { id: "vazirmatn", label: "Vazirmatn" },
    { id: "shabnam", label: "Shabnam" },
    { id: "samim", label: "Samim" },
    { id: "sahel", label: "Sahel" },
    { id: "byekan", label: "BYekan" },
    { id: "system", label: "System UI" }
  ];

  const FONTS_LTR = [
    { id: "inter", label: "Inter" },
    { id: "roboto", label: "Roboto" },
    { id: "ibm-plex-sans", label: "IBM Plex Sans" },
    { id: "source-sans-3", label: "Source Sans 3" },
    { id: "system", label: "System UI" }
  ];

  function currentFontList() {
    const mode = (window.APP_DIR_MODE || document.documentElement.getAttribute("dir") || "ltr").toLowerCase();
    const list = mode === "rtl" ? FONTS_RTL : FONTS_LTR;
    // Resolve the translated label now (not at load time): window.APP_I18N is
    // defined by an inline script that runs after this file is parsed.
    return list.map((f) =>
      f.id === "system" ? { ...f, label: i18n("font_system", f.label) } : f
    );
  }

  function defaultFonts() {
    const mode = (window.APP_DIR_MODE || document.documentElement.getAttribute("dir") || "ltr").toLowerCase();
    if (mode === "rtl") {
      return { ui: "vazirmatn", heading: "inherit", nav: "inherit" };
    }
    return { ui: "inter", heading: "inherit", nav: "inherit" };
  }

  function loadFontSettings() {
    try {
      const raw = storeGet(FONT_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") return { ...defaultFonts(), ...parsed };
      }
    } catch (e) {}
    return defaultFonts();
  }

  function saveFontSettings(settings) {
    storeSet(FONT_KEY, JSON.stringify(settings));
  }

  function applyFonts(settings) {
    const root = document.documentElement;
    root.setAttribute("data-font-ui", settings.ui || "system");
    root.setAttribute("data-font-heading", settings.heading || "inherit");
    root.setAttribute("data-font-nav", settings.nav || "inherit");
  }

  function fillSelect(selectEl, fonts, value, includeInherit) {
    if (!selectEl) return;
    const opts = [];
    if (includeInherit) {
      opts.push({ id: "inherit", label: i18n("font_inherit", "Inherit (Body)") });
    }
    fonts.forEach((f) => opts.push(f));
    selectEl.replaceChildren(...opts.map((f) => {
      const option = document.createElement("option");
      option.value = f.id;
      option.textContent = f.label;
      return option;
    }));
    const allowed = opts.map((f) => f.id);
    selectEl.value = allowed.includes(value) ? value : opts[0].id;
  }

  function buildFontPicker() {
    const picker = document.querySelector(".font-picker");
    if (!picker || picker.dataset.ready === "true") return;
    picker.dataset.ready = "true";

    const menu = picker.querySelector(".font-menu");
    const button = picker.querySelector(".font-button");
    const selUi = document.getElementById("font-select-ui");
    const selHeading = document.getElementById("font-select-heading");
    const selNav = document.getElementById("font-select-nav");

    const fonts = currentFontList();
    let settings = loadFontSettings();

    // Drop saved choices that are not in the current direction list
    const ids = new Set(fonts.map((f) => f.id));
    if (settings.ui !== "system" && !ids.has(settings.ui)) settings.ui = defaultFonts().ui;
    if (settings.heading !== "inherit" && !ids.has(settings.heading)) settings.heading = "inherit";
    if (settings.nav !== "inherit" && !ids.has(settings.nav)) settings.nav = "inherit";

    fillSelect(selUi, fonts, settings.ui, false);
    fillSelect(selHeading, fonts, settings.heading, true);
    fillSelect(selNav, fonts, settings.nav, true);
    applyFonts(settings);
    saveFontSettings(settings);

    function onChange() {
      settings = {
        ui: selUi.value,
        heading: selHeading.value,
        nav: selNav.value
      };
      applyFonts(settings);
      saveFontSettings(settings);
    }

    if (selUi) selUi.addEventListener("change", onChange);
    if (selHeading) selHeading.addEventListener("change", onChange);
    if (selNav) selNav.addEventListener("change", onChange);

    if (button && menu) {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        menu.classList.toggle("open");
        // Close theme menu if open
        document.querySelectorAll(".theme-menu.open").forEach((m) => m.classList.remove("open"));
      });
      document.addEventListener("click", (event) => {
        if (!picker.contains(event.target)) menu.classList.remove("open");
      });
    }
  }


  function init() {
    buildThemePicker();
    buildFontPicker();
    setupSidebarToggle();
    bindLoginEnterKey();
    bindLoginButtonFlush();

    // Shiny replaces the login/dashboard DOM dynamically. Re-run the theme
    // picker and login Enter-key binder whenever the root UI changes.
    if (!window.__themeObserverInstalled) {
      // Shiny updates outputs often (tables, clock text ...). Re-binding on every
      // single DOM mutation wasted work, so it now runs at most once per frame.
      let pending = false;
      const observer = new MutationObserver(() => {
        if (pending) return;
        pending = true;
        window.requestAnimationFrame(() => {
          pending = false;
          buildThemePicker();
          buildFontPicker();
          setupSidebarToggle();
          bindLoginEnterKey();
          updateClock();
        });
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

    // User table actions: Change opens the edit modal, Delete starts the
    // password-confirmed deletion.
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
          // No browser confirm() here: the server answers with the confirmation
          // + password dialogs of @confirm_with_password (auth/confirm.py).
          Shiny.setInputValue("user_action_delete", userId, { priority: "event" });
        }
      });
    }
  }

  // Backups table (Users page): Restore / Download / Delete. The server validates
  // the file name and asks for the password (@confirm_with_password).
  if (!window.__backupActionsBound) {
    window.__backupActionsBound = true;
    document.addEventListener("click", function (event) {
      const btn = event.target.closest(".backup-action");
      if (!btn || !window.Shiny) return;
      event.preventDefault();
      // data-input names the Shiny input to fill (the Logs tab is a module, so its
      // buttons use "tab_logs-logbackup_action"); the Users page uses the default.
      Shiny.setInputValue(btn.getAttribute("data-input") || "backup_action", {
        action: btn.getAttribute("data-action"),
        name: btn.getAttribute("data-name"),
        nonce: Date.now()
      }, { priority: "event" });
    });
  }

  // Safety net for file pickers in right-to-left pages: some browsers scroll the
  // content area far sideways when focus returns from the native file dialog
  // (the page then looks blank). Undo any such jump. See tabs/_forms.py.
  function resetSidewaysScroll() {
    [document.querySelector(".app-main"), document.querySelector(".app-body"),
     document.scrollingElement].forEach((el) => {
      if (el && el.scrollLeft !== 0) {
        el.scrollLeft = 0;
      }
    });
  }
  ["change", "focusin", "cancel"].forEach((type) => {
    document.addEventListener(type, (event) => {
      const t = event.target;
      if (t && t.matches && t.matches("input[type=file]")) {
        resetSidewaysScroll();
        window.requestAnimationFrame(resetSidewaysScroll);
      }
    }, true);
  });

  // The Logs tab (user behaviour report) shows hours / weekdays in the browser's
  // own time zone: tell the server the offset from UTC, in minutes.
  document.addEventListener("shiny:connected", function () {
    if (window.Shiny) {
      Shiny.setInputValue("tab_logs-client_tz", -new Date().getTimezoneOffset());
    }
  });

  // Apply the saved theme immediately (also on the login page, which has no
  // theme picker) so the first paint already uses the right colours.
  applyTheme(storeGet(THEME_KEY) || "light-blue");

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(); startClock(); });
  } else {
    init();
    startClock();
  }
})();
