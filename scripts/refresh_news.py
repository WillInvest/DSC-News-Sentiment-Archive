#!/usr/bin/env python3
"""Generate the static News MVP feed from a small, public RSS whitelist."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

SOURCES = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Blockworks": "https://blockworks.com/feed/",
    "Decrypt": "https://decrypt.co/feed",
}
ARCHIVE_URL = "https://github.com/WillInvest/DSC-News-Sentiment-Archive/tree/main/news/archive"
USER_AGENT = "DSC-News-Sentiment-Archive/1.0"
DEFI_WORDS = ("defi", "dex", "swap", "lending", "liquidity", "stablecoin", "uniswap", "aave", "compound", "yield", "vault", "amm")
BLOCKCHAIN_WORDS = ("ethereum", "blockchain", "network", "layer 2", "l2", "validator", "protocol", "on-chain", "onchain", "security", "hack", "exploit", "regulation", "sec", "bitcoin")


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    source: str
    publishedAt: str
    url: str
    excerpt: str
    tags: list[str]
    category: str


def clean_text(value: str | None, limit: int = 260) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rsplit(" ", 1)[0] + "…" if len(text) > limit else text


def canonical_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, val) for key, val in query if not key.lower().startswith(("utm_", "mc_"))]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), urllib.parse.urlencode(query), ""))


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None


def text_of(element: ET.Element, *names: str) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text
    return ""


def entries(xml: bytes, source: str) -> list[tuple[str, str, datetime, str]]:
    root = ET.fromstring(xml)
    result: list[tuple[str, str, datetime, str]] = []
    for entry in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = clean_text(text_of(entry, "title", "{http://www.w3.org/2005/Atom}title"), 180)
        link = text_of(entry, "link")
        if not link:
            atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
            link = atom_link.get("href", "") if atom_link is not None else ""
        date = parse_date(text_of(entry, "pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"))
        excerpt = clean_text(text_of(entry, "description", "summary", "{http://www.w3.org/2005/Atom}summary", "{http://purl.org/rss/1.0/modules/content/}encoded"))
        if title and link and date:
            result.append((title, canonical_url(link), date, excerpt))
    return result


def classify(title: str, excerpt: str) -> tuple[str, list[str]] | None:
    content = f"{title} {excerpt}".lower()
    defi_hits = [word for word in DEFI_WORDS if word in content]
    chain_hits = [word for word in BLOCKCHAIN_WORDS if word in content]
    if defi_hits:
        tags = ["DeFi"]
        if any(word in content for word in ("stablecoin", "usdc", "usdt", "dai")):
            tags.append("Stablecoins")
        elif any(word in content for word in ("lending", "aave", "compound", "yield")):
            tags.append("Lending")
        else:
            tags.append("Markets")
        return "defi", tags
    if chain_hits:
        tags = ["Blockchain"]
        if any(word in content for word in ("security", "hack", "exploit")):
            tags.append("Security")
        elif any(word in content for word in ("regulation", "sec")):
            tags.append("Policy")
        else:
            tags.append("Infrastructure")
        return "blockchain", tags
    return None


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "news" / "latest.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--archive-output", type=Path, help="Write this run's selected stories to a dated archive file.")
    args = parser.parse_args()
    cutoff = datetime.now(UTC) - timedelta(days=30)
    seen: set[str] = set()
    buckets: dict[str, list[Item]] = {"blockchain": [], "defi": []}
    failures: list[str] = []
    for source, url in SOURCES.items():
        try:
            for title, link, date, excerpt in entries(fetch(url), source):
                if date < cutoff:
                    continue
                normalized_title = re.sub(r"[^a-z0-9]", "", title.lower())
                identity = f"{link}|{normalized_title}"
                if identity in seen:
                    continue
                category = classify(title, excerpt)
                if not category:
                    continue
                section, tags = category
                digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
                buckets[section].append(Item(digest, title, source, date.isoformat().replace("+00:00", "Z"), link, excerpt, tags, section))
                seen.add(identity)
        except Exception as exc:  # A failed publisher must not erase yesterday's digest.
            print(f"warning: {source}: {exc}", file=sys.stderr)
            failures.append(source)
    for section in buckets:
        buckets[section].sort(key=lambda item: item.publishedAt, reverse=True)
        buckets[section] = buckets[section][:5]
    if not any(buckets.values()):
        raise RuntimeError("no eligible news items fetched; preserving prior news.json")
    daily_sections = {key: [{k: v for k, v in asdict(item).items() if k != "category"} for item in values] for key, values in buckets.items()}
    previous_sections: dict[str, list[dict[str, object]]] = {"blockchain": [], "defi": []}
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
            for section in previous_sections:
                if isinstance(previous.get("sections", {}).get(section), list):
                    previous_sections[section] = previous["sections"][section]
        except (OSError, ValueError, TypeError):
            pass
    recent_sections: dict[str, list[dict[str, object]]] = {}
    for section in previous_sections:
        merged: dict[str, dict[str, object]] = {}
        for item in daily_sections[section] + previous_sections[section]:
            published = parse_date(str(item.get("publishedAt", "")))
            identifier = str(item.get("id") or item.get("url") or item.get("title"))
            if published and published >= cutoff and identifier:
                merged[identifier] = item
        recent_sections[section] = sorted(merged.values(), key=lambda item: str(item.get("publishedAt", "")), reverse=True)
    payload = {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "archiveUrl": ARCHIVE_URL,
        "disclosure": "Automated daily digest based on linked public sources. Headlines and excerpts belong to their original publishers.",
        "sections": recent_sections,
    }
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.dry_run:
        print(encoded)
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(args.output)
    if args.archive_output:
        args.archive_output.parent.mkdir(parents=True, exist_ok=True)
        archive_payload = {**payload, "sections": daily_sections}
        args.archive_output.write_text(json.dumps(archive_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(buckets['blockchain'])} blockchain, {len(buckets['defi'])} new; {len(recent_sections['blockchain'])} blockchain, {len(recent_sections['defi'])} defi stored; failed sources: {', '.join(failures) or 'none'})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
