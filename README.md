# Lead Discovery Engine V4 (Enterprise Edition)

An autonomous, highly concurrent lead discovery and enrichment pipeline designed for enterprise-scale web scraping.

## 🚀 Key Features

* **Organic Search Engine**: Uses headless Playwright browsers to query search engines dynamically, discovering business domains without relying on fragile directory platforms.
* **Infinite Query Generation**: Automatically expands base queries (e.g., "restaurants") with modifiers ("best", "top") and alphabet suffixing (a-z) to dig extremely deep into long-tail search results.
* **Resilient Architecture**: Built with automated cooldowns for IP bans, internet connectivity monitoring, and automatic pause/resume state management.
* **Proxy Network Integration**: Fully supports rotating residential proxy networks (via HTTPX and Playwright) to eliminate rate limits and IP blocking.
* **High-Concurrency PostgreSQL Storage**: Replaced SQLite with an `asyncpg` connection pool, allowing 100+ concurrent crawler tasks to save and deduplicate leads without database locking.
* **Real-time Google Sheets Sync**: Streams discovered and enriched leads directly to Google Sheets as the job runs.
* **Web Dashboard**: Includes a FastAPI and HTML-based dashboard to configure targets, durations, and monitor live metrics.

## 📦 Setup & Deployment

For full deployment instructions on a dedicated Virtual Private Server (VPS), see [PRODUCTION_SETUP.md](PRODUCTION_SETUP.md).

### Quick Local Startup
1. Clone the repository and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

2. Set up your `.env` file with PostgreSQL and Proxy configurations:
```bash
DB_DSN="postgresql://user:password@localhost/leads_db"
PROXY_URL="http://your.proxy.provider.com:port"
PROXY_USER="username"
PROXY_PASS="password"
```

3. Launch the Web Dashboard:
```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

## 🧠 Architecture Flow
1. **Dashboard:** User starts a job with a target count.
2. **Query Scheduler:** Generates 1,000+ query combinations and adds them to a queue.
3. **Orchestrator:** Spins up 20+ parallel headless browsers (routed through proxies) to search DuckDuckGo/Google for business URLs.
4. **Website Crawler:** Spins up 100+ parallel HTTPX clients to crawl the discovered websites, extracting the actual `<title>`, `<meta name="description">`, and scanning for `mailto:` links.
5. **PostgresManager:** Saves the leads, handles deduplication, and streams the finished records to Google Sheets.

## 🛡 Testing
Run the mock tests to verify the resilience of the network and cooldown handlers:
```bash
python -m pytest tests/test_resilience.py -v
```
