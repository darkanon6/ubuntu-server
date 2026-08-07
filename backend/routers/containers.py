from datetime import datetime, timezone

import docker
from docker.errors import DockerException
from fastapi import APIRouter, HTTPException

router = APIRouter()


def _client() -> docker.DockerClient:
    return docker.from_env()


def _format_ports(ports: dict) -> list[str]:
    formatted = []
    for container_port, bindings in (ports or {}).items():
        if not bindings:
            formatted.append(container_port)
            continue
        for binding in bindings:
            host_ip = binding.get("HostIp") or "0.0.0.0"
            host_port = binding.get("HostPort")
            formatted.append(f"{host_ip}:{host_port} -> {container_port}")
    return formatted


def _uptime_seconds(started_at: str) -> float | None:
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return (datetime.now(timezone.utc) - started).total_seconds()


@router.get("/containers")
def list_containers():
    try:
        containers = _client().containers.list(all=True)
    except DockerException as exc:
        raise HTTPException(status_code=502, detail=f"Docker unavailable: {exc}") from exc

    result = []
    for container in containers:
        attrs = container.attrs
        state = attrs.get("State", {})
        image_tags = container.image.tags
        result.append(
            {
                "id": container.short_id,
                "name": container.name,
                "status": container.status,
                "image": image_tags[0] if image_tags else container.image.short_id,
                "ports": _format_ports(attrs.get("NetworkSettings", {}).get("Ports", {})),
                "restart_count": attrs.get("RestartCount", 0),
                "uptime_seconds": _uptime_seconds(state.get("StartedAt")) if state.get("Running") else None,
            }
        )

    result.sort(key=lambda c: c["name"])
    return result
