import asyncio
from typing import AsyncGenerator
from urllib.parse import urlparse
import os

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper

class OrganicSearchScraper(BaseScraper):
    """Organic search discovery engine using DuckDuckGo HTML version via Playwright."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        
    @property
    def name(self) -> str:
        return "Organic Search"
        
    async def initialize(self) -> None:
        self._playwright = await async_playwright().start()
        proxy_settings = None
        proxy_url = os.getenv("PROXY_URL")
        if proxy_url:
            proxy_settings = {"server": proxy_url}
            proxy_user = os.getenv("PROXY_USER")
            proxy_pass = os.getenv("PROXY_PASS")
            if proxy_user and proxy_pass:
                proxy_settings["username"] = proxy_user
                proxy_settings["password"] = proxy_pass
                
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            proxy=proxy_settings,
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
        search_query = f"{query} in {location} official website"
        
        page = await self._context.new_page()
        try:
            # Go directly to search URL
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(search_query)
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            await page.goto(search_url, wait_until="domcontentloaded")
            
            try:
                await page.wait_for_selector("article[data-testid='result']", timeout=15000)
            except PlaywrightTimeoutError:
                # Sometimes DDG serves a different layout when direct linked, try fallback selector
                await page.wait_for_selector(".result", timeout=10000)
            
            while yielded_count < target:
                results = await page.locator("article[data-testid='result'], .result").all()
                for result in results:
                    if yielded_count >= target:
                        break
                        
                    link = result.locator("a[data-testid='result-title-a'], a.result__url").first
                    if not await link.count():
                        continue
                        
                    href = await link.get_attribute("href")
                    if not href or "duckduckgo.com" in href:
                        # Sometimes href is in a different attribute on older DDG versions
                        href = await link.get_attribute("data-expanded-url") or href
                        if not href:
                            continue
                        
                    if href.startswith("//"):
                        href = "https:" + href
                        
                    domain = urlparse(href).netloc.replace("www.", "")
                    
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
                    
                if yielded_count >= target:
                    break
                    
                # Next page (infinite scroll usually, but sometimes there's a button)
                more_btn = page.locator("#more-results").first
                if await more_btn.count() and await more_btn.is_visible():
                    await more_btn.click()
                    await asyncio.sleep(2)
                else:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                # Wait for more results to load
                try:
                    await page.wait_for_selector("article[data-testid='result'], .result", timeout=10000)
                except PlaywrightTimeoutError:
                    break
                    
        except Exception as e:
            raise RuntimeError(f"Search Discovery failed: {e}")
        finally:
            await page.close()
            
    async def shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
