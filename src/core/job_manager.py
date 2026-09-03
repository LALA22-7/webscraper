import uuid
import os
import asyncio
from datetime import datetime
from src.models.job import Job
from src.core.orchestrator import DiscoveryOrchestrator
from src.enrichment.website_crawler import WebsiteCrawler
from src.storage.sqlite import SQLiteManager

class JobManager:
    """Manages the lifecycle of a scraping job including persistence and resumption."""
    
    def __init__(self, orchestrator: DiscoveryOrchestrator, website_crawler: WebsiteCrawler, db_path: str = "leads.db"):
        self.orchestrator = orchestrator
        self.website_crawler = website_crawler
        self.db = SQLiteManager(db_path)
        
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
                self.db.save_lead(lead, job.id)
                
                job.enriched_count += 1
                if lead.emails:
                    job.email_count += 1
                    
                if job.enriched_count % 5 == 0:
                    self.db.save_job(job)
                    
            except Exception as e:
                job.errors.append(f"Enrichment error on {lead.business_name}: {e}")
            finally:
                queue.task_done()

    async def create_and_run_job(self, query: str, location: str, target: int, sources: list[str], require_email: bool = False) -> Job:
        job = Job(
            id=f"JOB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
            query=query,
            location=location,
            target=target,
            sources=sources,
            require_email=require_email
        )
        
        self.orchestrator.source_manager.configure_sources(sources)
        self.db.save_job(job)
        
        queue = asyncio.Queue(maxsize=50) # backpressure
        
        # Start enrichment workers
        workers = [asyncio.create_task(self._enrichment_worker(queue, job)) for _ in range(15)]
        
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
            # Shutdown workers
            for _ in workers:
                await queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)
            self.db.save_job(job)
            
        return job
