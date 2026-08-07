# Project Log — Server Dashboard

A running record of decisions, dead ends, and pivots for the dashboard sub-project specifically. `README.md` covers the server's whole life plus this app; this log is the ongoing decision/pivot history for just the dashboard, going forward. Updated after significant milestones, not every commit.

## 2026-08-07 — Planning and repo layout

Started from `SERVER-DASHBOARD-PROJECT-PLAN.md`, a brief written to define scope before any code got written. Two decisions diverged from the original plan almost immediately:

- The plan's proposed layout nested everything under a `server-dashboard/` folder. Given the plan file already lived at the root of the `ubuntu-server` repo, that repo root became the dashboard root directly instead — no extra nesting.
- Auth mechanism: the plan asked for a recommendation between session-cookie and JWT. Went with session cookies — simplest to implement correctly for a single-user tool, no token refresh/expiry machinery to get wrong for no real benefit at this scale.

## 2026-08-07 — Build steps 1–5, in order

Followed the plan's build order deliberately: skeleton → container status → system stats → auth → terminal, with the terminal explicitly held back until auth was working and confirmed (a web terminal with no auth in front of it is not a small risk).

Each step got smoke-tested locally as it landed, but the dev workspace has no Docker socket and no Netdata instance — so "tested" for steps 2–3 meant confirming the clean-failure path (a `502` with a clear message), not real data.

One real gotcha hit during the auth step: Starlette's `add_middleware` makes the *last*-added middleware the *outermost* layer, not the first. `AuthGateMiddleware` had to be added *before* `SessionMiddleware` — the opposite of the naive guess — otherwise the auth check ran before the session was ever populated, and the app 500'd on every request.

The terminal (step 5) is a reverse proxy — ttyd runs as its own container with no port published to the host at all, reachable only through an authenticated route inside the dashboard's backend. WebSocket connections bypass the shared auth middleware entirely (it's HTTP-only), so that one route checks the session itself before accepting a connection — flagged directly in the code as the one place that's easy to accidentally break during a future refactor.

## 2026-08-07 — Deployment day: three bugs that only showed up on the real server

Deploying to `myserver` (over Tailscale SSH, driven from the dev workspace) surfaced problems that never appeared in local testing, because local testing literally couldn't reach the things that were broken:

- **Port conflict.** 8080, picked during planning, turned out to already be bound by another container (`portfolio`) that isn't in the plan's service table at all. Found via `ss -tlnp` against everything actually listening on the server. Moved to 8090.
- **CPU always read 100%.** The math was `100 - idle%`. The real Netdata instance's `system.cpu` response doesn't include an `idle` dimension, so it silently defaulted to `100 - 0`. Fixed to sum whatever dimensions are actually present when `idle` isn't one of them.
- **The Netdata proxy couldn't reach Netdata.** Using the server's own hostname (`http://myserver:19999`) from inside the dashboard's container resolved to `127.0.1.1` — the *host's* Debian/Ubuntu self-hostname loopback convention, forwarded straight through Docker's DNS. Inside a container that's the container's own loopback, not the host's. Switched to `host.docker.internal` (via `extra_hosts: host-gateway` in the compose file), Docker's actual portable answer to this.
- **The terminal would have been broken for every real user.** ttyd's real client opens with a text-frame JSON handshake before sending anything else. The WebSocket proxy only handled binary frames and crashed on that very first message — `KeyError('bytes')` — before a session could ever start. Every local test had passed because none of them used a real ttyd client to exercise that code path. Fixed by handling both frame types symmetrically in both directions.

None of these were exotic — each one is the kind of thing that only exists at the seam between "code that imports cleanly" and "code that runs against the real thing." The whole reason the deployment checklist existed was to force that seam to actually get crossed before calling any of this done.

## Open

- README and this log are now written. Originally split into a separate `HOMELAB-JOURNEY.md` (full narrative) and a thin `README.md` (front door linking to it), then consolidated into one `README.md` on request — the original planning brief and raw journey source notes are folded in there as phases 1–7, with the dashboard as phase 8. The source documents themselves are kept local-only (not part of this public repo).
- Still open: whether ttyd should keep running as root with a fixed `bash` shell or move to something more scoped (flagged in the original plan, not yet decided).
- Still open: a real browser walkthrough — everything verified so far is `curl` and a raw WebSocket client, not an actual login-and-click-around session.
- No GitHub remote connected yet; repo is local-only (`git init`), consistent with the plan's private-first approach.
