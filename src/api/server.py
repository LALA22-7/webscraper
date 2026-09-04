"""
Lead Discovery Engine V4.2 — Production API Server

Key features:
- MULTI-TENANT: Run multiple jobs in parallel (e.g. from multiple tabs)
- HIGH CONCURRENCY: Set CRAWL_CONCURRENCY for extreme scale
- Continuous job loop: keeps discovering leads until deadline OR total target is hit
- 4-layer email validation (format/disposable/DNS MX/SMTP) on every email found
- Real-time Google Sheets sync (set GOOGLE_SHEET_ID + credentials.json)
- Proxy pool rotation for website crawling (set PROXY_LIST env var)
- SerpAPI for search (set SERPAPI_KEY env var)

Env vars:
  SERPAPI_KEY        required  - SerpAPI key for Google search
  CRAWL_CONCURRENCY  optional  - Crawl workers per job (default: 50)
  GOOGLE_SHEET_ID    optional  - Google Sheet ID to sync leads into
  GOOGLE_CREDS_PATH  optional  - Path to credentials.json (default: credentials.json)
  PROXY_LIST         optional  - Comma-separated proxy URLs for crawling
  PROXY_URL          optional  - Single proxy URL (fallback if PROXY_LIST not set)
"""

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import os
import httpx
import random
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, Dict, List

from src.models.job import Job
from src.models.lead import Lead
from src.enrichment.website_crawler import WebsiteCrawler
from src.processing.email_validator import EmailValidator
from src.storage.sheets_sync import GoogleSheetsSyncManager

app = FastAPI(title="Lead Discovery Engine V4.2")
app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

# ── Global state (Multi-Tenant) ──────────────────────────────────────────────
JOBS: Dict[str, Job] = {}
TASKS: Dict[str, asyncio.Task] = {}
LEADS: Dict[str, List[dict]] = {}  # job_id -> [{business_name, website, emails}]

# Query variations to keep generating fresh searches when first batch is done
QUERY_MODIFIERS = [
    "", "contact", "official website", "email", "phone",
    "head office", "headquarters", "location", "address",
    "near me", "best", "top", "local", "independent",
]


# ── HTML serving ─────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("src/api/static/index.html", "r") as f:
        return f.read()


# ── Status endpoint ──────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status(job_id: Optional[str] = None):
    if not job_id or job_id not in JOBS:
        return {"status": "STOPPED", "message": "No active job selected"}
    
    active_job = JOBS[job_id]

    if active_job.status in ("completed", "stopped") and active_job.finished_at:
        elapsed = (active_job.finished_at - active_job.started_at).total_seconds()
    else:
        elapsed = (datetime.utcnow() - active_job.started_at).total_seconds() if active_job.started_at else 0

    return {
        "job_id":          active_job.id,
        "query":           active_job.query,
        "location":        active_job.location,
        "status":          active_job.status,
        "discovered":      active_job.discovered_count,
        "enriched":        active_job.enriched_count,
        "emails":          active_job.email_count,
        "runtime_seconds": elapsed,
    }


# ── Results endpoint ─────────────────────────────────────────────────────────
@app.get("/api/results")
async def get_results(job_id: Optional[str] = None):
    if not job_id or job_id not in LEADS:
        return {"total": 0, "leads": []}
    
    collected_leads = LEADS[job_id]
    return {"total": len(collected_leads), "leads": collected_leads}


