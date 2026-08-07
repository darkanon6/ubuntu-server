document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

async function loadSystem() {
  const list = document.getElementById("system");
  try {
    const res = await fetch("/api/system");
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    const s = await res.json();

    list.innerHTML = "";
    const items = [
      `CPU: ${s.cpu_percent}%`,
      `RAM: ${s.ram.used_mb} / ${s.ram.total_mb} MB (${s.ram.percent}%)`,
      `Disk: ${s.disk.used_gb} / ${s.disk.total_gb} GB (${s.disk.percent}%)`,
      `Net: ↓ ${s.net.received_kbps} kb/s ↑ ${s.net.sent_kbps} kb/s`,
    ];
    for (const text of items) {
      const li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li>Failed to load system stats: ${err.message}</li>`;
  }
}

async function loadContainers() {
  const list = document.getElementById("containers");
  try {
    const res = await fetch("/api/containers");
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    const containers = await res.json();

    list.innerHTML = "";
    if (containers.length === 0) {
      list.innerHTML = "<li>No containers found.</li>";
      return;
    }
    for (const c of containers) {
      const ports = c.ports.length ? c.ports.join(", ") : "no published ports";
      const li = document.createElement("li");
      li.textContent = `${c.name} — ${c.status} — ${ports}`;
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li>Failed to load containers: ${err.message}</li>`;
  }
}

loadSystem();
loadContainers();
