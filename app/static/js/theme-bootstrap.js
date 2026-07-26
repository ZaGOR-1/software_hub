"use strict";

(() => {
  try {
    const theme = window.localStorage.getItem("software-hub-theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
      document.documentElement.setAttribute("data-theme-preference", theme);
    }
  } catch {
    // The CSS system preference remains the safe no-storage fallback.
  }
})();
