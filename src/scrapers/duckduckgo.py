import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import AsyncGenerator
from urllib.parse import urlparse

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class DuckDuckGoScraper(BaseScraper):
    """Fallback search discovery engine using DuckDuckGo HTML version."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.client = None
        
    @property
    def name(self) -> str:
        return "Search Discovery"
        
    async def initialize(self) -> None:
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            timeout=15.0
        )
        
    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        if not self.client:
            await self.initialize()
            
        yielded_count = 0
        
        # e.g., "gyms in Noida official website"
        search_query = f"{query} in {location} official website"
        
        try:
            resp = await self.client.post(
                "https://html.duckduckgo.com/html/", 
                data={"q": search_query}
            )
            
            if resp.status_code != 200:
                raise RuntimeError(f"DuckDuckGo blocked or failed with {resp.status_code}")
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            results = soup.find_all("a", class_="result__url")
            
            for result in results:
                if yielded_count >= target:
                    break
                    
                href = result.get("href")
                if not href or "duckduckgo.com" in href:
                    continue
                    
                if href.startswith("//"):
                    href = "https:" + href
                    
                # We assume the domain name could be the business name candidate
                domain = urlparse(href).netloc.replace("www.", "")
                
                # Filter out obvious directories
                if any(x in domain for x in ["justdial", "sulekha", "indiamart", "google", "facebook", "instagram"]):
                    continue
                    
                yield SourceResult(
                    source_name=self.name,
                    source_url=href,
                    business_name=domain.split('.')[0].title(),
                    website=href,
                    city=location
                )
                yielded_count += 1
                
        except Exception as e:
            raise RuntimeError(f"Search Discovery failed: {e}")
            
    async def shutdown(self) -> None:
        if self.client:
            await self.client.aclose()
