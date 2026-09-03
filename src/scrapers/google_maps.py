import asyncio
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

from src.models.source_result import SourceResult
from src.scrapers.base import BaseScraper
from src.processing.normalizer import normalize_phone

class GoogleMapsScraper(BaseScraper):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        
    @property
    def name(self) -> str:
        return "Google Maps"
        
    async def initialize(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        self._context = await self._browser.new_context(
            locale="en-US",
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
    async def shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _canonicalize_place_url(self, url: str) -> str:
        try:
            p = urlparse(url)
            q = dict(parse_qsl(p.query, keep_blank_values=True))
            for noisy in ("authuser", "hl", "entry", "g_ep", "g_st", "g_mvn"):
                q.pop(noisy, None)
            query = urlencode(q, doseq=True)
            return urlunparse((p.scheme, p.netloc, p.path, p.params, query, p.fragment))
        except Exception:
            return url

    async def _maybe_accept_consent(self, page: Page) -> None:
        candidates = [
            "#introAgreeButton",
            'button:has-text("I agree")',
            'button:has-text("Agree")',
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button[type="submit"]',
        ]
        targets = [page]
        try:
            targets += page.frames
        except Exception:
            pass
            
        for tgt in targets:
            for sel in candidates:
                try:
                    btn = tgt.locator(sel).first
                    if await btn.count() and await btn.is_visible():
                        await btn.click(timeout=3000)
                        await asyncio.sleep(1)
                        return
                except Exception:
                    pass

    async def _search(self, page: Page, query: str) -> None:
        await page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await self._maybe_accept_consent(page)
        
        url = page.url.lower()
        if "/sorry/" in url:
            raise RuntimeError("Google blocked the automated browser (CAPTCHA/unusual traffic).")
            
        searchbox = page.locator("#searchboxinput, input.searchboxinput, input[name='q'], input[aria-label*='Search']").first
        try:
            await searchbox.wait_for(state="visible", timeout=20_000)
        except PlaywrightTimeoutError:
            await self._maybe_accept_consent(page)
            await searchbox.wait_for(state="visible", timeout=10_000)
            
        await searchbox.fill(query)
        await searchbox.press("Enter")
        await asyncio.sleep(1.5)

    async def _scroll_results(self, feed) -> None:
        stagnant_rounds = 0
        last_height = -1
        
        for _ in range(5): # Short burst of scrolls
            try:
                height = await feed.evaluate("el => el.scrollHeight")
                if height == last_height:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0
                    last_height = height
                    
                if stagnant_rounds >= 2:
                    break
                    
                await feed.evaluate("el => { el.scrollTop = el.scrollHeight - 200; }")
                await asyncio.sleep(0.15)
                await feed.evaluate("el => { el.scrollTop = el.scrollHeight; }")
                await asyncio.sleep(0.8)
            except Exception:
                break

    async def scrape(self, query: str, location: str, target: int) -> AsyncGenerator[SourceResult, None]:
        page = await self._context.new_page()
        try:
            search_query = f"{query} in {location}"
            await self._search(page, search_query)
            
            feed = page.locator('div[role="feed"]').first
            try:
                await feed.wait_for(state="visible", timeout=15_000)
            except PlaywrightTimeoutError:
                # Might be a direct place page instead of a list
                name_el = page.locator("h1").first
                if await name_el.count() and await name_el.is_visible():
                    name = (await name_el.inner_text()).strip()
                    phone = await self._extract_phone(page)
                    website = await self._extract_website(page)
                    yield SourceResult(
                        source_name=self.name,
                        source_url=page.url,
                        business_name=name,
                        phone=phone,
                        website=website,
                        city=location
                    )
                return

            yielded_count = 0
            seen_urls = set()
            
            # Collection phase
            stagnant_rounds = 0
            last_seen = 0
            
            # Phase 1: Collect URLs
            while len(seen_urls) < target * 1.5:
                cards = feed.locator('div[role="article"]')
                card_count = await cards.count()
                
                for i in range(card_count):
                    card = cards.nth(i)
                    try:
                        link = card.locator('a[href*="/maps/place"]').first
                        href = await link.get_attribute("href") if await link.count() else None
                        if href:
                            if href.startswith("/"):
                                href = "https://www.google.com" + href
                            href = self._canonicalize_place_url(href)
                            if "/maps/place" in href and href not in seen_urls:
                                seen_urls.add(href)
                    except Exception:
                        continue
                        
                if len(seen_urls) == last_seen:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0
                    last_seen = len(seen_urls)
                    
                if stagnant_rounds >= 3:
                    break
                    
                await self._scroll_results(feed)
                
            # Phase 2: Extract Details
            for url in list(seen_urls):
                if yielded_count >= target:
                    break
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
                    await asyncio.sleep(0.5)
                    
                    name_el = page.locator("h1").first
                    if not await name_el.count():
                        continue
                        
                    name = (await name_el.inner_text()).strip()
                    if not name or name.lower() == "results":
                        continue
                        
                    phone = await self._extract_phone(page)
                    website = await self._extract_website(page)
                    
                    yield SourceResult(
                        source_name=self.name,
                        source_url=url,
                        business_name=name,
                        phone=phone,
                        website=website,
                        city=location
                    )
                    yielded_count += 1
                except Exception as e:
                    print(f"Error extracting {url}: {e}")
                    continue
                    
        finally:
            await page.close()

    async def _extract_phone(self, page: Page) -> Optional[str]:
        selectors = [
            'button[data-item-id*="phone"]',
            'button[aria-label^="Phone:"]',
            'button[aria-label*="Phone:"]',
            'div[role="region"] button[aria-label*="Phone"]',
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() and await btn.is_visible():
                    aria = (await btn.get_attribute("aria-label") or "").strip()
                    if "Phone" in aria:
                        phone = aria.split(":", 1)[-1].strip() if ":" in aria else aria
                        if phone:
                            return normalize_phone(phone)
                    text = await btn.inner_text() or ""
                    if text:
                        return normalize_phone(text)
            except Exception:
                pass
        return None
        
    async def _extract_website(self, page: Page) -> Optional[str]:
        selectors = [
            'a[data-item-id*="authority"]',
            'a[aria-label^="Website:"]',
        ]
        for sel in selectors:
            try:
                link = page.locator(sel).first
                if await link.count() and await link.is_visible():
                    href = await link.get_attribute("href")
                    if href:
                        return href
            except Exception:
                pass
        return None
