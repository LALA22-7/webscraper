from typing import List, Dict, Optional
from src.scrapers.base import BaseScraper
from src.scrapers.google_maps import GoogleMapsScraper
from src.scrapers.justdial import JustdialScraper

class SourceManager:
    """Manages the lifecycle and state of different scraping sources."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        
        # Available sources mapping
        self._available_sources: Dict[str, BaseScraper] = {
            "google_maps": GoogleMapsScraper(headless=self.headless),
            "justdial": JustdialScraper(headless=self.headless),
        }
        
        # Priority map: lower number is higher priority
        self.PRIORITIES = {
            "google_maps": 10,
            "justdial": 20,
            "sulekha": 30,
            "indiamart": 40,
            "tradeindia": 50,
            "duckduckgo": 100,
        }
        
        # Track enabled sources based on config
        self._enabled_sources: List[str] = []
        
        # Track health status for each source
        # Statuses: AVAILABLE, ACTIVE, EXHAUSTED, RATE_LIMITED, BLOCKED, FAILED
        self.source_health: Dict[str, str] = {
            name: "AVAILABLE" for name in self._available_sources
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
        scrapers = [
            self._available_sources[name] 
            for name in self._enabled_sources 
            if self.source_health.get(name) in ("AVAILABLE", "ACTIVE")
        ]
        return sorted(scrapers, key=lambda s: self.PRIORITIES.get(s.name.lower().replace(" ", "_"), 999))
        
    def update_health(self, source_name: str, status: str) -> None:
        """Update the health status of a source."""
        # E.g., if a CAPTCHA is hit, mark as BLOCKED so the orchestrator skips it
        # Map source.name (e.g. "Google Maps") back to key ("google_maps")
        for key, scraper in self._available_sources.items():
            if scraper.name == source_name:
                self.source_health[key] = status
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
