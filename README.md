# The Homelab Journey — From Bare Metal to a Web Dashboard

This is the story of turning a small physical PC into an always-on personal server, and eventually building a web dashboard to watch over it. It's written as a build log, not a highlight reel — the dead ends and pivots are included on purpose, because that's most of what actually happened.

**Hardware:** Lenovo ThinkCentre M73 Tiny mini PC, 16GB RAM, 4 cores, 4TB SSD (OS installed directly on it)
**OS:** Ubuntu Server
**Hostname:** `myserver`
**User:** `darkanon6`

**Goals going in:**
- Learn how to actually manage a server, not just use one
- Host personal projects somewhere that isn't a laptop
- Reach it from any device — laptop, phone, iPad — from anywhere
- Keep it online and reachable without babysitting it

## Phase 1 — Getting the hardware to behave

Before anything else could run reliably, the machine itself had to stay on. The first move was masking sleep/suspend/hibernate at the OS level so the server would never nod off on its own:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

Then came the first real dead end: getting into the BIOS at all. F1/F2 went straight to GRUB with no firmware-setup entry in sight, which looked like a legacy-BIOS-vs-UEFI problem. It wasn't. The actual cause was the keyboard — swapping to a different physical keyboard let F1 register properly and the BIOS finally opened. A timing quirk in a keyboard, not a firmware setting, was the blocker the whole time.

Once inside, three settings mattered:
- **After Power Loss → Power On** — the server auto-boots after any power interruption, no manual intervention needed
- **Wake-on-LAN enabled** — though it only works over wired Ethernet, and the server currently runs on WiFi, so WoL sits unused until/unless it gets plugged into Ethernet
- **Virtualization (Intel VT-x) enabled** — needed later for running VMs (Windows-in-Docker) via QEMU/KVM

## Phase 2 — Reaching it from anywhere

A server that only works from the same WiFi network isn't much of a server. Tailscale went on the machine and every personal device (laptop, phone, iPad) — a private mesh VPN that gives each device a stable `100.x.x.x` address reachable from anywhere, regardless of local network. That mattered specifically because the server lives on a campus network, where DHCP reservations and router admin access aren't realistic options, especially across dorm moves.

MagicDNS turned the stable IPs into a stable hostname — `myserver` — instead of memorizing numbers. SSH was confirmed working from the laptop and, over Tailscale, from the phone and iPad via Termius. DHCP reservation was considered and deliberately skipped for the same campus-network reason Tailscale was chosen in the first place.

## Phase 3 — Containers and management

Docker and Docker Compose went in via the official Docker repository method, and this is where the server started actually doing things:

- **Portainer** — a web UI for Docker itself, at `http://myserver:9000`
- **Netdata** — real-time system and per-container health (CPU, RAM, disk, network), at `http://myserver:19999`, also connected to Netdata Cloud
- **Uptime Kuma** — a basic ping monitor, at `http://myserver:3001`

Discord webhook notifications for Uptime Kuma were planned but deferred — still on the open-items list.

## Phase 4 — File access, which took two tries

The first attempt at file access was Filebrowser — a simple web UI for browsing files on any device. It worked, but it got replaced once code-server (Phase 5) took over as the day-to-day way into the server's filesystem, making a separate file browser redundant.

What stuck was **Syncthing**: real-time, bidirectional folder sync between the laptop and the server, so there's no manual `git push`/`pull` needed just to keep files in parity. It runs in Docker with the entire home directory mounted, so any folder can be shared without reconfiguring the container per-folder. The gotcha that cost some time here: server-side paths have to be given exactly as they appear *inside* the container (`/var/syncthing/home/...`), which maps to the real `~/...` on the server — repeating the username in the path, which felt like the intuitive thing to do, just breaks it.

## Phase 5 — A dev environment that works from an iPad

The goal was full development capability from any device, including an iPad, which can't run a desktop IDE. **code-server** (browser-based VS Code) solved that, but not on the first try:

- Built as a custom Docker image with OpenJDK 21 + Maven baked in directly, so the JDK didn't need reinstalling every session.
- The whole home directory got mounted (`~` → `/home/coder/server-files`) so every folder — projects, synced files, everything — shows up without per-folder mounts.
- **The permissions dead end:** file access inside code-server was broken until PUID/PGID were explicitly set to match the real server user (`1000:1000`). Without that alignment, the container's view of file ownership didn't match reality and things silently failed to be writable/readable correctly.
- The GitHub Copilot Chat extension got removed — it kept nagging for sign-in and wasn't being used.
- Git identity (`user.name`, `user.email`) had to be set *inside* the running container, which turned out to be a trap: it's container-level state, not persisted to a volume, so it resets every time the container is recreated. Baking it into the Dockerfile is on the list if the re-setup ever gets annoying enough.

