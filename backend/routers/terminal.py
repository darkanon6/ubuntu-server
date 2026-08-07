import asyncio
import os

import httpx
import websockets
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from websockets.exceptions import ConnectionClosed

router = APIRouter()

# ttyd is only reachable on the docker-compose network (no published host
# port) and runs with --base-path /terminal so its own generated URLs
# (index.html, /terminal/token, /terminal/ws) already match this prefix.
TTYD_URL = os.environ.get("TTYD_URL", "http://ttyd:7681").rstrip("/")
TTYD_WS_URL = TTYD_URL.replace("http://", "ws://").replace("https://", "wss://")

_EXCLUDED_REQUEST_HEADERS = {"host", "cookie", "connection"}
_EXCLUDED_RESPONSE_HEADERS = {"content-encoding", "transfer-encoding", "connection"}


@router.api_route("/terminal/{path:path}", methods=["GET", "POST"])
async def proxy_http(path: str, request: Request):
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _EXCLUDED_REQUEST_HEADERS}
    async with httpx.AsyncClient() as client:
        upstream = await client.request(
            request.method,
            f"{TTYD_URL}/{path}",
            params=request.query_params,
            headers=headers,
            content=await request.body(),
        )
    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _EXCLUDED_RESPONSE_HEADERS}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)


@router.websocket("/terminal/ws")
async def proxy_ws(websocket: WebSocket):
    # AuthGateMiddleware doesn't run on websocket-scope connections (it's an
    # HTTP-only Starlette middleware), so the terminal's actual data channel
    # has to check the session itself. This is the one path where auth is
    # NOT enforced by the shared middleware — verify it explicitly.
    if not websocket.session.get("authenticated"):
        await websocket.close(code=4401)
        return

    await websocket.accept(subprotocol="tty")

    try:
        async with websockets.connect(f"{TTYD_WS_URL}/terminal/ws", subprotocols=["tty"]) as upstream:

            async def client_to_upstream():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await upstream.send(data)
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client():
                try:
                    async for message in upstream:
                        await websocket.send_bytes(message)
                except ConnectionClosed:
                    pass

            done, pending = await asyncio.wait(
                [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except OSError:
        # ttyd unreachable (not running / network issue) — close, don't crash.
        pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed
