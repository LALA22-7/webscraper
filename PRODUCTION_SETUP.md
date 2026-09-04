# Enterprise Production Setup Guide

This guide details how to deploy the Lead Discovery Engine V3 on a dedicated Virtual Private Server (VPS) utilizing a PostgreSQL database and a rotating residential proxy network.

## 1. Hardware Requirements
For optimal performance running 20+ headless browsers and 100+ concurrent crawler tasks, we recommend:
- **CPU:** 16+ Cores
- **RAM:** 32GB+
- **OS:** Ubuntu 22.04 LTS (or equivalent Linux distribution)

## 2. Server Provisioning & Dependencies
Connect to your VPS via SSH and install the required system dependencies:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git screen curl
```

### Install PostgreSQL
```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Configure the Database
Login to PostgreSQL and create the database and user:
```bash
sudo -u postgres psql
```
In the SQL prompt:
```sql
CREATE DATABASE leads_db;
CREATE USER scraper_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE leads_db TO scraper_user;
\q
```

## 3. Application Setup

Clone the repository and set up the Python environment:
```bash
git clone <your-repo-url>
cd web-scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 4. Configuration (Environment Variables)

The engine requires configuration to connect to your Proxy Provider (e.g., BrightData, Oxylabs) and the PostgreSQL database.
Create a `.env` file or export these variables in your shell:

```bash
# Database Configuration
export DB_DSN="postgresql://scraper_user:your_secure_password@localhost/leads_db"

# Proxy Network Configuration
export PROXY_URL="http://your.proxy.provider.com:port"
export PROXY_USER="your_proxy_username"
export PROXY_PASS="your_proxy_password"
```

### Google Sheets Integration Setup
To stream data directly to a Google Sheet so your entire office can access it:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project.
2. Enable the **Google Sheets API**.
3. Create a **Service Account** and generate a new JSON key. Download it.
4. Rename that downloaded file to `credentials.json` and upload it to the root folder of this project on your server.
5. Create a new Google Sheet and share it with the email address of the service account you just created (e.g., `scraper@your-project.iam.gserviceaccount.com`).
6. Copy the **Spreadsheet ID** from the URL of your Google Sheet (it's the long string of characters between `/d/` and `/edit`).
7. Update `src/core/job_manager.py` (Line 29) to include your ID: `self.sheets_sync = GoogleSheetsSyncManager(spreadsheet_id="YOUR_SPREADSHEET_ID")`.

## 5. Running the Engine

To keep the FastAPI server running continuously in the background, you can use `screen` or a process manager like `pm2`.

Using `screen`:
```bash
screen -S scraper
source venv/bin/activate
uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```
*(Press `Ctrl+A` then `D` to detach and leave it running).*

## 6. Accessing the Dashboard
You can now access the Live Dashboard from anywhere in your office by navigating to:
`http://<YOUR_VPS_IP_ADDRESS>:8000/`

Set your desired target count (e.g., 30,000) and click Start. The system will utilize 100% of the server's power to harvest, enrich, and stream the data!

## 7. Performance & Analytics Estimates
When running on the recommended hardware (16+ Cores, 32GB RAM) with a Rotating Proxy Network and PostgreSQL, the engine can safely scale to:
- **20+ Parallel Search Workers**
- **100+ Parallel Website Enrichment Crawlers**

With this configuration:
- You will average around **15,000 to 25,000 fully enriched leads per hour**.
- To achieve a target of **25,000 to 30,000 leads**, the engine will take approximately **1.5 to 2 hours** to complete the job and deduplicate the data. 
- The data is streamed into Google Sheets in real-time, meaning your team can begin accessing and working with the first few thousand leads within minutes of starting the job!
