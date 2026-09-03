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
        
    async def run_discovery(self, job: Job, out_queue: asyncio.Queue, db) -> List[Lead]:
        """
        Execute discovery across configured sources to find leads matching the job parameters.
        Pushes discovered leads to out_queue.
        """
        print(f"\n[Orchestrator] Starting discovery for '{job.query} in {job.location}' (Target: {job.target}, Require Email: {job.require_email})")
        
        await self.source_manager.initialize_all()
        active_scrapers = self.source_manager.get_enabled_scrapers()
        
        if not active_scrapers:
            print("[Orchestrator] No active scrapers available. Aborting.")
            return []
            
        from src.processing.query_expander import QueryExpander
        search_combinations = QueryExpander.generate_combinations(job.query, job.location)
        
        target = job.target * 2 if job.require_email else job.target
        
        for scraper in active_scrapers:
            for q, loc in search_combinations:
                if (job.require_email and job.email_count >= job.target) or (not job.require_email and len(self.deduplicator.leads) >= target):
                    print(f"[Orchestrator] Target reached. Stopping discovery.")
                    await self.source_manager.shutdown_all()
                    return list(self.deduplicator.leads.values())
                    
                print(f"\n[Orchestrator] Starting source: {scraper.name} with query: '{q} in {loc}'")
                
                consecutive_stalls = 0
                try:
                    remaining = target - len(self.deduplicator.leads)
                    
                    async for result in scraper.scrape(q, loc, remaining):
                        # Stalling detection
                        if consecutive_stalls > 20:
                            print(f"[Orchestrator] Source {scraper.name} stalled. Moving to next.")
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
                            print(f"  + Discovered: {new_lead.business_name} ({job.discovered_count}/{target})")
                            
                        if (job.require_email and job.email_count >= job.target) or (not job.require_email and len(self.deduplicator.leads) >= target):
                            break
                            
                    self.source_manager.update_health(scraper.name, "COMPLETED")
                    
                except Exception as e:
                    print(f"[Orchestrator] Source {scraper.name} failed: {e}")
                    self.source_manager.update_health(scraper.name, "FAILED")
                    job.errors.append(f"[{scraper.name}] {str(e)}")
                    break # break out of combinations for this scraper if it failed
                    
        await self.source_manager.shutdown_all()
        print(f"\n[Orchestrator] Discovery complete. Total unique leads: {len(self.deduplicator.leads)}")
        return list(self.deduplicator.leads.values())
