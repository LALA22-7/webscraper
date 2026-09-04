# Technical Explainer

This document provides an in-depth breakdown of the architecture, design patterns, and technical workflows powering the Multi-Source Business Scraper. It is intended for developers looking to understand, maintain, or extend the codebase.

---

## 🏗 System Architecture Overview

The application utilizes a modular, event-driven architecture centered around a `DiscoveryOrchestrator`. Instead of monolithic scraping scripts, the logic is decoupled into distinct phases: **Discovery**, **Processing/Deduplication**, **Enrichment**, and **Storage**. 

The `Orchestrator` manages a priority queue of various `BaseScraper` implementations, delegating tasks and handling fallbacks seamlessly.

---

## 🔍 1. Discovery Phase (The Scrapers)

The orchestrator attempts to fulfill the user's requested `Target Count` by delegating the search query to a cascading list of sources via the `SourceManager`.

### Scraper Implementations
All scrapers inherit from a common `BaseScraper` interface, ensuring a unified input (query, location) and output (a stream of `Lead` objects).
- **Google Maps (`google_maps.py`)**: The primary and most reliable source. It utilizes headless Playwright to navigate to Google Maps, perform infinite scrolling to load results, wait for dynamic DOM elements to render, and extract highly accurate data including websites, phone numbers, and ratings. It acts as a human user to bypass basic blocks.
- **Justdial (`justdial.py`)**: A secondary source highly effective for local Indian businesses. It uses lightweight `httpx` requests for fast HTML retrieval.
- **IndiaMART (`indiamart.py`)**: A tertiary source focused on B2B. Because IndiaMART uses heavy bot-protection, this scraper also utilizes Playwright to render the page fully before extracting supplier details.
- **TradeIndia & Sulekha**: Fallback directories that are parsed using `BeautifulSoup4` over standard HTTP requests.
- **DuckDuckGo (`duckduckgo.py`)**: The ultimate organic fallback. It uses Playwright to execute a targeted search (`"query in location official website"`) and harvests domains directly from organic search engine result pages (SERPs).

### Resilience & Query Expansion
- **QueryExpander**: Located in `src/processing/`, this module dynamically generates variations of the base search query and location. If a directory fails to find "software companies", it might try "IT services" or "software development".
- **Auto-Fallback**: If any scraper throws an exception (HTTP 403 Forbidden, 301 Redirect loop, Timeout, or CAPTCHA interception), the Orchestrator catches it, logs a warning, and immediately moves to the next available source in the chain.
- **Stalling Detection**: The Orchestrator monitors the yield. If a scraper returns 20 consecutive duplicate leads (indicating that it has reached the end of its pagination or is stuck in a loop), the Orchestrator assumes the source is exhausted and skips to the next one.

---

## 🧹 2. Processing & Deduplication

Because we aggregate data from multiple sources, overlapping leads are inevitable (e.g., a plumber listed on both Google Maps and Justdial). 

As leads are discovered, they are passed through the `Deduplicator` module which holds an in-memory registry of the current job's findings.
- **Normalization**: The `normalizer.py` module cleans the data. It strips out whitespace, standardizes company names (e.g., "Acme Corp LLC" -> "acme corp"), standardizes phone numbers (stripping country codes and formatting), and normalizes URLs to base domains.
- **Matching Logic**: Deduplication groups leads based on matching `normalized_name`, matching `phone` numbers, or matching `domain`.
- **Merging**: When a duplicate is detected, the lead is not simply discarded. The data is merged. If Google Maps provided the phone number and DuckDuckGo provided the website, the resulting Lead object will contain both. `source_names` and `source_urls` are appended together to maintain a breadcrumb trail of where the data was found.

---

## 🌐 3. Enrichment Phase (Crawling & Extraction)

If a discovered lead possesses a `website` URL, it enters the Enrichment phase, managed by the `WebsiteCrawler` and `EmailExtractor`.

- **Asynchronous Crawling**: The `WebsiteCrawler` uses an asynchronous `httpx` client to fetch the homepage. To maximize the chances of finding an email, it also automatically navigates to common contact paths (e.g., `/contact`, `/about-us`, `/contact-us`).
- **Extraction Techniques**:
  1. **Mailto Parsing**: It looks for explicit HTML `<a href="mailto:...">` tags. These are highly accurate.
  2. **Regex Scanning**: It extracts all plain text from the webpage and runs sophisticated Regular Expressions to identify email patterns hidden in paragraphs or footers.
- **Confidence Scoring & Validation**: The `EmailExtractor` validates the findings to filter out false positives (like `example@example.com`, `info@wix.com`, or emails ending in `.png`/`.jpg`). 
  - Emails found via `mailto:` are graded with a `ConfidenceScore.HIGH`.
  - Emails found via plaintext regex are graded with `ConfidenceScore.MEDIUM`.
- **Domain Caching**: An internal cache prevents the crawler from hitting the same domain twice in a single run, optimizing performance and reducing unnecessary network overhead.

---

## 💾 4. Data Models & Storage (SQLite)

To ensure data consistency, the application uses strict data models located in `src/models/`. These models (e.g., `Lead`, `Job`, `Email`, `SourceResult`) define the exact schema and types expected throughout the pipeline.

- **Relational Persistence**: Instead of just holding data in memory, the app persists data to a normalized SQLite schema managed by `src/storage/sqlite.py`.
- **Tables**: The schema consists of `Jobs` (tracking the run), `Leads` (the business entities), `Emails` (linked to leads via foreign keys), and `Phones` (linked to leads).
- **Upserts**: The `SQLiteManager` uses `INSERT OR REPLACE` (or equivalent upsert logic) to seamlessly update existing leads in the database without throwing constraint errors. This means you can run the scraper multiple times over the same area and it will incrementally update your database.

---

## 📤 5. Export Pipeline

The final step of the lifecycle is delivering the data to the user.
- Upon job completion (or when triggered manually via the `export` CLI command), the `SQLiteManager.export_csv()` method is invoked.
- **Flattening Relational Data**: It uses complex SQL queries featuring `LEFT JOIN` and `GROUP_CONCAT`. This takes the relational structure (one lead to many emails/phones) and flattens it into a single row per lead (e.g., `emails: a@example.com, b@example.com`).
- **CSV Generation**: The flattened data is dumped into a user-friendly `.csv` file saved to the `results/` directory, ready to be imported into Excel, CRMs, or cold-email software.