Two tools were tried and dropped along the way. **JetBrains Gateway** was set up and tested for remote IntelliJ access, then abandoned — syncing files straight to the laptop via Syncthing and running IntelliJ natively there turned out to be simpler than any remote-session tooling. And **RustDesk**, originally used to remote into a gaming laptop just to code on it, became unnecessary once code-server + Syncthing meant coding no longer required touching that laptop at all. RustDesk (or GNOME Remote Desktop) is still on the table for actual desktop/GUI access when that's genuinely needed, using Tailscale's direct-IP connection rather than RustDesk's public relay.

## Phase 6 — Housekeeping scripts

Two small scripts made ongoing maintenance less manual:

- **`update-system`** — runs `apt update`, `apt upgrade`, `apt autoremove`/`autoclean` in one shot, and reports whether a reboot is required.
- **`update-services-doc`** — regenerates `~/SERVICES.md`, a live table of every running container and its ports/status. It preserves a manually-editable `## Notes` section across regenerations, so personal notes don't get wiped every run.

## Phase 7 — Windows-in-Docker for security labs (in progress)

For TryHackMe labs and general security learning, the server needed to run actual Windows environments — not "Windows containers" but genuine VMs, via `dockurr/windows` (a real Windows ISO run inside Docker using QEMU/KVM).

Windows Server 2022 went in first and immediately hit a port-mapping bug: the container's own log message printed the wrong port. Diagnosing and fixing it meant writing a proper `docker-compose.yml` at `~/windows-server/`, landing on:
- Web viewer (noVNC): port 8006
- RDP: port 3389 (TCP + UDP)
- Disk preserved at `~/windows-server-data/` (64GB), so it never needs reinstalling

It's currently stopped deliberately (resumable anytime with `cd ~/windows-server && docker compose up -d`). A Windows client (10/11) container is planned but not started — separate compose file, separate data folder, separate ports. The hardware note that shaped this: 16GB RAM / 4 cores is enough for one Windows VM at a time alongside the lightweight services, but not for Server and client simultaneously — the plan is to start/stop whichever a given lab needs.

## Phase 8 — The dashboard (the current chapter)

Everything above was infrastructure. This phase is about building something to look *at* it — a single-pane web dashboard for container status, system stats, and a browser-based terminal, secured behind a login. It also doubles as this repo you're reading.

The build followed a strict order on purpose: skeleton first, then read-only data (containers, then system stats), then auth, and only *then* the terminal — deliberately last, because a web terminal with no auth in front of it is a very bad idea, and the plan was explicit that the terminal must not be built until auth is working and confirmed.

- **FastAPI skeleton** — a plain app serving a placeholder page, confirmed working before anything else got added.
- **Container status** (`/api/containers`) — via the Docker SDK against the host's Docker socket: name, status, ports, restart count, uptime.
- **System stats** (`/api/system`) — proxying and aggregating Netdata's existing API rather than re-implementing metric collection, matching the plan's explicit "don't duplicate stat collection."
- **Auth** — a session-cookie login gating the entire app, including every API route, verified end-to-end (redirect when logged out, 401 on API calls, successful login, logout revoking the session) before the terminal was allowed to be built at all.
- **Terminal** — ttyd, run as its own container with no port published to the host, reachable *only* through an authenticated reverse proxy inside the dashboard's own backend. The one place auth isn't covered by the shared middleware (WebSocket connections bypass it entirely) got its own explicit auth check, called out directly in the code as the one spot that's easy to accidentally break later.

None of that was fully trustworthy until it ran on the actual server, and deploying it surfaced three real bugs that never showed up in local testing (the dev machine has no Docker socket and no Netdata to test against in the first place):

1. **CPU always read 100%.** The code computed CPU usage as `100 - idle%`, but the real server's Netdata response for the CPU chart doesn't include an `idle` dimension at all — so it silently read as `100 - 0`. Fixed to sum the dimensions that are actually present.
2. **The Netdata proxy couldn't reach Netdata.** `http://myserver:19999`, called from *inside* the dashboard's own container, resolved to `127.0.1.1` — which is the *host's* own self-hostname convention (a standard Debian/Ubuntu thing), leaking through Docker's DNS forwarding. Inside a container, `127.0.1.1` is that container's own loopback, not the host's — so the proxy was trying to talk to itself. Fixed with Docker's `host.docker.internal` mechanism, the actual portable way to reach host-published ports from inside a container.
3. **The terminal would have been dead on arrival in a real browser.** ttyd's actual client opens with a text-frame JSON handshake before anything else — the WebSocket proxy only knew how to handle binary frames and crashed immediately on that first message. It never would have shown a working terminal to an actual user; it just happened to look fine in every test that didn't involve a real ttyd instance.

A smaller but still real one: the dashboard's port (8080, picked early in planning) turned out to already be in use on `myserver` by another container that predates this plan and isn't in its service table. Caught with `ss -tlnp` against everything actually listening, moved to 8090.

