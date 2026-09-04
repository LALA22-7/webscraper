# Multi-Source Business Scraper & Enricher

A highly resilient, advanced multi-source Python CLI application designed to discover local business leads and automatically enrich them with vital contact information (emails, phone numbers, and websites).

Unlike simple scrapers that rely solely on a single directory and easily break upon encountering CAPTCHAs, this tool acts as a robust orchestrator. It aggregates leads across multiple search engines and directories, utilizing Playwright-driven headless browsers to gracefully bypass bot-blocks and simulate human interaction.

## ✨ Core Features

### 1. Multi-Source Discovery Engine
The scraper does not rely on a single point of failure. It automatically queries and cycles through a prioritized list of sources to maximize the data yield:
- **Google Maps**: The primary source for high-quality local business data (websites, phones, ratings).
- **Justdial**: An excellent secondary source for deep coverage of Indian local businesses.
- **IndiaMART**: Focused on B2B, wholesale suppliers, and manufacturers.
- **TradeIndia & Sulekha**: Fallback business directories to cast a wider net.
- **DuckDuckGo**: The ultimate organic fallback. It performs `"query in location official website"` searches to scrape domains directly from organic search engine results when directories are exhausted.

### 2. Block Resilience & Auto-Fallback
Web scraping is prone to IP blocks, HTTP 403 Forbidden errors, and CAPTCHA challenges. The **Orchestrator** is built to handle this gracefully. If a source times out or triggers a block, the application logs the error and seamlessly falls back to the next source in the chain, ensuring that your `Target Count` of leads is met without manual intervention.

### 3. Smart Query Expansion & Autocorrect
Powered by advanced query expansion and normalization (often integrating with suggestion APIs), the tool automatically corrects typos in location strings and expands the base query. This maximizes the yield from strict directories that might otherwise return zero results due to a simple spelling mistake.

### 4. Headless Browser Integration (Playwright)
Heavily guarded sources (like DuckDuckGo, Google Maps, and IndiaMART) cannot be scraped using simple HTTP requests. The application integrates a stealth headless Chromium browser via **Playwright**. This allows the scraper to execute JavaScript, scroll down pages to trigger lazy-loading, wait for specific UI elements, and bypass basic anti-bot challenges.

### 5. Deep Email Enrichment & Web Crawling
Discovering a business is only the first step. If a lead contains a website, the **Website Crawler** steps in:
- It asynchronously visits the homepage and common contact paths (`/contact`, `/about`).
- It extracts explicit `mailto:` links.
- It runs sophisticated Regex patterns over the page's plaintext to extract hidden emails.
- It grades the discovered emails (e.g., assigning a `HIGH` confidence score to `mailto:` links and discarding common false positives like `image@2x.png`).

### 6. Auto-Export & Robust SQLite Storage
All data is persisted in real-time to a normalized **SQLite database** (`data/leads.db`). This ensures no data is lost if the script is interrupted.
Once a job is completed, the tool automatically flattens the relational data and exports a clean, deduplicated **CSV file** to the `results/` folder.

---

## 🚀 Installation & Setup

This is a standalone Python package. It requires **Python 3.10+**.

1. **Clone the repository** and navigate to the project root:
   ```bash
   git clone <repository-url>
   cd "web scraper"
   ```

2. **Create and activate a virtual environment** (Recommended to isolate dependencies):
   ```bash
   # On macOS/Linux
   python -m venv .venv
   source .venv/bin/activate

   # On Windows
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browser binaries**:
   This downloads the necessary headless Chromium browser used for stealth scraping.
   ```bash
   playwright install chromium
   ```

---

## 💻 Usage

Start the interactive scraping wizard by running the CLI tool:

```bash
python scraper.py scrape
```

The interactive wizard will prompt you for the following parameters:
- **Business Type**: The category or niche (e.g., `plumbers`, `software companies`, `gyms`).
- **Location**: The city, state, or area (e.g., `Mumbai`, `New York`, `London`).
- **Target Count**: The exact number of *unique* leads you want to acquire. The scraper will stop once this goal is reached.
- **Email Requirement**: A strict filter. If set to `Yes`, the engine will discard any discovered lead that does not yield a valid email address after the enrichment phase.

### Exporting Past Jobs
Every scraping session is recorded as a "Job". You can re-export any past job to a CSV manually using its Job ID. This is useful if you want to extract the data again without re-scraping:

```bash
python scraper.py export <JOB_ID> --output custom_file.csv
```

---

## 📁 Project Structure

The codebase is modular and designed for extensibility:

```text
├── src/
│   ├── core/           # Orchestration logic (Orchestrator, JobManager, SourceManager)
│   ├── models/         # Data structures (Lead, Job, Email, SourceResult)
│   ├── scrapers/       # Individual scraper modules (google_maps.py, duckduckgo.py, etc.)
│   ├── enrichment/     # Deep crawling (website_crawler.py, email_extractor.py)
│   ├── processing/     # Data cleaning (Deduplicator, Normalizer, QueryExpander)
│   ├── storage/        # Database management (sqlite.py)
│   └── cli/            # Command-line interface definitions (Typer/Click)
├── data/               # Persistent SQLite database storage (leads.db)
├── results/            # Auto-generated CSV exports
├── scraper.py          # Main executable entry point
└── requirements.txt    # Python dependencies
```
