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

loadContainers();
