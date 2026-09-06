# The HomeLab Journey

This is the story of turning a small physical PC into an always-on personal server — the services, the security, the tooling, and the pivots along the way, including a custom web dashboard that got built, deployed, and later retired in favor of something simpler. It's written as a build log, not a highlight reel — the dead ends and pivots are included on purpose, because that's most of what actually happened.

**Hardware:** Lenovo ThinkCentre M73 Tiny mini PC (OS installed directly on it)
**OS:** Ubuntu Server


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
- **Wake-on-LAN enabled** — though it only works over wired Ethernet, and the server ran WiFi-only at the time, so WoL sat unused until it gained an Ethernet connection (see Phase 11)
- **Virtualization (Intel VT-x) enabled** — needed later for running VMs (Windows-in-Docker) via QEMU/KVM

## Phase 2 — Reaching it from anywhere

A server that only works from the same WiFi network isn't much of a server. Tailscale went on the machine and every personal device (laptop, phone, iPad) — a private mesh VPN that gives each device a stable `100.x.x.x` address reachable from anywhere, regardless of local network. That mattered specifically because the server lives on a campus network, where DHCP reservations and router admin access aren't realistic options, especially across dorm moves.

MagicDNS turned the stable IPs into a stable hostname — `myserver` — instead of memorizing numbers. SSH was confirmed working from the laptop and, over Tailscale, from the phone and iPad via Termius. DHCP reservation was considered and deliberately skipped for the same campus-network reason Tailscale was chosen in the first place.

## Phase 3 — Containers and management

Docker and Docker Compose went in via the official Docker repository method, and this is where the server started actually doing things:

- **Portainer** — a web UI for Docker itself, at `http://myserver:9000`
- **Netdata** — real-time system and per-container health (CPU, RAM, disk, network), at `http://myserver:19999`, also connected to Netdata Cloud (later replaced by Glances — see Phase 11)
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

## Phase 8 — The dashboard (retired — see Phase 9)

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

