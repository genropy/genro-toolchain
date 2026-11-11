"""docker-compose file for a dockerized instance: postgres plus the app."""

from __future__ import annotations

import json
import re

_PLAIN = re.compile(r"[A-Za-z_./][A-Za-z0-9_./-]*")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "y", "n", "null", "~"}


def traefik_labels(instance_name: str, fqdns: list[str], router: str = "traefik") -> dict:
    """Traefik routing labels for the app service; empty without FQDNs."""
    if not (fqdns and router == "traefik"):
        return {}
    hosts_rule = " || ".join(f"Host(`{fqdn}`)" for fqdn in fqdns)
    name = instance_name
    return {
        "traefik.enable": "true",
        f"traefik.http.routers.{name}_web.rule": f"({hosts_rule}) && !Path(`/websocket`)",
        f"traefik.http.routers.{name}_web.entrypoints": "http",
        f"traefik.http.routers.{name}_web.service": f"{name}_svc_web",
        f"traefik.http.services.{name}_svc_web.loadbalancer.server.port": 8888,
        f"traefik.http.routers.{name}_wsk.rule": f"({hosts_rule}) && Path(`/websocket`)",
        f"traefik.http.routers.{name}_wsk.entrypoints": "http",
        f"traefik.http.routers.{name}_wsk.service": f"{name}_svc_wsk",
        f"traefik.http.services.{name}_svc_wsk.loadbalancer.server.port": 9999,
    }


def compose_document(instance_name: str, image: str, labels: dict | None = None) -> dict:
    """The compose structure; ``image`` is the full ``name:tag`` reference."""
    name = instance_name
    app: dict = {"image": image}
    if labels:
        app["labels"] = dict(labels)
    app["ports"] = ["8888:8888"]
    app["depends_on"] = {f"{name}_db": {"condition": "service_healthy"}}
    app["environment"] = {
        "GNR_DB_IMPLEMENTATION": "postgres",
        "GNR_DB_HOST": f"${{GNR_DB_HOST:-{name}_db}}",
        "GNR_ROOTPWD": "${GNR_ROOTPWD:-admin}",
        "GNR_DB_USER": "${GNR_DB_USER:-genro}",
        "GNR_DB_PORT": "${GNR_DB_PORT:-5432}",
        "GNR_DB_PASSWORD": "${GNR_DB_PASSWORD:-S3cret}",
        "GNR_LOCALE": "IT_it",
    }
    app["volumes"] = [f"{name}_site:/home/genro/site/"]
    return {
        "volumes": {f"{name}_site": {}},
        "services": {
            f"{name}_db": {
                "image": "postgres:latest",
                "environment": {
                    "POSTGRES_PASSWORD": "S3cret",
                    "POSTGRES_USER": "genro",
                    "POSTGRES_DB": name,
                },
                "healthcheck": {
                    "test": ["CMD-SHELL", f"pg_isready -U genro -d {name}"],
                    "interval": "10s",
                    "retries": 5,
                    "start_period": "30s",
                    "timeout": "10s",
                },
            },
            name: app,
        },
    }


def _scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if _PLAIN.fullmatch(text) and text.lower() not in _RESERVED:
        return text
    # A JSON string is a valid YAML double-quoted scalar.
    return json.dumps(text, ensure_ascii=False)


def _emit(value, indent: int, lines: list[str]) -> None:
    pad = "  " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{_scalar(key)}:")
                _emit(item, indent + 1, lines)
            else:
                empty = "{}" if isinstance(item, dict) else "[]"
                text = empty if isinstance(item, (dict, list)) else _scalar(item)
                lines.append(f"{pad}{_scalar(key)}: {text}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}-")
                _emit(item, indent + 1, lines)
            else:
                lines.append(f"{pad}- {_scalar(item)}")


def to_yaml(document: dict, header: str | None = None) -> str:
    lines = ["---"]
    if header:
        lines.append(f"# {header}")
    _emit(document, 0, lines)
    return "\n".join(lines) + "\n"


def compose_yaml(
    instance_name: str,
    image: str,
    fqdns: list[str] | None = None,
    router: str = "traefik",
) -> str:
    labels = traefik_labels(instance_name, fqdns or [], router)
    document = compose_document(instance_name, image, labels)
    return to_yaml(document, header=f"Docker compose file for instance {instance_name} ({image})")
