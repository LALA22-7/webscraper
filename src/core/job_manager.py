import uuid
import os
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
        
    async def create_and_run_job(self, query: str, location: str, target: int, sources: list[str]) -> Job:
        job = Job(
            id=f"JOB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
            query=query,
            location=location,
            target=target,
            sources=sources
        )
        
        self.orchestrator.source_manager.configure_sources(sources)
        self.db.save_job(job)
        
        try:
            # Phase 1: Discovery
            leads = await self.orchestrator.run_discovery(job)
            job.discovered_count = len(leads)
            self.db.save_job(job)
            
            # Save raw leads
            for lead in leads:
                self.db.save_lead(lead, job.id)
                
            # Phase 2: Enrichment
            for lead in leads:
                if lead.website:
                    await self.website_crawler.crawl_lead(lead)
                    lead.enriched_at = datetime.utcnow()
                    self.db.save_lead(lead, job.id)
                    job.enriched_count += 1
                    if lead.emails:
                        job.email_count += 1
                    # Periodically save job state
                    if job.enriched_count % 10 == 0:
                        self.db.save_job(job)
                        
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            
        except Exception as e:
            job.status = "failed"
            job.errors.append(str(e))
            
        finally:
            self.db.save_job(job)
            
        return job
