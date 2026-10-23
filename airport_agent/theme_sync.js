// Mirrors Streamlit's active theme onto <html data-p-theme="light|dark"> so the custom CSS palette follows it live,
// including the in-app theme switch (which does not rerun the Python script).
(() => {
  if (window.__themeSync) return;
  window.__themeSync = true;
  const apply = () => {
    const app = document.querySelector('[data-testid="stApp"]') || document.body;
    const m = getComputedStyle(app).backgroundColor.match(/\d+(\.\d+)?/g);
    if (!m) return;
    const [r, g, b] = m.map(Number);
    const theme = (0.299 * r + 0.587 * g + 0.114 * b) < 128 ? "dark" : "light";
    if (document.documentElement.dataset.pTheme !== theme) document.documentElement.dataset.pTheme = theme;
  };
  apply();
  new MutationObserver(apply).observe(document.documentElement, { attributes: true, childList: true, subtree: true,
                                                                  attributeFilter: ["class", "style", "data-theme"] });
  setInterval(apply, 400);
})();
