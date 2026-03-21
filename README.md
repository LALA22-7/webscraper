# 🗺️ Google Maps Lead Scraper

**A terminal-only CLI** that scrapes Google Maps for business leads (name, phone, URL) and exports them to CSV. No web app, no UI—just run it in your terminal.

---

## ✨ What it does

- **Search** by profession + location (e.g. *Gyms in Noida*) or a custom query
- **Verify** location & profession before scraping (with smart spelling hints, e.g. *noda* → *Noida*)
- **Choose** how many leads you want (50–1000)
- **Export** to CSV: `name`, `phone`, `url`

Runs entirely in the **command line**. No frontend.

---

## 📋 Prerequisites

- **Python 3.10+**
- **Chromium** (installed via Playwright in the setup step below)

---

## 🚀 Quick start

### 1. Clone or download the repo

```bash
git clone https://github.com/YOUR_USERNAME/google-maps-scraper.git
cd google-maps-scraper
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
```

**Activate it:**

| OS       | Command |
|----------|---------|
| Windows (PowerShell) | `.\.venv\Scripts\Activate.ps1` |
| Windows (CMD)        | `.\.venv\Scripts\activate.bat`  |
| macOS / Linux        | `source .venv/bin/activate`    |

### 3. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

> If `playwright` isn’t found, always use: `python -m playwright install chromium`

### 4. Run the scraper

```bash
python google_maps_scraper.py
```

You’ll be prompted for **profession**, **location**, **verification**, and **number of leads**. Output is saved as `{profession}_{location}.csv` in the current folder.

---

## 📖 Usage

### Interactive mode (recommended)

Prompts for profession, location, verification, and number of leads:

```bash
python google_maps_scraper.py
```

Example flow:

```
Enter profession (e.g. Gyms): Restaurants
Enter location (e.g. Noida): Greater Noida

  Profession: Restaurants
  Location:  Greater Noida
  We'll scrape data for: "Restaurants" in "Greater Noida".
Proceed? (y/n): y

How many leads do you want? (50-1000, default 50): 100
```

### CLI options (no prompts)

Run without interactive prompts by passing flags:

```bash
# By profession + location
python google_maps_scraper.py --profession "Gyms" --location "Noida" --max 200

# Custom full query
python google_maps_scraper.py --query "Dentists in Mumbai" --max 150

# Custom output file
python google_maps_scraper.py --profession Restaurants --location "Greater Noida" --max 100 --out my_leads.csv

# Headless (browser runs in background)
python google_maps_scraper.py --profession Gyms --location Delhi --max 50 --headless

# Skip verification step
python google_maps_scraper.py --profession Gyms --location Noida --no-verify --max 80
```

### Option reference

| Option         | Description |
|----------------|-------------|
| `--query`      | Full search string (e.g. `"Gyms in Noida"`). Overrides profession/location. |
| `--profession` | Category (e.g. Gyms, Restaurants, Dentists). |
| `--location`   | Place (e.g. Noida, Mumbai, Uttar Pradesh). |
| `--max`        | Number of leads to scrape (50–1000). If omitted, you’re prompted. |
| `--out`        | Output CSV path. Default: `{profession}_{location}.csv`; with `--query` only, `results.csv`. |
| `--headless`   | Run browser in background (no visible window). |
| `--no-verify`  | Skip the “Proceed? (y/n)” verification step. |

---

## 📊 Output

- **Format:** CSV  
- **Columns:** `name`, `phone`, `url`  
- **Default filename:** `{profession}_{location}.csv` (e.g. `restaurants_greater_noida.csv`)

---

## 📈 How many leads you get

Google Maps returns more results when the **search is broader**:

| Search scope | Typical lead count |
|--------------|--------------------|
| **State** (e.g. *Restaurants in Uttar Pradesh*)     | up to ~1000 |
| **District** (e.g. *Restaurants in Gautam Buddha Nagar*) | up to ~200  |
| **City** (e.g. *Restaurants in Greater Noida*)     | ~50–80      |

Use a **state or district** for more leads; use a **city** for a smaller, focused list.

---

## ⚠️ Notes

- **Consent / CAPTCHA:** Google may show a consent or “unusual traffic” page. Running in **headed** mode (default) and solving any CAPTCHA usually helps.
- **Debug:** If the script can’t find the search box, it may save `debug_maps.png` in the current folder.
- **Legal:** Use responsibly and comply with Google’s Terms of Service and local laws.

---

## 🌐 Web Frontend (NEW)

A modern, dark-themed web interface is now available for the scraper with enhanced features:

### Frontend Features
- **Modern Dark Theme UI** - Clean, professional interface with glass morphism effects
- **Real-time Progress Tracking** - Live progress bar with time estimation
- **Multiple Export Formats** - CSV, Excel, and PDF export options
- **Advanced Results Table** - Sortable, searchable, and paginated results
- **Responsive Design** - Works perfectly on desktop and mobile devices
- **Copy to Clipboard** - Quick copy functionality for phone numbers

### Web Usage

1. **Start the Web Application**
   ```bash
   python app.py
   ```

2. **Open in Browser**
   Navigate to `http://localhost:5000`

3. **Use the Web Interface**
   - Enter business type/profession (e.g., "Restaurants", "Gyms", "Salons")
   - Enter location (e.g., "New York", "Mumbai", "London")
   - Select number of leads to scrape
   - Click "Start Scraping"
   - Monitor real-time progress
   - Export results in your preferred format

### Web API Endpoints
- `POST /api/start_scraping` - Start a new scraping task
- `GET /api/scraping_status/<task_id>` - Get scraping progress and results
- `GET /api/export/<task_id>/<format>` - Export results (csv, excel, pdf)

### Web Requirements
The web frontend requires additional dependencies (already included in requirements.txt):
- Flask & Flask-CORS
- Pandas
- ReportLab (for PDF generation)
- openpyxl (for Excel export)

---

## 📁 Project structure

```
google-maps-scraper/
├── google_maps_scraper.py   # Main CLI script
├── app.py                   # Flask web application
├── requirements.txt         # Python dependencies
├── templates/
│   └── index.html          # Web frontend interface
├── README.md               # This file
└── .gitignore
```

Both CLI and web interfaces are available. Use the CLI for quick terminal operations, or the web interface for a more user-friendly experience with enhanced features.

---

## 📄 License

Use at your own risk. For educational purposes.

