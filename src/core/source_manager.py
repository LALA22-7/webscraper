from typing import List, Dict, Optional
from datetime import datetime, timedelta
from src.scrapers.base import BaseScraper
from src.scrapers.organic_search import OrganicSearchScraper

class SourceManager:
    """Manages the lifecycle, health, and availability of the organic search scraper."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        
        # Available sources mapping
        self._available_sources: Dict[str, BaseScraper] = {
            "organic_search": OrganicSearchScraper(headless=self.headless),
        }
        
        self.PRIORITIES = {
            "organic_search": 10,
        }
        
        self._enabled_sources: List[str] = []
        
        self.source_health: Dict[str, str] = {
            name: "AVAILABLE" for name in self._available_sources
        }
        
        self.source_cooldowns: Dict[str, Optional[datetime]] = {
            name: None for name in self._available_sources
        }
        
    def configure_sources(self, requested_sources: Optional[List[str]] = None) -> None:
        """Enable specific sources, or all if none provided."""
        if not requested_sources:
            self._enabled_sources = list(self._available_sources.keys())
        else:
            self._enabled_sources = [
                s for s in requested_sources if s in self._available_sources
            ]
            
    def get_enabled_scrapers(self) -> List[BaseScraper]:
        """Return instances of enabled and healthy scrapers sorted by priority."""
        scrapers = []
        for name in self._enabled_sources:
            health = self.source_health.get(name)
            cooldown = self.source_cooldowns.get(name)
            
            if cooldown and datetime.utcnow() < cooldown:
                continue
                
            if health in ("AVAILABLE", "ACTIVE"):
                scrapers.append(self._available_sources[name])
                
        return sorted(scrapers, key=lambda s: self.PRIORITIES.get(s.name.lower().replace(" ", "_"), 999))
        
    def get_scraper(self, name: str) -> Optional[BaseScraper]:
        key = name.lower().replace(" ", "_")
        scraper = self._available_sources.get(key)
        if not scraper:
            return None
            
        cooldown = self.source_cooldowns.get(key)
        if cooldown and datetime.utcnow() < cooldown:
            return None
            
        return scraper
        
    def update_health(self, source_name: str, status: str, cooldown_minutes: int = 0) -> None:
        """Update the health status of a source."""
        for key, scraper in self._available_sources.items():
            if scraper.name == source_name:
                self.source_health[key] = status
                if cooldown_minutes > 0:
                    self.source_cooldowns[key] = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
                break
                
    async def initialize_all(self) -> None:
        """Initialize all enabled sources."""
        for name in self._enabled_sources:
            try:
                await self._available_sources[name].initialize()
                self.source_health[name] = "ACTIVE"
            except Exception as e:
                print(f"Failed to initialize source {name}: {e}")
                self.source_health[name] = "FAILED"
                
    async def shutdown_all(self) -> None:
        """Shutdown all sources gracefully."""
        for name in self._available_sources:
            try:
                await self._available_sources[name].shutdown()
            except Exception as e:
                print(f"Error shutting down {name}: {e}")
