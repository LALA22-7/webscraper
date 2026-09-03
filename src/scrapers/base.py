from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from src.models.source_result import SourceResult

class BaseScraper(ABC):
    """Abstract base class for all source scrapers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the source, e.g., 'Google Maps'"""
        pass
        
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize any required resources (e.g., browser contexts)."""
        pass
        
    @abstractmethod
    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        """
        Execute search and yield results continuously until target is reached 
        or source is exhausted/blocked.
        """
        pass
        
    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass
