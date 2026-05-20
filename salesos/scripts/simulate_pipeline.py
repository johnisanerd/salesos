from __future__ import annotations

import argparse
import json

import asyncio
import time
from urllib import request


async def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate the SalesOS scrape pipeline with local fixtures.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--fixture", default="sample_leads", help="Fixture name under scripts/fixtures")
    parser.add_argument("--query", default="marketing agency")
    parser.add_argument("--location", default="Austin, TX")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--poll-timeout", type=int, default=180)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    payload = {
        "query": args.query,
        "location": args.location,
        "max_results": args.max_results,
        "fixture_name": args.fixture,
    }

    def send_request() -> dict:
        encoded = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{args.base_url.rstrip('/')}/api/leads/scrape",
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30.0) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_job(job_id: str) -> dict:
        with request.urlopen(f"{args.base_url.rstrip('/')}/api/leads/scrape/{job_id}", timeout=30.0) as response:
            return json.loads(response.read().decode("utf-8"))

    accepted = await asyncio.to_thread(send_request)
    deadline = time.monotonic() + args.poll_timeout
    result = accepted
    while time.monotonic() < deadline:
        result = await asyncio.to_thread(get_job, accepted["job_id"])
        if result["status"] in {"completed", "partial", "failed"}:
            break
        await asyncio.sleep(args.poll_interval)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
