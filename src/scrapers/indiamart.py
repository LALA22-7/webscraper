import asyncio
from typing import AsyncGenerator
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class IndiaMARTScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        
    @property
    def name(self) -> str:
        return "IndiaMART"
        
    async def initialize(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security'
            ]
        )
        self._context = await self._browser.new_context(
            locale="en-US",
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        if not self._context:
            await self.initialize()
            
        yielded_count = 0
        search_url = f"https://dir.indiamart.com/search.mp?ss={query}&mcatid=&catid=&cq={location}"
        
        page = await self._context.new_page()
        try:
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_selector(".staticSupplierBox, .lst_cl", timeout=15000)
            
            # Wait for JS to populate the page
            await asyncio.sleep(3)
            
            while yielded_count < target:
                listings = await page.locator(".staticSupplierBox, .lst_cl").all()
                for listing in listings:
                    if yielded_count >= target:
                        break
                        
                    name_tag = listing.locator("h3.companyName, a.companyName, h4").first
                    if not await name_tag.count():
                        continue
                        
                    name = await name_tag.inner_text()
                    phone = None
                    phone_tag = listing.locator("span.pns_h, span.call-btn").first
                    if await phone_tag.count():
                        phone = await phone_tag.inner_text()
                        phone = normalize_phone(phone)
                        
                    url_tag = listing.locator("a[href]").first
                    url = await url_tag.get_attribute("href") if await url_tag.count() else search_url
                    if url.startswith("//"):
                        url = "https:" + url
                        
                    yield SourceResult(
                        source_name=self.name,
                        source_url=url,
                        business_name=name.strip(),
                        phone=phone,
                        city=location
                    )
                    yielded_count += 1
                    
                if yielded_count >= target:
                    break
                    
                # Scroll to load more
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)
                
                # We do this for a maximum of a few scrolls then break if no new items
                new_listings = await page.locator(".staticSupplierBox, .lst_cl").count()
                if new_listings <= len(listings):
                    break # No more results loaded
                    
        except Exception as e:
            raise RuntimeError(f"IndiaMART scraping failed: {e}")
        finally:
            await page.close()
            
    async def shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
