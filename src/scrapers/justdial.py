import asyncio
from typing import AsyncGenerator
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class JustdialScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        
    @property
    def name(self) -> str:
        return "Justdial"
        
    async def initialize(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        self._context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        page = await self._context.new_page()
        try:
            justdial_query = f"{query} in {location}"
            await page.goto("https://www.justdial.com", wait_until="domcontentloaded")
            await asyncio.sleep(1.5)
            
            searchbox = page.locator("input[type='search'], input[placeholder*='Search']").first
            try:
                await searchbox.wait_for(state="visible", timeout=8000)
                await searchbox.fill(justdial_query)
                await searchbox.press("Enter")
                await asyncio.sleep(2.0)
            except PlaywrightTimeoutError:
                return
                
            yielded_count = 0
            seen_urls = set()
            
            for _ in range(15): # Max scrolls
                if yielded_count >= target:
                    break
                    
                listings = await page.locator(".srvr-title, .resultbox, .store-info").all()
                
                for listing in listings:
                    if yielded_count >= target:
                        break
                        
                    try:
                        name_elem = listing.locator("h2, .title, .name").first
                        name = await name_elem.inner_text() if await name_elem.count() else ""
                        name = name.strip()
                        
                        phone_elem = listing.locator("[class*='phone'], [class*='contact'], .mobile").first
                        phone = await phone_elem.inner_text() if await phone_elem.count() else ""
                        phone = normalize_phone(phone)
                        
                        url_elem = listing.locator("a[href]").first
                        url = await url_elem.get_attribute("href") if await url_elem.count() else ""
                        
                        if name and url and url not in seen_urls:
                            seen_urls.add(url)
                            result = SourceResult(
                                source_name=self.name,
                                source_url=url if url.startswith("http") else f"https://www.justdial.com{url}",
                                business_name=name,
                                phone=phone if phone else None,
                                city=location
                            )
                            yield result
                            yielded_count += 1
                    except Exception:
                        continue
                        
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)
                except Exception:
                    break
                    
        finally:
            await page.close()

    async def shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
