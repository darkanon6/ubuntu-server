import asyncio
import os

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

NETDATA_URL = os.environ.get("NETDATA_URL", "http://localhost:19999").rstrip("/")


async def _get_json(client: httpx.AsyncClient, path: str, **params) -> dict:
    response = await client.get(f"{NETDATA_URL}{path}", params=params)
    response.raise_for_status()
    return response.json()


async def _latest_chart_values(client: httpx.AsyncClient, chart: str) -> dict[str, float]:
    data = await _get_json(client, "/api/v1/data", chart=chart, points=1, format="json")
    labels = data.get("labels", [])[1:]  # drop leading "time" column
    row = data.get("data") or [[]]
    values = row[0][1:]
    return dict(zip(labels, values))


async def _find_root_disk_chart(client: httpx.AsyncClient) -> str | None:
    charts = await _get_json(client, "/api/v1/charts")
    for chart_id, chart in charts.get("charts", {}).items():
        if chart_id.startswith("disk_space.") and chart.get("family") == "/":
            return chart_id
    return None


async def _empty_dict() -> dict[str, float]:
    return {}


@router.get("/system")
async def system_stats():
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            disk_chart = await _find_root_disk_chart(client)
            cpu, ram, net, disk = await asyncio.gather(
                _latest_chart_values(client, "system.cpu"),
                _latest_chart_values(client, "system.ram"),
                _latest_chart_values(client, "system.net"),
                _latest_chart_values(client, disk_chart) if disk_chart else _empty_dict(),
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Netdata unavailable: {exc}") from exc

    ram_used = ram.get("used", 0)
    ram_total = sum(ram.values())
    disk_used = disk.get("used", 0)
    disk_total = sum(v for k, v in disk.items() if k in ("avail", "used"))

    return {
        "cpu_percent": round(100 - cpu.get("idle", 0), 1),
        "ram": {
            "used_mb": round(ram_used, 1),
            "total_mb": round(ram_total, 1),
            "percent": round(ram_used / ram_total * 100, 1) if ram_total else None,
        },
        "disk": {
            "used_gb": round(disk_used, 2),
            "total_gb": round(disk_total, 2),
            "percent": round(disk_used / disk_total * 100, 1) if disk_total else None,
        },
        "net": {
            "received_kbps": round(abs(net.get("received", 0)), 1),
            "sent_kbps": round(abs(net.get("sent", 0)), 1),
        },
    }
