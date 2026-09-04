# Multi-Source Business Scraper & Enricher

A highly resilient, multi-source Python CLI application that discovers local business leads and enriches them with contact information (emails, phones, websites).

Unlike simple scrapers that rely on a single directory, this tool aggregates leads across multiple engines and uses Playwright headless browsers to gracefully bypass bot-blocks and CAPTCHAs.

## Features
- **Multi-Source Discovery Engine**: Automatically cycles through Google Maps, Justdial, IndiaMART, TradeIndia, Sulekha, and DuckDuckGo.
- **Block Resilience**: If one source times out or triggers a CAPTCHA, the orchestrator seamlessly falls back to the next source to ensure your target lead count is met.
- **Smart Autocorrect**: Powered by the Google Suggest API, it automatically corrects typos in location strings to maximize yield from strict directories.
- **Headless Playwright Integration**: Heavily guarded sources (like DuckDuckGo and IndiaMART) are parsed via a stealth headless Chromium browser.
- **Deep Email Enrichment**: Crawls discovered websites to extract and validate emails, checking main pages and `mailto:` links.
- **Auto-Export & SQLite Storage**: Automatically exports jobs into a clean, flat CSV in the `results/` folder, while maintaining a robust normalized SQLite database in `data/leads.db`.

## Installation

This is a Python package (not a Chrome Extension). It requires Python 3.10+.

1. Clone the repository and navigate to the root directory.
2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```
4. Install Playwright browser binaries:
```bash
playwright install chromium
```

## Usage

Start the interactive scraping wizard:
```bash
python scraper.py scrape
```

The wizard will prompt you for:
- **Business Type**: The category (e.g., `electricians`, `gyms`).
- **Location**: The city or area (e.g., `Mumbai`, `New York`).
- **Target Count**: The number of unique leads you want.
- **Email Requirement**: Whether the engine should discard leads that don't yield an email address.

### Exporting Past Jobs
You can export any past job to a CSV manually using its Job ID:
```bash
python scraper.py export <JOB_ID> --output custom_file.csv
```

## Project Structure
- `src/core/`: Core orchestration logic (`orchestrator.py`, `job_manager.py`, `source_manager.py`).
- `src/models/`: Data models for Jobs, Leads, Emails, and Source Results.
- `src/scrapers/`: Individual scraping implementations (Google Maps, DuckDuckGo, etc.).
- `src/enrichment/`: Website crawling (`website_crawler.py`) and email extraction logic (`email_extractor.py`).
- `src/processing/`: Normalization (phone numbers, domains), deduplication, and query expansion.
- `src/storage/`: SQLite database management (`sqlite.py`).
- `src/cli/`: Typer-based command-line interface.
- `src/utils/`: Helpers like the Google Suggest autocorrect module.
- `results/`: Output directory for generated CSV files.
- `data/`: Storage location for the `leads.db` SQLite database.
