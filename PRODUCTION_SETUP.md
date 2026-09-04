# Enterprise Production Setup Guide — V4.2

This guide details how to deploy the Lead Discovery Engine V4.2 on a dedicated Virtual Private Server (VPS) utilizing high-concurrency parallel jobs and a rotating residential proxy network.

## 1. Hardware Requirements
For optimal performance running extreme concurrency (30,000+ leads in 2 hours), we recommend:
- **CPU:** 16+ Cores
- **RAM:** 32GB+
- **OS:** Ubuntu 22.04 LTS (or equivalent Linux distribution)

## 2. Server Provisioning & Dependencies
Connect to your VPS via SSH and install the required system dependencies:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git screen curl
```

## 3. Application Setup

Clone the repository and set up the Python environment:
```bash
git clone <your-repo-url>
cd web-scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. Configuration (Environment Variables)

The engine requires configuration to connect to your Proxy Provider, SerpAPI, and Google Sheets.
Create a `.env` file or export these variables in your shell:

```bash
# SerpAPI for Search
export SERPAPI_KEY="your_serpapi_key"

# Concurrency Tuning (EXTREME SCALE)
# Default is 50. For a 16-core machine, you can push this to 100 or 150.
export CRAWL_CONCURRENCY="100"

# Proxy Network Configuration (Rotating Pool)
# Comma-separated list of proxies for Website Crawling
export PROXY_LIST="http://user:pass@proxy1:port,http://user:pass@proxy2:port"
```

### Google Sheets Integration Setup
To stream data directly to a Google Sheet so your entire office can access it:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project.
2. Enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** and generate a new JSON key. Download it.
4. Rename that downloaded file to `credentials.json` and upload it to the root folder of this project on your server.
5. Create a new Google Sheet and share it with the email address of the service account you just created (e.g., `scraper@your-project.iam.gserviceaccount.com`).
6. Copy the **Spreadsheet ID** from the URL of your Google Sheet.
7. Set the Environment Variables:
```bash
export GOOGLE_SHEET_ID="your_spreadsheet_id"
export GOOGLE_CREDS_PATH="credentials.json"
```

## 5. Running the Engine

To keep the FastAPI server running continuously in the background, you can use `screen` or a process manager like `pm2`.

Using `screen`:
```bash
screen -S scraper
source venv/bin/activate
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```
*(Press `Ctrl+A` then `D` to detach and leave it running).*

## 6. Multi-Tenant Parallel Usage

The V4.2 engine supports **Multi-Tenancy**. This means:
1. You can open `http://<YOUR_VPS_IP_ADDRESS>:8000/` in **multiple browser tabs**.
2. Tab 1 can search for "hotels in switzerland".
3. Tab 2 can search for "dental clinics in london".
4. Both jobs will run **completely in parallel** on the backend.
5. The frontend will keep track of which tab is running which job (even if you refresh the page).

## 7. Troubleshooting

### SerpAPI Rate Limits / Missing Results
**Symptom:** Search stops finding new URLs.
**Cause:** SerpAPI plans have rate limits (e.g., 5-20 searches per second). If you run too many concurrent tabs, you may get 429 Too Many Requests.
**Fix:** The backend has built-in random jitter to mitigate this, but if it persists, you may need a higher tier SerpAPI plan.

### Proxy Blocking (403/429)
**Symptom:** Crawler fails to extract data from many sites.
**Fix:** Ensure your `PROXY_LIST` contains rotating residential or high-quality datacenter proxies. The crawler automatically cools down any proxy that returns a 403 or 429 for 60 seconds before retrying it.

### Google Sheets Quotas
**Symptom:** Leads stop appearing in Google Sheets but show in the UI.
**Fix:** Google Sheets API has a write quota of 300 requests per minute per project. The engine uses batched writes (20 rows at a time) to avoid this. If you run 10 parallel jobs hitting the same sheet, you might hit the quota. Monitor your Google Cloud Console quota usage.
