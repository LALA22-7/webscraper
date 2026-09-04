import uuid
import os
import asyncio
from datetime import datetime
from typing import Optional
from src.models.job import Job
from src.core.orchestrator import DiscoveryOrchestrator
from src.enrichment.website_crawler import WebsiteCrawler
from src.storage.postgres import PostgresManager
from src.storage.sheets_sync import GoogleSheetsSyncManager

import socket

async def check_connectivity(host="8.8.8.8", port=53, timeout=3):
    """Check if we have internet connectivity."""
    try:
        # Use a non-blocking connect via loop
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, socket.create_connection, (host, port), timeout)
        await asyncio.wait_for(future, timeout=timeout)
        return True
    except Exception:
        return False

class JobManager:
    """Manages the lifecycle of a scraping job including persistence and resumption."""
    
    def __init__(self, orchestrator: DiscoveryOrchestrator, website_crawler: WebsiteCrawler, db_dsn: str = "postgresql://user:password@localhost/leads_db"):
        self.orchestrator = orchestrator
        self.website_crawler = website_crawler
        self.db = PostgresManager(db_dsn)
        self.sheets_sync = GoogleSheetsSyncManager(spreadsheet_id="") # Configured via UI/Args
        
    async def _enrichment_worker(self, queue: asyncio.Queue, job: Job):
        while True:
            lead = await queue.get()
            if lead is None:
                queue.task_done()
                break
                
            try:
                # Website fallback discovery could go here if no website
                
                if lead.website:
                    await self.website_crawler.crawl_lead(lead)
                    job.total_websites_crawled += 1
                    
                lead.enriched_at = datetime.utcnow()
                await self.db.save_lead(lead, job.id)
                
                job.enriched_count += 1
                if lead.emails:
                    job.email_count += 1
                    
                if job.enriched_count % 5 == 0:
                    await self.db.save_job(job)
                    
                await self.sheets_sync.add_to_sync_queue(lead)
                    
            except Exception as e:
                job.errors.append(f"Enrichment error on {lead.business_name}: {e}")
            finally:
                queue.task_done()

    async def create_and_run_job(self, query: str, location: str, target: Optional[int] = None, duration_seconds: Optional[int] = None, sources: list[str] = None, require_email: bool = False) -> Job:
        job = Job(
            id=f"JOB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
            query=query,
            location=location,
            target=target,
            duration_seconds=duration_seconds,
            sources=sources or [],
            require_email=require_email
        )
        
        await self.db.connect()
        
        self.orchestrator.source_manager.configure_sources(job.sources)
        await self.db.save_job(job)
        
        queue = asyncio.Queue(maxsize=50) # backpressure
        
        # Start enrichment workers
        workers = [asyncio.create_task(self._enrichment_worker(queue, job)) for _ in range(15)]
        
        # Start checkpoint worker
        async def checkpoint_worker():
            while job.status in ("running", "paused", "internet_disconnected"):
                await asyncio.sleep(60)
                await self.db.save_job(job)
                
        # Start connectivity monitor
        async def connectivity_monitor():
            while job.status in ("running", "paused", "internet_disconnected"):
                is_connected = await check_connectivity()
                if not is_connected and job.status == "running":
                    print("[ConnectivityMonitor] Internet disconnected. Pausing job.")
                    job.status = "internet_disconnected"
                elif is_connected and job.status == "internet_disconnected":
                    print("[ConnectivityMonitor] Internet restored. Resuming job.")
                    job.status = "running"
                await asyncio.sleep(10)

        checkpoint_task = asyncio.create_task(checkpoint_worker())
        connectivity_task = asyncio.create_task(connectivity_monitor())
        
        # We pass a mutable status obj to the sheets sync so it knows when to shutdown
        status_obj = {"status": job.status}
        
        async def update_status_obj():
            while job.status in ("running", "paused", "internet_disconnected"):
                status_obj["status"] = job.status
                await asyncio.sleep(1)
                
        status_updater = asyncio.create_task(update_status_obj())
        sheets_task = asyncio.create_task(self.sheets_sync.start_sync_worker(job.id, status_obj))
        
        try:
            # Phase 1: Discovery pushes to queue
            await self.orchestrator.run_discovery(job, out_queue=queue, db=self.db)
            
            # Wait for all items in queue to be processed
            await queue.join()
            
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            
        except Exception as e:
            job.status = "failed"
            job.errors.append(str(e))
            
        finally:
            job.status = job.status if job.status in ["completed", "failed", "stopped"] else "completed"
            
            # Shutdown workers
            for _ in workers:
                await queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)
            checkpoint_task.cancel()
            connectivity_task.cancel()
            status_updater.cancel()
            
            # Shutdown sheets sync
            await self.sheets_sync.queue.put(None)
            await asyncio.gather(sheets_task, return_exceptions=True)
            
            await self.db.save_job(job)
            
            # Perform final deduplication cleanup on the database
            await self.db.deduplicate_leads(job.id)
            
            await self.db.disconnect()
            
        return job
