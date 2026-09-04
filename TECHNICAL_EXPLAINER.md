# Technical Explainer

This document outlines the architecture and technical design of the Multi-Source Business Scraper.

## System Architecture

The application is built around a centralized `DiscoveryOrchestrator` that manages a priority queue of different `BaseScraper` implementations.

### 1. Discovery Phase
The orchestrator attempts to fulfill the user's `Target Count` by delegating the search query to a cascading list of sources via `SourceManager`:
- **Google Maps (`google_maps.py`)**: Primary source. Uses headless Playwright to perform scrolling, wait for UI elements, and bypass basic blocks. Yields high quality websites and phone numbers.
- **Justdial (`justdial.py`)**: Secondary source. Uses `httpx`. High volume of local Indian businesses.
- **IndiaMART (`indiamart.py`)**: Tertiary source. Uses Playwright. Good for B2B and wholesale suppliers. 
- **TradeIndia & Sulekha**: Fallback directories parsed via `BeautifulSoup`.
- **DuckDuckGo (`duckduckgo.py`)**: Final organic fallback. Uses Playwright to execute a `"query in location official website"` search, harvesting domains directly from search results.

**Resilience & Query Expansion**: 
- `QueryExpander` dynamically generates variations of the search query and location.
- If any scraper throws a 403, 301, or Timeout, the Orchestrator catches the error, logs it, and moves to the next source in the chain. 
- The Orchestrator also features stalling detection: if a scraper yields 20 consecutive duplicates, it assumes the source is exhausted and skips to the next one.

### 2. Processing & Deduplication
As leads are discovered, they are deduplicated in memory using the `Deduplicator` module. Deduplication is based on normalization logic from `normalizer.py`, grouping by `normalized_name`, phone numbers, or domain. When duplicates are found, data is merged (e.g., combining `source_names` and `source_urls`).

### 3. Enrichment Phase
If a lead possesses a `website`, it is processed by the `WebsiteCrawler` in the enrichment phase.
- The `WebsiteCrawler` uses an asynchronous `httpx` client to fetch the homepage and common contact paths (`/contact`, `/about`).
- It parses `mailto:` links and extracts emails from the text using regex via the `EmailExtractor`.
- Emails are validated to remove common false positives (like `example@example.com` or image files) and graded with a `ConfidenceScore` (`HIGH` for `mailto`, `MEDIUM` for plaintext regex matches).
- A domain cache prevents redundant crawling of the same website across multiple leads.

### 4. Data Models & Storage
The application utilizes typed data models located in `src/models/` (`Lead`, `Job`, `Email`, `SourceResult`) to ensure data consistency.
- Leads, emails, and phone numbers are persisted to a normalized SQLite schema (Jobs, Leads, Emails, Phones tables) managed by `src/storage/sqlite.py`.
- `SQLiteManager.save_job()` and `SQLiteManager.save_lead()` handle inserting or replacing records seamlessly.

### 5. Export
Upon job completion, or when triggered manually via the CLI, `SQLiteManager.export_csv()` uses SQL `LEFT JOIN` and `GROUP_CONCAT` to flatten the relational data (aggregating multiple emails and phones) into a single, user-friendly CSV file output to the `results/` directory.
