import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from typing import AsyncGenerator
from urllib.parse import urlencode

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class SulekhaScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.client = None
        
    @property
    def name(self) -> str:
        return "Sulekha"
        
    async def initialize(self) -> None:
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            },
            timeout=15.0,
            verify=False
        )
        
    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        if not self.client:
            await self.initialize()
            
        yielded_count = 0
        seen = set()
        
        # Build search URL (e.g. sulekha.com/noida/gyms)
        # We use a simple internal site search format
        search_url = f"https://www.sulekha.com/{query.replace(' ', '-')}/{location.replace(' ', '-')}"
        
        try:
            for page in range(1, 10): # Pagination
                if yielded_count >= target:
                    break
                    
                url = f"{search_url}?page={page}" if page > 1 else search_url
                resp = await self.client.get(url)
                
                if resp.status_code == 404:
                    break
                if resp.status_code != 200:
                    raise RuntimeError(f"Sulekha blocked or failed with status {resp.status_code}")
                    
                soup = BeautifulSoup(resp.text, 'html.parser')
                listings = soup.find_all("li", class_="list-item")
                
                if not listings:
                    break
                    
                for listing in listings:
                    if yielded_count >= target:
                        break
                        
                    name_tag = listing.find("h3")
                    if not name_tag:
                        continue
                        
                    name = name_tag.text.strip()
                    if name in seen:
                        continue
                    seen.add(name)
                    
                    # Phone extraction can be tricky on Sulekha as they mask it, 
                    # but sometimes it's in a data attribute
                    phone = None
                    phone_tag = listing.find(attrs={"data-vno": True})
                    if phone_tag:
                        phone = normalize_phone(phone_tag["data-vno"])
                        
                    # Extract address
                    address = None
                    addr_tag = listing.find("address")
                    if addr_tag:
                        address = addr_tag.text.strip()
                        
                    yield SourceResult(
                        source_name=self.name,
                        source_url=url,
                        business_name=name,
                        phone=phone,
                        city=location,
                        address=address
                    )
                    yielded_count += 1
                    
                await asyncio.sleep(2) # Cooldown
                
        except Exception as e:
            # If the request fails (e.g., CAPTCHA or networking), we yield and the orchestrator handles it
            raise RuntimeError(f"Sulekha scraping failed: {e}")
            
    async def shutdown(self) -> None:
        if self.client:
            await self.client.aclose()
