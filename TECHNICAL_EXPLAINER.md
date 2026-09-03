# Technical Explainer

This document outlines the architecture and technical design of the Multi-Source Business Scraper.

## System Architecture

The application is built around a centralized `DiscoveryOrchestrator` that manages a priority queue of different `BaseScraper` implementations. 

### 1. Discovery Phase
The orchestrator attempts to fulfill the user's `Target Count` by delegating the search query to a cascading list of sources:
- **Google Maps (`google_maps.py`)**: Primary source. Uses headless Playwright to perform scrolling, wait for UI elements, and bypass basic blocks. Yields high quality websites and phone numbers.
- **Justdial (`justdial.py`)**: Secondary source. Uses `httpx`. High volume of local Indian businesses.
- **IndiaMART (`indiamart.py`)**: Tertiary source. Uses Playwright. Good for B2B and wholesale suppliers. 
- **TradeIndia & Sulekha**: Fallback directories parsed via `BeautifulSoup`.
- **DuckDuckGo (`duckduckgo.py`)**: Final organic fallback. Uses Playwright to execute a `"query in location official website"` search, harvesting domains directly from search results.

**Resilience**: If any scraper throws a 403, 301, or Timeout, the Orchestrator catches the error, logs it, and immediately moves to the next source in the chain.

### 2. Enrichment Phase
As leads are discovered, they are deduplicated by `normalized_name` and `domain`. If a lead possesses a `website`, it is pushed to the `WebsiteEnricher`. 
- The Enricher uses a stealth HTTP client to fetch the homepage.
- It parses mailto links and regex-matches email patterns.
- Emails are graded with a `ConfidenceScore` (e.g., `HIGH` if it matches the domain, `LOW` if it's a generic `@gmail.com` address).

### 3. Storage & Export
- Leads, emails, and phone numbers are persisted to a normalized SQLite schema in `data/leads.db`. 
- Upon job completion, `SQLiteManager.export_csv()` uses SQL `LEFT JOIN` and `GROUP_CONCAT` to flatten the relational data into a single, user-friendly CSV file output to the `results/` directory.

### 4. Utilities
- **Autocorrect**: The `src/utils/autocorrect.py` module hooks into the Google Suggest API to silently fix typos in the user's location string. This prevents 0-yield runs on strict directory websites like TradeIndia that don't have internal spellcheckers.
