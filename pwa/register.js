(() => {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((error) => {
      console.error("ValuasiOto service worker registration failed:", error);
    });
  });

  let installPrompt;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;

    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Pasang ValuasiOto";
    button.setAttribute("aria-label", "Pasang aplikasi ValuasiOto");
    Object.assign(button.style, {
      position: "fixed",
      right: "16px",
      bottom: "16px",
      zIndex: "99999",
      border: "0",
      borderRadius: "999px",
      padding: "11px 16px",
      background: "#172554",
      color: "#ffffff",
      font: "600 14px system-ui, sans-serif",
      boxShadow: "0 4px 16px rgba(15, 23, 42, .22)",
      cursor: "pointer",
    });
    document.body.appendChild(button);

    button.addEventListener("click", async () => {
      if (!installPrompt) return;
      installPrompt.prompt();
      await installPrompt.userChoice;
      installPrompt = null;
      button.remove();
    });
  });

  window.addEventListener("appinstalled", () => {
    document.querySelectorAll('button[aria-label="Pasang aplikasi ValuasiOto"]')
      .forEach((button) => button.remove());
  });
})();