# ── SerpAPI search ───────────────────────────────────────────────────────────
async def search_serpapi(query: str, location: str, limit: int, start: int = 0) -> list:
    """
    Fetch up to `limit` unique business URLs from Google via SerpAPI.
    `start` controls the result offset (for pagination in the continuous loop).
    """
    api_key = os.getenv("SERPAPI_KEY", "")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY not set.")

    BLACKLIST = {"google", "facebook", "instagram", "youtube", "wikipedia",
                 "justdial", "sulekha", "indiamart", "twitter", "linkedin",
                 "bing", "microsoft", "booking", "expedia", "tripadvisor",
                 "hotels", "trivago", "makemytrip", "goibibo", "agoda",
                 "airbnb", "vrbo", "kayak", "priceline", "orbitz",
                 "yelp", "yellowpages", "trustpilot", "glassdoor", "wyndham",
                 "marriott", "hilton", "accor", "ihg", "hyatt"}

    found = []
    found_domains = set()

    async with httpx.AsyncClient(timeout=30) as client:
        page_start = start
        while len(found) < limit:
            try:
                # Adding small jitter to prevent 429 Too Many Requests under extreme concurrency
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
                resp = await client.get(
                    "https://serpapi.com/search.json",
                    params={"q": f"{query} {location}", "api_key": api_key,
                            "num": 10, "start": page_start, "engine": "google"}
                )
                data = resp.json()
                organic = data.get("organic_results", [])
                if not organic:
                    break

                for result in organic:
                    link = result.get("link", "")
                    title = result.get("title", "")
                    if not link:
                        continue
                    try:
                        parsed = urlparse(link)
                        domain = parsed.netloc.replace("www.", "")
                        parts = domain.split(".")
                        base = parts[-2].lower() if len(parts) >= 2 else parts[0].lower()
                    except Exception:
                        continue
                    if not domain or base in BLACKLIST or any(b in domain for b in BLACKLIST):
                        continue
                    if domain not in found_domains:
                        found_domains.add(domain)
                        found.append({"url": f"https://{parsed.netloc}/", "title": title})
                    if len(found) >= limit:
                        break

                page_start += 10
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"[Search] SerpAPI failed at start={page_start}: {e}")
                break

    return found[:limit]


# ── Core job runner ──────────────────────────────────────────────────────────
async def run_job(job_id: str, query: str, location: str, target: int, duration_seconds: int,
                  sheet_id: str, creds_path: str):
    
    active_job = JOBS[job_id]
    collected_leads = LEADS[job_id]
    
    discovered_domains: set = {}
    total_emails_found = 0
    deadline = datetime.utcnow().timestamp() + duration_seconds if duration_seconds else None

    def time_left() -> bool:
        return deadline is None or datetime.utcnow().timestamp() < deadline

    def hits_target() -> bool:
        return target and total_emails_found >= target

    # Start Sheets sync worker in parallel (each job gets its own queue if multi-tenant writing to same sheet)
    sheets = GoogleSheetsSyncManager(
        spreadsheet_id=sheet_id,
        credentials_path=creds_path or "credentials.json"
    )
    sheets_worker = asyncio.create_task(sheets.start_sync_worker(active_job.id))

    validator = EmailValidator()
    
    # Extreme Concurrency setting for Dedicated Server
    crawl_concurrency = int(os.getenv("CRAWL_CONCURRENCY", "50"))
    crawler = WebsiteCrawler(max_pages_per_domain=5, concurrency=crawl_concurrency)

    print(f"[Job {job_id}] Starting: '{query}' in '{location}' | target={target} | duration={duration_seconds}s | concurrency={crawl_concurrency}")

    # ── CONTINUOUS LOOP ──────────────────────────────────────────────────────
    modifier_index = 0
    search_offset = 0

    try:
        while time_left() and not hits_target() and active_job.status == "running":

            # Build next query variant to avoid duplicate results
            modifier = QUERY_MODIFIERS[modifier_index % len(QUERY_MODIFIERS)]
            search_q = f"{query} {modifier}".strip() if modifier else query
            modifier_index += 1

            print(f"[Job {job_id}] Searching: '{search_q}' in '{location}' (offset={search_offset})")

            # Phase 1: Discover URLs
            try:
                results = await search_serpapi(search_q, location, limit=10, start=search_offset)
                search_offset += 10
            except Exception as e:
                print(f"[Job {job_id}] Search error: {e}")
                await asyncio.sleep(5)
                continue

            new_results = [r for r in results if r["url"] not in discovered_domains]
            if not new_results:
                print(f"[Job {job_id}] No new URLs in this batch, rotating query modifier.")
                await asyncio.sleep(2)
                continue

            for r in new_results:
                discovered_domains[r["url"]] = True
                active_job.discovered_count += 1

            print(f"[Job {job_id}] {len(new_results)} new URLs to crawl")

            # Phase 2: Crawl + validate emails
            for r in new_results:
                if not time_left() or hits_target() or active_job.status != "running":
                    break

                url = r["url"]
                name = r.get("title", "") or urlparse(url).netloc.replace("www.", "").split(".")[0].title()

                lead = Lead(
                    id=f"lead-{active_job.enriched_count}",
                    business_name=name,
                    normalized_name=name.lower(),
                    website=url
                )

                try:
                    await crawler.crawl_lead(lead)
                except Exception as e:
                    print(f"[Crawl {job_id}] Error on {url}: {e}")
                    continue

                active_job.enriched_count += 1

                if not lead.emails:
                    continue

                # Phase 3: Validate each email
                raw_emails = list(lead.emails.keys())
                validation_results = await validator.validate_batch(raw_emails, concurrency=5)

                lead_entry = {
                    "business_name": lead.business_name,
                    "website": url,
                    "emails": []
                }

                for vr in validation_results:
                    if vr.status in ("valid", "risky"):
                        total_emails_found += 1
                        active_job.email_count += 1

                        email_entry = {
                            "email": vr.email,
                            "status": vr.status,
                            "score": vr.score,
                            "role_based": vr.is_role_based,
                        }
                        lead_entry["emails"].append(email_entry)

                        # Push to Google Sheets immediately (non-blocking)
                        await sheets.add_lead(
                            business_name=lead.business_name,
                            website=url,
                            email=vr.email,
                            email_status=vr.status,
                            score=vr.score,
                            is_role_based=vr.is_role_based,
                            query=query,
                            location=location,
                            job_id=active_job.id,
                        )
                        print(f"  [Job {job_id} Email] {vr.email} → {vr.status} (score={vr.score})")

                if lead_entry["emails"]:
                    collected_leads.append(lead_entry)

            # Small pause between search batches to be polite
            if time_left() and not hits_target():
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        print(f"[Job {job_id}] Cancelled.")
    except Exception as e:
        print(f"[Job {job_id}] Error: {e}")
        active_job.status = f"error: {str(e)}"
        active_job.finished_at = datetime.utcnow()
    finally:
        await sheets.stop()
        try:
            await asyncio.wait_for(sheets_worker, timeout=15)
        except asyncio.TimeoutError:
            sheets_worker.cancel()

    if active_job.status == "running":
        active_job.status = "completed"
    active_job.finished_at = datetime.utcnow()
    print(f"[Job {job_id}] Done. discovered={active_job.discovered_count} "
          f"enriched={active_job.enriched_count} emails={active_job.email_count}")


