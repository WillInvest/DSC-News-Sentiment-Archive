#!/usr/bin/env python3
"""Collect free, attributable Ethereum evidence for the sentiment MVP."""

import argparse
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = (
    ("Cointelegraph Ethereum", "https://cointelegraph.com/rss/tag/ethereum", 12),
    ("Ethereum Foundation", "https://blog.ethereum.org/feed.xml", 6),
)
TRUSTED_REDDIT = ("/r/ethereum/", "/r/ethfinance/", "/r/ethtrader/", "/r/cryptocurrency/")
COMMUNITY_LIMITS = {
    "youtube": 4,
    "stocktwits": 4,
    "hackernews": 3,
    "polymarket": 3,
    "github": 3,
}


def text(child: ET.Element) -> str:
    return (child.text or "").strip()


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def fetch_feed(source: str, url: str, maximum: int, cutoff: datetime) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "DSC-sentiment-MVP/1.0"})
    root = ET.fromstring(urllib.request.urlopen(request, timeout=25).read())
    records = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
            continue
        fields: dict[str, str] = {}
        link = ""
        for child in item:
            key = child.tag.rsplit("}", 1)[-1].lower()
            fields.setdefault(key, text(child))
            if key == "link" and child.attrib.get("href"):
                link = child.attrib["href"]
        title = fields.get("title", "")
        published = fields.get("pubdate") or fields.get("published") or fields.get("updated")
        date = parse_date(published)
        if not title or (date and date < cutoff):
            continue
        records.append({
            "source": source,
            "title": title,
            "url": link or fields.get("link", ""),
            "published_at": published,
            "summary": fields.get("description") or fields.get("summary") or fields.get("content", ""),
        })
        if len(records) >= maximum:
            break
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--community", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    status: dict[str, str] = {}
    results: list[dict] = []
    for source, url, maximum in FEEDS:
        key = source.lower().replace(" ", "_") + "_rss"
        try:
            rows = fetch_feed(source, url, maximum, cutoff)
            status[key] = "ok" if rows else "no-results"
            results.extend(rows)
        except Exception as error:
            status[key] = f"error: {type(error).__name__}"

    community = json.loads(Path(args.community).read_text())
    trusted_reddit = [
        item for item in community.get("results", [])
        if item.get("source") == "reddit"
        and any(part in (item.get("url") or "").lower() for part in TRUSTED_REDDIT)
    ][:5]
    results.extend(trusted_reddit)
    for source, maximum in COMMUNITY_LIMITS.items():
        results.extend([item for item in community.get("results", []) if item.get("source") == source][:maximum])
    status.update(community.get("source_status", {}))
    evidence = {
        "query": "Ethereum ETH blockchain",
        "window_days": 30,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source_status": status,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
