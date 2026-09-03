import asyncio
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from src.models.job import Job
from src.models.lead import Lead
from src.core.source_manager import SourceManager
from src.processing.deduplicator import Deduplicator

class DiscoveryOrchestrator:
    """Orchestrates the business lead discovery process across multiple sources."""
    
    def __init__(self, source_manager: SourceManager, deduplicator: Deduplicator):
        self.source_manager = source_manager
        self.deduplicator = deduplicator
        
    async def run_discovery(self, job: Job) -> List[Lead]:
        """
        Execute discovery across configured sources to find leads matching the job parameters.
        Returns the list of unique leads discovered.
        """
        print(f"\n[Orchestrator] Starting discovery for '{job.query} in {job.location}' (Target: {job.target})")
        
        await self.source_manager.initialize_all()
        active_scrapers = self.source_manager.get_enabled_scrapers()
        
        if not active_scrapers:
            print("[Orchestrator] No active scrapers available. Aborting.")
            return list(self.deduplicator.leads.values())
            
        # We run sources sequentially for simplicity and stability, 
        # but could run them concurrently using asyncio.gather if needed.
        # Given the requirements: "fallback strategy", it's better to run 
        # them one by one until the target is reached.
        
        for scraper in active_scrapers:
            if len(self.deduplicator.leads) >= job.target:
                print(f"[Orchestrator] Target of {job.target} reached. Stopping discovery.")
                break
                
            print(f"\n[Orchestrator] Starting source: {scraper.name}")
            try:
                # Calculate how many more we need
                remaining = job.target - len(self.deduplicator.leads)
                
                # Consume the async generator
                async for result in scraper.scrape(job.query, job.location, remaining):
                    # Check deduplication
                    existing_lead = self.deduplicator.find_match(result)
                    
                    if existing_lead:
                        # Merge new info into existing lead
                        self.deduplicator.merge_result(existing_lead, result)
                    else:
                        # Create new lead
                        new_lead = Lead(
                            id=str(uuid.uuid4()),
                            business_name=result.business_name,
                            normalized_name=result.business_name, # The normalizer should be applied here ideally
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
                        print(f"  + Discovered: {new_lead.business_name} ({job.discovered_count}/{job.target})")
                        
                    if len(self.deduplicator.leads) >= job.target:
                        break
                        
                self.source_manager.update_health(scraper.name, "COMPLETED")
                
            except Exception as e:
                print(f"[Orchestrator] Source {scraper.name} failed: {e}")
                self.source_manager.update_health(scraper.name, "FAILED")
                job.errors.append(f"[{scraper.name}] {str(e)}")
                
        await self.source_manager.shutdown_all()
        print(f"\n[Orchestrator] Discovery complete. Total unique leads: {len(self.deduplicator.leads)}")
        return list(self.deduplicator.leads.values())