# ── Start / Stop endpoints ───────────────────────────────────────────────────
@app.post("/api/start")
async def start_job(query: str, location: str,
                    duration_seconds: int = 60, target: int = 50):
    
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    creds_path = os.getenv("GOOGLE_CREDS_PATH", "credentials.json")

    job_id = f"JOB-{datetime.utcnow().strftime('%H%M%S%f')}"
    
    active_job = Job(
        id=job_id,
        query=query, location=location,
        target=target, duration_seconds=duration_seconds,
        sources=["organic_search"]
    )
    active_job.status = "running"
    active_job.started_at = datetime.utcnow()
    
    JOBS[job_id] = active_job
    LEADS[job_id] = []

    active_task = asyncio.create_task(
        run_job(job_id, query, location, target, duration_seconds, sheet_id, creds_path)
    )
    TASKS[job_id] = active_task

    # Hard deadline auto-stop
    async def auto_stop(j_id):
        await asyncio.sleep(duration_seconds)
        job = JOBS.get(j_id)
        if job and job.status == "running":
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            task = TASKS.get(j_id)
            if task and not task.done():
                task.cancel()
            print(f"[Auto-stop] {duration_seconds}s deadline reached for {j_id}.")

    asyncio.create_task(auto_stop(job_id))

    return {"message": "Job started", "job_id": job_id, "query": query, "location": location,
            "duration_seconds": duration_seconds, "target": target,
            "sheets": bool(sheet_id)}


@app.post("/api/stop")
async def stop_job(job_id: str):
    if not job_id or job_id not in JOBS:
        return {"error": "Invalid or missing job_id"}
        
    task = TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
        
    job = JOBS[job_id]
    if job.status == "running":
        job.status = "stopped"
        job.finished_at = datetime.utcnow()
        
    return {"message": f"Job {job_id} stopped",
            "discovered": job.discovered_count,
            "enriched": job.enriched_count,
            "emails": job.email_count}
