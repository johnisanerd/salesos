from __future__ import annotations

import argparse
import json


def build_lead(index: int, *, query: str, location: str) -> dict:
    return {
        "title": f"{query.title()} Test Lead {index}",
        "phone": f"+1 (555) 010-{1000 + index}",
        "website": f"{query.replace(' ', '-')}-{index}.local",
        "city": location,
        "state": "Local",
        "country": "USA",
        "category": query,
        "place_id": f"generated-{index}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake Google Maps scrape results for SalesOS testing.")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--query", default="marketing agency")
    parser.add_argument("--location", default="Austin, TX")
    args = parser.parse_args()

    leads = [build_lead(index + 1, query=args.query, location=args.location) for index in range(args.count)]
    print(json.dumps(leads, indent=2))


if __name__ == "__main__":
    main()
