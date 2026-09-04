import asyncio
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from src.models.job import Job
from src.models.lead import Lead
from src.core.source_manager import SourceManager
from src.processing.deduplicator import Deduplicator
from src.core.query_scheduler import QueryScheduler
from src.processing.query_expander import QueryExpander

class DiscoveryOrchestrator:
    """Orchestrates the business lead discovery process across multiple sources using asynchronous workers."""
    
    def __init__(self, source_manager: SourceManager, deduplicator: Deduplicator):
        self.source_manager = source_manager
        self.deduplicator = deduplicator
        self.scheduler = QueryScheduler(QueryExpander)
        
    async def _search_worker(self, worker_id: int, job: Job, out_queue: asyncio.Queue, db, target: int):
        print(f"[Worker-{worker_id}] Started.")
        while job.status == "running":
            
            # Check stop conditions
            if job.duration_seconds and job.started_at:
                if (datetime.utcnow() - job.started_at).total_seconds() > job.duration_seconds:
                    break
            if job.target:
                if (job.require_email and job.email_count >= job.target) or (not job.require_email and len(self.deduplicator.leads) >= target):
                    break

            next_query = await self.scheduler.get_next()
            if not next_query:
                await asyncio.sleep(1) # Wait for more queries or stop if exhausted
                continue
                
            source_name, q, loc = next_query
            scraper = self.source_manager.get_scraper(source_name)
            
            if not scraper:
                self.scheduler.mark_failed(source_name, q, loc)
                continue
                
            print(f"[Worker-{worker_id}] Executing: '{q}' in '{loc}' on {source_name}")
            
            consecutive_stalls = 0
            try:
                remaining = (target - len(self.deduplicator.leads)) if target else 999999
                
                async for result in scraper.scrape(q, loc, remaining):
                    if consecutive_stalls > 20:
                        print(f"[Worker-{worker_id}] Source {source_name} stalled. Stopping query.")
                        break
                        
                    existing_lead = self.deduplicator.find_match(result)
                    
                    if existing_lead:
                        self.deduplicator.merge_result(existing_lead, result)
                        consecutive_stalls += 1
                    else:
                        consecutive_stalls = 0
                        new_lead = Lead(
                            id=str(uuid.uuid4()),
                            business_name=result.business_name,
                            normalized_name=result.business_name,
                            category=result.category,
                            address=result.address,
                            locality=result.locality,
                            city=result.city,
                            phone_numbers=[result.phone] if result.phone else [],
                            website=result.website,
                            rating=result.rating,
                            review_count=result.review_count,
                            latitude=result.latitude,
                            longitude=result.longitude,
                            source_names=[result.source_name],
                            source_urls=[result.source_url],
                            source_ids=[result.source_id] if result.source_id else []
                        )
                        self.deduplicator.add_lead(new_lead)
                        job.discovered_count = len(self.deduplicator.leads)
                        
                        db.save_lead(new_lead, job.id)
                        await out_queue.put(new_lead)
                        print(f"  + [Worker-{worker_id}] Discovered: {new_lead.business_name}")
                        
                    # Stop checks during scraping loop
                    if job.duration_seconds and job.started_at:
                        if (datetime.utcnow() - job.started_at).total_seconds() > job.duration_seconds:
                            break
                    if job.target:
                        if (job.require_email and job.email_count >= job.target) or (not job.require_email and len(self.deduplicator.leads) >= target):
                            break

                self.source_manager.update_health(source_name, "COMPLETED")
                self.scheduler.mark_completed(source_name, q, loc)
                
            except Exception as e:
                print(f"[Worker-{worker_id}] Source {source_name} failed: {e}")
                self.source_manager.update_health(source_name, "FAILED", cooldown_minutes=5)
                job.errors.append(f"[{source_name}] {str(e)}")
                self.scheduler.mark_failed(source_name, q, loc)
                
        print(f"[Worker-{worker_id}] Stopped.")

    async def run_discovery(self, job: Job, out_queue: asyncio.Queue, db, num_workers: int = 3) -> List[Lead]:
        """
        Execute discovery across configured sources using concurrent workers.
        """
        print(f"\n[Orchestrator] Starting continuous discovery for '{job.query} in {job.location}'")
        
        await self.source_manager.initialize_all()
        active_scrapers = self.source_manager.get_enabled_scrapers()
        
        if not active_scrapers:
            print("[Orchestrator] No active scrapers available. Aborting.")
            return []
            
        target = job.target * 2 if job.require_email and job.target else (job.target or 0)
        
        # Seed the scheduler
        active_source_names = [s.name for s in active_scrapers]
        await self.scheduler.initialize(job.query, job.location, active_source_names)
        
        # Start search workers
        workers = []
        for i in range(num_workers):
            task = asyncio.create_task(self._search_worker(i, job, out_queue, db, target))
            workers.append(task)
            
        # Wait for all workers to complete (they will complete when duration/target is hit, or queue is empty and stalls)
        await asyncio.gather(*workers, return_exceptions=True)
                    
        await self.source_manager.shutdown_all()
        print(f"\n[Orchestrator] Discovery complete. Total unique leads: {len(self.deduplicator.leads)}")
        return list(self.deduplicator.leads.values())
