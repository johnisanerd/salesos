from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from urllib.parse import urlparse
import urllib.error
import urllib.request
from collections.abc import Callable


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for SalesOS service dependencies to become reachable.")
    parser.add_argument(
        "--service",
        dest="services",
        action="append",
        choices=("postgres", "redis", "ollama", "api", "telegram-bot", "dashboard", "n8n"),
        help="Dependency to wait for. May be provided multiple times. Defaults to postgres, redis, and ollama.",
    )
    parser.add_argument("--timeout", type=float, default=_env_float("STARTUP_DEPENDENCY_TIMEOUT_SECONDS", 60.0))
    parser.add_argument("--interval", type=float, default=_env_float("STARTUP_DEPENDENCY_POLL_SECONDS", 2.0))
    args = parser.parse_args()

    services = args.services or ["postgres", "redis", "ollama"]
    checks = {name: _service_checks()[name] for name in services}
    deadline = time.monotonic() + args.timeout

    log(
        "info",
        "Waiting for services",
        services=services,
        timeout=args.timeout,
        interval=args.interval,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
    )

    while True:
        all_ready = True
        snapshot: dict[str, dict[str, str | bool]] = {}

        for name, check in checks.items():
            ok, detail = check()
            snapshot[name] = {"ok": ok, "detail": detail}
            if not ok:
                all_ready = False

        if all_ready:
            log("info", "All requested services are reachable", services=snapshot)
            return 0

        if time.monotonic() >= deadline:
            log("error", "Timed out waiting for services", services=snapshot)
            return 1

        log("warning", "Services still starting", services=snapshot)
        time.sleep(args.interval)


def _service_checks() -> dict[str, Callable[[], tuple[bool, str]]]:
    api_port = int(os.getenv("API_PORT", "8000"))
    bot_port = int(os.getenv("TELEGRAM_BOT_PORT", "8080"))
    dashboard_port = int(os.getenv("DASHBOARD_PORT", "3000"))

    return {
        "postgres": lambda: tcp_check(os.getenv("POSTGRES_HOST", "postgres"), int(os.getenv("POSTGRES_PORT", "5432")), "postgres"),
        "redis": lambda: tcp_check(_redis_host(), _redis_port(), "redis"),
        "ollama": lambda: http_check(
            os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434") + "/api/tags",
            "ollama",
        ),
        "api": lambda: http_check(f"http://api:{api_port}/api/ready", "api"),
        "telegram-bot": lambda: http_check(f"http://telegram-bot:{bot_port}/ready", "telegram-bot"),
        "dashboard": lambda: http_check(f"http://dashboard:{dashboard_port}", "dashboard"),
        "n8n": lambda: http_check("http://n8n:5678", "n8n"),
    }


def tcp_check(host: str, port: int, name: str) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True, f"{name} tcp reachable at {host}:{port}"
    except OSError as exc:
        return False, f"{name} tcp unavailable at {host}:{port}: {exc}"


def http_check(url: str, name: str) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "salesos-wait-for-services/1.0"})
    parsed = urlparse(url)
    resolved = _resolve_host(parsed.hostname)
    started_at = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=4.0) as response:
            status_code = getattr(response, "status", None)
            elapsed = time.monotonic() - started_at
            if status_code >= 400:
                return False, _http_detail(
                    name,
                    response=response,
                    url=url,
                    status_code=status_code,
                    elapsed=elapsed,
                    resolved=resolved,
                )
            return True, _http_detail(
                name,
                response=response,
                url=url,
                status_code=status_code,
                elapsed=elapsed,
                resolved=resolved,
            )
    except urllib.error.URLError as exc:
        return False, _http_detail(
            name,
            url=url,
            status=f"http unavailable: {exc}",
            elapsed=time.monotonic() - started_at,
            resolved=resolved,
        )


def _redis_host() -> str:
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        host_port = url.split("://", 1)[1].split("/", 1)[0]
        return host_port.split(":", 1)[0]
    except IndexError:
        return "redis"


def _redis_port() -> int:
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        host_port = url.split("://", 1)[1].split("/", 1)[0]
        if ":" in host_port:
            return int(host_port.split(":", 1)[1])
    except (IndexError, ValueError):
        pass
    return 6379


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _resolve_host(host: str | None) -> str:
    if not host:
        return "host missing from URL"
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, None)})
    except socket.gaierror as exc:
        return f"dns lookup failed for {host}: {exc}"
    return f"{host} -> {', '.join(addresses)}"


def _http_detail(
    name: str,
    *,
    url: str,
    resolved: str,
    status: str | None = None,
    response: object | None = None,
    status_code: int | None = None,
    elapsed: float | None = None,
) -> str:
    effective_status_code = status_code
    if effective_status_code is None and response is not None:
        effective_status_code = getattr(response, "status", None)

    if status is None:
        if effective_status_code is None:
            status = "http status unknown"
        elif effective_status_code >= 400:
            status = f"http unhealthy: status {effective_status_code}"
        else:
            status = f"http reachable: status {effective_status_code}"

    elapsed_suffix = ""
    if elapsed is not None:
        elapsed_suffix = f"; elapsed={elapsed:.3f}s"

    return f"{name} {status} at {url} ({resolved}{elapsed_suffix})"


def log(level: str, message: str, **fields: object) -> None:
    payload = {"level": level, "message": message, **fields}
    print(json.dumps(payload), file=sys.stderr if level == "error" else sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
