# Server Dashboard

This repo is two things at once: the story of building a personal homelab from a bare mini PC to an always-on server, and the web dashboard that now monitors and manages it.

Read **[HOMELAB-JOURNEY.md](./HOMELAB-JOURNEY.md)** for the full story — power reliability, Tailscale networking, Docker services, a remote dev environment, file sync, and the dashboard itself, dead ends included. This README covers just the dashboard: what it does and how to run it.

## What it does

- **Container status** — live list of Docker containers on the host: name, status, ports, restart count, uptime.
- **System stats** — CPU, RAM, disk, and network, proxied from an existing [Netdata](https://www.netdata.cloud/) instance rather than re-collecting metrics.
- **Web terminal** — an in-browser shell ([ttyd](https://github.com/tsl0922/ttyd)) for ad hoc commands on the server, reachable only after logging in.

The whole thing sits behind a login — every page and every API route, including the terminal.

## Tech stack

- **Backend:** Python, FastAPI
- **Docker interaction:** the `docker` Python SDK against the host's Docker socket
- **System stats:** proxied/aggregated from Netdata's REST API
- **Terminal:** [ttyd](https://github.com/tsl0922/ttyd), run as its own container with no port exposed to the host, reachable only through an authenticated reverse proxy in the backend
- **Frontend:** plain HTML/CSS/JS
- **Auth:** session-cookie login, single username/password
- **Deployment:** Docker Compose, `--restart=always`, reachable over Tailscale only (no public port)

## Setup

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

### Local development (without Docker)

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
DASHBOARD_USERNAME=... DASHBOARD_PASSWORD=... SESSION_SECRET_KEY=... \
  .venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8090
```

Container status and system stats require a real Docker socket and Netdata instance respectively — without them, those two routes fail cleanly with a `502` rather than crashing.

## Security notes

- The Docker socket mount gives this container real power over the whole host — treat it as high-privilege, and don't add unrelated things into the same image later.
- ttyd has no `ports:` mapping in `docker-compose.yml` on purpose; it's reachable only through the dashboard's own authenticated proxy.
- Secrets live in `.env`, which is gitignored and never committed.

See [CLAUDE.md](./CLAUDE.md) for the full build history, architecture notes, and everything verification found when this was actually deployed.
