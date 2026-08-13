#!/usr/bin/env python3
"""Write the small public pointer used by DSC clients."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> None:
    news = read(ROOT / "news/latest.json")
    sentiment = read(ROOT / "sentiment/watchlist/latest.json")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "news": {
            "path": "news/latest.json",
            "generated_at": news.get("generatedAt"),
            "archive_path": "news/archive/",
        },
        "sentiment": {
            "path": "sentiment/watchlist/latest.json",
            "generated_at": sentiment.get("generated_at") or sentiment.get("generatedAt"),
            "evidence_path": "evidence/watchlist/",
        },
        "disclosure": "Public-source archive. Sentiment is an evidence-grounded research summary, not financial advice.",
    }
    (ROOT / "latest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
