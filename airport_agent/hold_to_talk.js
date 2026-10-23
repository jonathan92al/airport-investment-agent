// Turns Streamlit's chat-input mic button into hold-to-talk: press starts recording, release submits.
// A quick tap (< 300 ms) leaves the recording running, so the built-in Cancel / Submit buttons still work.
(() => {
  if (window.__holdToTalk) return;
  window.__holdToTalk = true;
  const MIC = '[data-testid="stChatInputMicButton"]';
  const APPROVE = '[data-testid="stChatInputApproveButton"]';
  let heldSince = 0, suppressClick = false;

  document.addEventListener("pointerdown", (e) => {
    const mic = e.target.closest && e.target.closest(MIC);
    if (!mic || mic.disabled || e.button !== 0) return;
    heldSince = Date.now();
    suppressClick = true;           // the click that follows this press must not toggle recording again
    mic.click();
  }, true);

  document.addEventListener("click", (e) => {
    if (suppressClick && e.target.closest && e.target.closest(MIC)) {
      e.stopPropagation(); e.preventDefault();
    }
    suppressClick = false;
  }, true);

  const release = () => {
    if (!heldSince) return;
    const held = Date.now() - heldSince;
    heldSince = 0;
    if (held < 300) return;         // tap: keep recording until the user presses Submit or Cancel
    const t0 = Date.now();
    const timer = setInterval(() => {
      const ok = document.querySelector(APPROVE);
      if (ok && !ok.disabled) { clearInterval(timer); ok.click(); }
      else if (Date.now() - t0 > 3000) clearInterval(timer);
    }, 50);
  };
  window.addEventListener("pointerup", release, true);
  window.addEventListener("pointercancel", release, true);
})();
