import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import AsyncGenerator

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class TradeIndiaScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.client = None
        
    @property
    def name(self) -> str:
        return "TradeIndia"
        
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
        search_url = f"https://www.tradeindia.com/search.html?keyword={query}&city={location}"
        
        try:
            resp = await self.client.get(search_url)
            if resp.status_code != 200:
                raise RuntimeError(f"TradeIndia failed with {resp.status_code}")
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            listings = soup.find_all("div", class_="card-body")
            
            for listing in listings:
                if yielded_count >= target:
                    break
                    
                name_tag = listing.find("a", class_="company-name")
                if not name_tag:
                    continue
                    
                name = name_tag.text.strip()
                url = name_tag["href"] if "href" in name_tag.attrs else search_url
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("/"):
                    url = "https://www.tradeindia.com" + url
                    
                phone_tag = listing.find("a", href=lambda h: h and h.startswith("tel:"))
                phone = normalize_phone(phone_tag["href"]) if phone_tag else None
                
                yield SourceResult(
                    source_name=self.name,
                    source_url=url,
                    business_name=name,
                    phone=phone,
                    city=location
                )
                yielded_count += 1
                
        except Exception as e:
            raise RuntimeError(f"TradeIndia scraping failed: {e}")
            
    async def shutdown(self) -> None:
        if self.client:
            await self.client.aclose()
