"use strict";

(() => {
  const STORAGE_KEY = "software-hub-theme";
  const THEMES = ["system", "light", "dark"];
  const LABELS = {
    system: "Системна тема",
    light: "Світла тема",
    dark: "Темна тема",
  };
  const ICONS = {
    system: "◐",
    light: "☀",
    dark: "☾",
  };

  const storedTheme = () => {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      return THEMES.includes(value) ? value : "system";
    } catch {
      return "system";
    }
  };

  const saveTheme = (theme) => {
    try {
      if (theme === "system") {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, theme);
      }
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
    }
  };

  const applyTheme = (theme) => {
    if (theme === "system") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", theme);
    }
    document.documentElement.setAttribute("data-theme-preference", theme);

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.hidden = false;
      button.setAttribute("aria-label", `${LABELS[theme]}. Змінити тему`);
      button.setAttribute("title", `${LABELS[theme]}. Змінити тему`);
      const label = button.querySelector("[data-theme-label]");
      const icon = button.querySelector("[data-theme-icon]");
      if (label) {
        label.textContent = LABELS[theme];
      }
      if (icon) {
        icon.textContent = ICONS[theme];
      }
    });
  };

  const nextTheme = (theme) => {
    const currentIndex = THEMES.indexOf(theme);
    return THEMES[(currentIndex + 1) % THEMES.length];
  };

  const initialize = () => {
    let currentTheme = storedTheme();
    applyTheme(currentTheme);

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        currentTheme = nextTheme(currentTheme);
        saveTheme(currentTheme);
        applyTheme(currentTheme);
      });
    });

    window.addEventListener("storage", (event) => {
      if (event.key === STORAGE_KEY) {
        currentTheme = storedTheme();
        applyTheme(currentTheme);
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