**Update — retired.** This dashboard ran on `myserver` for about a month before being decommissioned in favor of [Homarr](https://homarr.dev) — see Phase 9. Nothing here was broken; it was fully deployed and working, deployment bugs and all. A well-maintained, widely-used homepage-style tool covered the "one page linking to everything with live container status" need without the ongoing cost of maintaining custom auth and a terminal proxy just for that. The code, the bugs found, and the setup instructions below are kept as-written for reference.

## Running the dashboard

> This specific instance is no longer deployed on `myserver` (see Phase 9) — the instructions below describe how to self-host this code if you want to run it yourself.

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

## Phase 9 — Replacing the dashboard, then actually locking the server down

The custom dashboard from Phase 8 worked, but got retired in favor of [Homarr](https://homarr.dev) — a homepage-style dashboard that already does "one page linking to every service with live Docker status" well, without maintaining custom auth and a terminal proxy just to get there.

**Setting up Homarr** was mostly a straightforward `docker run` with a persistent config volume and Docker socket access for live container status, with one real gotcha: the current `ghcr.io/homarr-labs/homarr` image hard-requires a `SECRET_ENCRYPTION_KEY` (64-character hex) environment variable that isn't obvious from a quick skim of the setup docs — omit it and the container crash-loops on startup with "Invalid environment variables." Generated one with `openssl rand -hex 32` directly on the server.

Standing up a new front door was a good excuse to finally look at server security properly, since up to this point the only protection was "it's Tailscale-only":

- **SSH** — key-only login, no root login, capped auth attempts, restricted to a single user. One real config gotcha: Ubuntu's `sshd_config` reads `/etc/ssh/sshd_config.d/*.conf` *before* the rest of the main config file, and for any given setting, whichever value sshd sees *first* wins — later duplicates are silently ignored. A root-only `50-cloud-init.conf` already existed in that directory from the original install; naming the new file `10-hardening.conf` made it sort (and load) first, so it actually took effect regardless of what cloud-init had already set.
- **Firewall** — `ufw` had never been touched and was completely inactive on every interface. Set to default-deny incoming / default-allow outgoing, with explicit allows for SSH (both the Tailscale range and the LAN, so a Tailscale outage alone can't cause a full lockout) and Netdata (Tailscale-only — Netdata has no authentication of its own, so no LAN fallback was given).
- **The bigger discovery: Docker bypasses ufw.** Docker inserts its own `iptables` rules ahead of ufw's normal filtering chain for anything it publishes a port for, so `ufw default deny incoming` correctly governs native services (SSH, Netdata) but does *nothing* for Docker-published ports. "ufw enabled" would have been false confidence for almost every service on the box. The real fix: every externally-facing container (Homarr, Portainer, Uptime Kuma, plus code-server and Syncthing at the time) got its published port re-bound to the Tailscale IP specifically instead of `0.0.0.0`, so it simply doesn't listen on the LAN/WAN-facing interfaces at all — structurally unreachable regardless of firewall state. Syncthing needed a different fix than the others, since it runs in Docker's host-networking mode where port-bind flags don't apply; its GUI address is set via an `STGUIADDRESS` environment variable instead.
- **A credential audit** turned up three real findings: Netdata has no authentication at all (confirmed by querying its API with zero credentials and getting full system data back); the Windows-in-Docker web console (Phase 7) had no password set; and code-server's password turned out to be the exact same one as the server's own SSH/sudo login — the password gating a browser-based VS Code instance was also the password gating root-equivalent server access. That specific exposure stopped mattering once code-server was removed entirely (Phase 10), but the habit is worth remembering regardless of what tool it applies to next.

## Phase 10 — Simplifying: dropping Syncthing and code-server for Google Drive

Not long after the security pass, Syncthing and code-server both got retired — Google Drive now covers the "keep files in sync across devices" need Syncthing was solving, and the day-to-day need for code-server (a browser-based dev environment reachable from an iPad) had faded. Both containers and their images were removed, along with their config directories and Syncthing's internal sync-index volume — but not the actual project files those containers had mounted, which were never anything the containers owned in the first place.

Phase 4's and Phase 5's dead ends (the Syncthing path gotcha, the code-server PUID fix) are left as-written above; they were real problems solved at the time, even though the tools they were solving for aren't running anymore.

## Phase 11 — Netdata → Glances, Portainer redeployed, external heartbeat monitoring, and Nextcloud after all

Four more pieces landed in the same post-hardening cleanup, picked back up after a gap where the working chat session that did most of it got lost — a good reminder that this file, not chat history, is the actual record of what happened.

- **Portainer got redeployed.** It had quietly disappeared at some point before this, blamed at the time on "integration issues with Homarr" — a theory that didn't hold up on a second look, since Portainer was never one of Homarr's supported integrations to begin with. The real cause was almost certainly the same Docker hairpin-NAT reachability problem from Phase 9, misdiagnosed as a Portainer-specific issue. Redeployed clean via `docker run` on the internal Docker network, published on the Tailscale IP only, same pattern as everything else. One extra wrinkle: current Portainer CE requires a one-time setup token pulled from the container logs within 5 minutes of first start, not just a username/password — the first token expired before it got used, so the container needed one restart to get a fresh window. It's wired into Homarr as a plain bookmark tile rather than a live-status widget, since no native integration exists for it.
- **Netdata got fully removed and replaced by Glances**, purely to feed Homarr's system-stats widget. The first idea — Homarr's "Synology DiskStation" integration — was a dead end before it started: that integration only talks to real Synology NAS hardware's DSM API, which this Ubuntu box doesn't have. Of the actual options in Homarr's integration list, Beszel would have been redundant with what Netdata already did, and Dash./Dashdot has an open, unfixed upstream bug (a JSON-parse failure on integration creation). Glances had neither problem and got verified working end-to-end before Netdata was touched at all. Only once that was confirmed did Netdata actually come out — package purged, its apt source removed, and the `ufw` rules that existed solely for its port cleaned up along with it.
- **External heartbeat monitoring** was added to catch the server itself going down, from something that isn't also running on the server. Uptime Robot was the first idea and a dead end: its free tier only offers monitors that need Uptime Robot's own servers to reach the target directly, which is impossible here since the server has no publicly-routable address at all. Push/heartbeat monitoring — the only pattern that doesn't require exposing anything — is Uptime Robot Pro-only. Switched to Better Stack instead, which offers heartbeat monitors on its free tier: a cron job on the server pings a Better Stack URL every 5 minutes, and Better Stack alerts if the pings stop arriving. Embedding a Better Stack status page into Homarr via an iframe hit a 404 at first; later resolved. The alert channel for that heartbeat ended up being plain email rather than Discord — Better Stack's free plan only supports Slack and email for notifications, with Discord not offered natively at any tier.
- **Nextcloud actually got deployed**, reversing the "tabled as a bigger future project" call made earlier — running alongside its own database container, reachable the same Tailscale-only way as everything else.
- **Uptime Kuma picked up two more monitors**: the portfolio site and the Gateway Anime API, both already sharing the `homelab-internal` Docker network with Kuma, so they're checked by container name (`http://portfolio:8080`, `http://gateway-anime-api-1:4000`) rather than through Cloudflare — these monitors reflect container health, not the public-facing tunnel path. The Gateway Anime API needed its `/health` endpoint specifically, since the root path 404s. Discord alerts for both are wired up through Kuma's own Discord webhook notification type, which Kuma supports natively (unlike Better Stack above).
- **The server gained a wired Ethernet connection alongside WiFi**, which made the Wake-on-LAN setting from Phase 1 usable for the first time — tested and confirmed working over Ethernet.

## Open items

- [ ] Discord webhook notifications for Uptime Kuma
- [ ] Revisit Wake-on-LAN if the server ever moves to a wired Ethernet connection

The rest of this list as of Phase 11 — the sudo/system password rotation, a backup approach for project files and service configs/volumes, reconciling `~/windows-server/docker-compose.yml`, and evaluating Trivy for image scanning — have since been resolved. The specifics weren't captured in a session that made it into this file, so they're marked done here rather than walked through the way the rest of this log does.

## Explicitly decided against / deferred

- **Samba** — not needed; Filebrowser/code-server/Syncthing already cover file access
- **DHCP reservation** — doesn't fit the campus network situation
- **CasaOS** — considered as a Portainer alternative, passed on to stay closer to raw Docker for the sake of actually learning it
- **A Windows client (10/11) container alongside Windows Server** — decided to just use the existing Windows Server instead
- **OPNsense** for firewall monitoring in Homarr — considered, but it's a router-replacement project (dedicated hardware or a VM with 2+ NICs sitting between the ISP modem and the LAN), not a container to add alongside everything else; tabled rather than adopted
- **Public internet exposure for the dashboard** (Cloudflare Tunnel, etc.) — Tailscale-only for now