The lesson underlined by all four: nothing here counted as "working" until it ran against the real Docker socket, the real Netdata instance, and the real ttyd container — clean local failure-path testing is necessary but nowhere near sufficient.

## Running the dashboard

### What it does

- **Container status** — live list of Docker containers on the host: name, status, ports, restart count, uptime.
- **System stats** — CPU, RAM, disk, and network, proxied from the Netdata instance above rather than re-collecting metrics.
- **Web terminal** — an in-browser shell (ttyd) for ad hoc commands on the server, reachable only after logging in.

The whole thing sits behind a login — every page and every API route, including the terminal.

### Tech stack

- **Backend:** Python, FastAPI
- **Docker interaction:** the `docker` Python SDK against the host's Docker socket
- **System stats:** proxied/aggregated from Netdata's REST API
- **Terminal:** [ttyd](https://github.com/tsl0922/ttyd), run as its own container with no port exposed to the host, reachable only through an authenticated reverse proxy in the backend
- **Frontend:** plain HTML/CSS/JS
- **Auth:** session-cookie login, single username/password
- **Deployment:** Docker Compose, `--restart=always`, reachable over Tailscale only (no public port)

### Setup

Requires an existing [Netdata](https://www.netdata.cloud/) instance reachable from the host, and Docker + Docker Compose.

1. Copy `.env.example` to `.env` and fill in real values:
   ```bash
   cp .env.example .env
   ```
   - `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` — the login for the dashboard
   - `SESSION_SECRET_KEY` — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`
   - `NETDATA_URL` — reachable from *inside* the container. The server's own hostname resolves to its own loopback inside a container, not the host — use `http://host.docker.internal:19999` (wired up via `extra_hosts` in `docker-compose.yml`), not `http://<hostname>:19999`.

2. Build and start:
   ```bash
   docker compose up -d --build
   ```

3. Open `http://<host>:8090` and log in.

#### Local development (without Docker)

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
DASHBOARD_USERNAME=... DASHBOARD_PASSWORD=... SESSION_SECRET_KEY=... \
  .venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8090
```

Container status and system stats require a real Docker socket and Netdata instance respectively — without them, those two routes fail cleanly with a `502` rather than crashing.

### Security notes

What's already handled:
- The whole dashboard sits behind a login — every page and every API route, including the terminal's WebSocket connection specifically (it isn't covered by the shared auth middleware, so it checks the session itself).
- Login compares credentials with `secrets.compare_digest` (constant-time) and refuses to start comparing at all if credentials aren't configured — fails closed, not open.
- Secrets live in `.env`, which is gitignored, `.dockerignore`d, and never committed.
- ttyd has no `ports:` mapping in `docker-compose.yml` on purpose; it's reachable only through the dashboard's own authenticated reverse proxy, never directly.
- `/api/containers` only ever returns name/status/image/ports/restart-count/uptime — never full container `attrs` (which can include other containers' environment variables), never logs, never a code-execution path.
- Intended to run reachable only over Tailscale (or an equivalent private network), never with a port opened to the public internet.

Known trade-offs, left as-is on purpose rather than hidden:
- **The Docker socket mount gives this container real power over the whole host.** There's no way around that and still have the container-status feature — treat this container as high-privilege, and don't add unrelated things into the same image later.
- **No rate limiting on `/api/login`.** For a single-user tool that's already gated behind a private network, this was judged an acceptable trade-off over the added complexity of a rate limiter — but it means brute-forcing the password isn't actively slowed down once someone's on the network.
- **ttyd runs as root with a fixed `bash` shell**, not a scoped-down user. Anyone who can log into the dashboard gets a root shell on the host. This is intentional for a personal admin tool, but is exactly why the login above is the only thing standing between "convenient" and "dangerous" — still an open decision whether to scope it down.

## Open items

- [ ] Discord webhook notifications for Uptime Kuma
- [ ] Set up Windows client (10/11) container alongside Windows Server
- [ ] Bake git identity into the code-server Dockerfile so it survives container recreation
- [ ] Revisit Wake-on-LAN if the server ever moves to a wired Ethernet connection
- [ ] Decide whether ttyd should keep running as root with a fixed shell, or move to something more scoped
- [ ] Actually open the dashboard in a browser and click through it (everything so far has been verified via `curl` and a raw WebSocket client, not a real browser session)

## Explicitly decided against / deferred

- **Samba** — not needed; Filebrowser/code-server/Syncthing already cover file access
- **DHCP reservation** — doesn't fit the campus network situation
- **CasaOS** — considered as a Portainer alternative, passed on to stay closer to raw Docker for the sake of actually learning it
- **Nextcloud** — tabled as a bigger, separate future project; would mostly overlap with Filebrowser/Syncthing unless calendar/contacts/photo backup become an actual need
- **Public internet exposure for the dashboard** (Cloudflare Tunnel, etc.) — Tailscale-only for now
