# DSC News & Sentiment Archive

This is the public, durable archive for the DeFi Statistics Center (DSC) news feed and market-sentiment research. It combines the former news and sentiment archives in one place. No private infrastructure, credentials, backend addresses, or user data are stored here.

## What is in this repository

| Location | Purpose |
| --- | --- |
| `latest.json` | Small public index pointing a DSC client to the newest news and sentiment records. |
| `news/latest.json` | The web-facing rolling news feed: relevant stories from the previous 30 days. |
| `news/archive/YYYY/MM/DD.json` | A permanent daily snapshot of stories selected that day. |
| `sentiment/watchlist/latest.json` | Latest research summaries for the tracked chains and protocols. |
| `sentiment/watchlist/*.json` | Per-entity latest sentiment records. |
| `sentiment/history/` | Earlier dated sentiment snapshots retained from the original archive. |
| `evidence/watchlist/YYYY-MM-DD/` | The public evidence package used for that day's sentiment run, including source status and linked items. |
| `config/watchlist.json` | The current transparent list of entities, aliases, and public communities to research. |
| `scripts/` | Reproducible collectors and evidence-to-summary tools. |

The initial watchlist covers Bitcoin, Ethereum, Solana, Base, Arbitrum, Optimism, BNB Chain, Avalanche, Uniswap, Aave, Lido, Maker/Sky, Compound, Curve, Morpho, EigenLayer, Pendle, and Ethena.

## Current data sources

### News feed

The daily news collector reads these public RSS feeds:

- CoinDesk
- Cointelegraph
- Blockworks
- Decrypt

It normalizes links, removes duplicates and tracking parameters, keeps stories published in the last 30 days, and classifies relevant items into **DeFi** or **Blockchain**. `news/latest.json` keeps the rolling 30-day feed for the DSC website; the daily selection is also preserved forever under `news/archive/`.

### Sentiment evidence

The sentiment collector uses only freely accessible public material. Depending on availability for an entity, it queries:

- CoinDesk and Cointelegraph RSS
- Ethereum Foundation blog posts
- public Reddit communities
- public YouTube metadata/transcripts where available
- Hacker News, Polymarket, and GitHub
- the keyless public-web retrieval routes provided by the pinned `last30days` collector

The collector records a source's status. A source that is unavailable or returns no relevant material is treated as missing evidence, **not** as positive or negative sentiment.

The current MVP deliberately does **not** collect X/Twitter, Discord, Telegram, Farcaster, private/cookie-gated sources, paid APIs, or user data.

## Daily mechanism

GitHub Actions runs this repository's `Daily DSC news and sentiment archive` workflow every day at approximately **06:15 America/New_York** (with a manual-run option for recovery/testing). GitHub provides a temporary Linux runner; DSC's AWS frontend and protected data backend do not execute this research job.

Each daily run:

1. Fetches the RSS whitelist and writes the latest 30-day feed plus that day's permanent news archive.
2. Collects fresh public evidence for every entity in `config/watchlist.json` with the pinned `last30days` tool and the direct RSS sources.
3. Saves the evidence package for auditability under `evidence/watchlist/<date>/`.
4. Uses the configured Cursor model in an isolated workspace to make an evidence-grounded summary. It may use flexible labels; every judgement must link its reasons to collected evidence, and it must say when evidence is insufficient.
5. Updates the latest sentiment records and `latest.json`, then commits the generated public archive back to this repository.

The supplied `CURSOR_API_KEY` is a GitHub Actions secret. It is never committed to the repository or sent to the DSC frontend/backend.

## Interpretation and limits

Sentiment files are research summaries, not trading signals or financial advice. They describe the evidence collected at a point in time; they do not establish truth, completeness, causation, or a market forecast. Follow the links in each record and use the saved daily evidence to check any conclusion.

Today's implementation produces one daily Cursor-based research pass. Future versions may add independent model views and rolling weekly, monthly, quarterly, yearly, and all-history reports. Those should be stored as separate, clearly labeled analyses of the same archived evidence rather than silently overwriting a prior conclusion.

## Website use

The DSC frontend should read `latest.json`, then the paths it names. The site can show `news/latest.json` as the last 30 days and link users here for the permanent archive. This avoids running expensive collection jobs on the web server while keeping the published records inspectable.

## Legacy archives

This repository is the canonical archive going forward. The previous `DSC-News-Archive` and `DSC-Sentiment-Archive` repositories remain historical references; their existing records were copied here during migration.
