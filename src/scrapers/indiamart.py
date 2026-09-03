import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import AsyncGenerator

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class IndiaMARTScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.client = None
        
    @property
    def name(self) -> str:
        return "IndiaMART"
        
    async def initialize(self) -> None:
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=15.0
        )
        
    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        if not self.client:
            await self.initialize()
            
        yielded_count = 0
        search_url = f"https://dir.indiamart.com/search.mp?ss={query}&mcatid=&catid=&cq={location}"
        
        try:
            resp = await self.client.get(search_url)
            if resp.status_code != 200:
                raise RuntimeError(f"IndiaMART failed with {resp.status_code}")
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            listings = soup.find_all("div", class_="lst_cl")
            
            for listing in listings:
                if yielded_count >= target:
                    break
                    
                name_tag = listing.find("h4")
                if not name_tag:
                    continue
                    
                name = name_tag.text.strip()
                phone_tag = listing.find("span", class_="pns_h")
                phone = normalize_phone(phone_tag.text) if phone_tag else None
                
                url_tag = listing.find("a", href=True)
                url = url_tag["href"] if url_tag else search_url
                if url.startswith("//"):
                    url = "https:" + url
                    
                yield SourceResult(
                    source_name=self.name,
                    source_url=url,
                    business_name=name,
                    phone=phone,
                    city=location
                )
                yielded_count += 1
                
        except Exception as e:
            raise RuntimeError(f"IndiaMART scraping failed: {e}")
            
    async def shutdown(self) -> None:
        if self.client:
            await self.client.aclose()
