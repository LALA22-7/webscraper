# Production-Grade Multi-Source Business Lead Discovery & Email Enrichment Platform

## Overview

A professional, asynchronous, and modular CLI application that orchestrates the discovery and enrichment of business leads across multiple sources (Google Maps, Justdial). It implements feature-based entity resolution for deduplication, an async crawler for email extraction from business domains, and a robust checkpointing system backed by SQLite.

## Architecture

```
User
  |
  v
CLI (Typer/Rich)
  |
  v
Job Manager (SQLite checkpointing)
  |
  v
Discovery Orchestrator
  |
  +---- Google Maps (Playwright)
  +---- Justdial (Playwright)
  |
  v
Normalization & Deduplication
  |
  v
Website Crawler & Email Extractor
  |
  v
Lead Database (SQLite)
```

## Features

- **Multi-source discovery**: Google Maps, Justdial.
- **Auto-scroll/pagination**: Asynchronous dynamic scrolling with Playwright.
- **Deduplication**: Feature-based entity resolution across sources (Phone, Domain, Name).
- **Website enrichment**: Async crawling of discovered domains using `httpx`.
- **Email extraction**: Regex-based email extraction with false-positive filtering and provenance tracking.
- **Checkpoint/resume**: SQLite-backed continuous persistence (prevents data loss).
- **CLI**: Rich, beautiful CLI progress tracking via Typer.
- **Source fallback**: Graceful degradation if a source is blocked.

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/web-scraper.git
cd web-scraper
python -m venv .venv
# Activate venv
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

```bash
python scraper.py scrape --query "gyms" --location "Noida" --target 300
```

Email-qualified leads:
```bash
python scraper.py scrape --query "real estate companies" --location "Greater Noida" --target 300 --require-email
```

Select specific sources:
```bash
python scraper.py scrape --query "dentists" --location "Mumbai" --target 100 --sources google_maps
```

## Development

To add a new source adapter:
1. Create `src/scrapers/my_source.py`.
2. Implement the `BaseScraper` interface.
3. Register the scraper in `src/core/source_manager.py`.

## Output

Data is continuously saved to `leads.db` (SQLite).
Export commands to CSV/JSON are planned for future iterations.
