(() => {
  const status = document.getElementById("status");
  const activation = new URLSearchParams(window.location.hash.slice(1));
  const name = activation.get("name");
  const key = activation.get("key");

  window.history.replaceState(null, "", window.location.pathname);

  if (!name || !key) {
    status.textContent = "Tautan aktivasi tidak lengkap.";
    return;
  }

  const form = new URLSearchParams({ name, key });
  fetch("/license/activate", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
    cache: "no-store",
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(await response.text());
      status.textContent = "Aktivasi berhasil. Membuka ValuasiOto...";
      window.location.replace("/");
    })
    .catch((error) => {
      status.textContent = error.message || "Aktivasi gagal. Periksa kembali lisensi Anda.";
    });
})();
