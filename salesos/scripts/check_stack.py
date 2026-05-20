from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request


def main() -> int:
    checks = [
        tcp_result("postgres", _host_alias(os.getenv("POSTGRES_HOST", "postgres")), int(os.getenv("POSTGRES_PORT", "5432"))),
        tcp_result("redis", _redis_host(), _redis_port()),
        http_result("ollama", _ollama_base_url() + "/api/tags"),
        http_result("api_live", _host_url("http://localhost:8000") + "/api/live"),
        http_result("api_ready", _host_url("http://localhost:8000") + "/api/ready"),
        http_result("api_health", _host_url("http://localhost:8000") + "/api/health"),
        http_result("telegram_live", f"http://localhost:{os.getenv('TELEGRAM_BOT_PORT', '8080')}/live"),
        http_result("telegram_ready", f"http://localhost:{os.getenv('TELEGRAM_BOT_PORT', '8080')}/ready"),
        http_result("telegram_health", f"http://localhost:{os.getenv('TELEGRAM_BOT_PORT', '8080')}/health"),
        http_result("dashboard", f"http://localhost:{os.getenv('DASHBOARD_PORT', '3000')}"),
        http_result("n8n", "http://localhost:5678"),
    ]

    ok = all(item["ok"] for item in checks if item["required"])
    print(json.dumps({"stack_ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


def tcp_result(name: str, host: str, port: int, *, required: bool = True) -> dict[str, object]:
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return {"name": name, "ok": True, "required": required, "detail": f"tcp reachable at {host}:{port}"}
    except OSError as exc:
        return {"name": name, "ok": False, "required": required, "detail": f"tcp unavailable at {host}:{port}: {exc}"}


def http_result(name: str, url: str, *, required: bool = True) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": "salesos-check-stack/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=4.0) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = getattr(response, "status", 200)
            return {
                "name": name,
                "ok": status_code < 400,
                "required": required,
                "detail": f"http status {status_code}",
                "body_preview": body[:240],
            }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"name": name, "ok": False, "required": required, "detail": f"http unavailable at {url}: {exc}"}


def _redis_host() -> str:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        host_port = url.split("://", 1)[1].split("/", 1)[0]
        return _host_alias(host_port.split(":", 1)[0])
    except IndexError:
        return "localhost"


def _redis_port() -> int:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        host_port = url.split("://", 1)[1].split("/", 1)[0]
        if ":" in host_port:
            return int(host_port.split(":", 1)[1])
    except (IndexError, ValueError):
        pass
    return 6379


def _host_url(default: str) -> str:
    base_url = os.getenv("HOST_API_BASE_URL")
    if base_url:
        return base_url.rstrip("/")
    return default.rstrip("/")


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/").replace(
        "://host.docker.internal:",
        "://localhost:",
    ).replace("://ollama:", "://localhost:")


def _host_alias(host: str) -> str:
    if host in {"postgres", "redis", "api", "telegram-bot", "dashboard", "n8n"}:
        return "localhost"
    return host


if __name__ == "__main__":
    raise SystemExit(main())
