"""
WebsiteCrawler — crawls business websites for email extraction.

Proxy rotation: set PROXY_LIST env var as comma-separated URLs:
  PROXY_LIST=http://user:pass@host1:port,http://user:pass@host2:port

Or single proxy: PROXY_URL=http://user:pass@host:port
"""

import asyncio
import httpx
import os
import time
import itertools
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from src.models.lead import Lead
from src.enrichment.email_extractor import EmailExtractor


class ProxyPool:
    """Round-robin rotating proxy pool with cooldown on failures."""

    COOLDOWN_SECONDS = 60

    def __init__(self, proxy_urls: List[str]):
        self._proxies = proxy_urls
        self._cooldowns: dict = {}  # proxy_url -> cooldown_until timestamp
        self._cycle = itertools.cycle(proxy_urls) if proxy_urls else None

    @classmethod
    def from_env(cls) -> "ProxyPool":
        """Build pool from PROXY_LIST or PROXY_URL env vars."""
        proxy_list_raw = os.getenv("PROXY_LIST", "")
        if proxy_list_raw:
            proxies = [p.strip() for p in proxy_list_raw.split(",") if p.strip()]
        else:
            # Single proxy fallback
            proxy_url = os.getenv("PROXY_URL", "")
            if proxy_url:
                user = os.getenv("PROXY_USER", "")
                password = os.getenv("PROXY_PASS", "")
                if user and password:
                    proxy_url = proxy_url.replace("http://", "").replace("https://", "")
                    proxy_url = f"http://{user}:{password}@{proxy_url}"
                proxies = [proxy_url]
            else:
                proxies = []
        return cls(proxies)

    def get_next(self) -> Optional[str]:
        """Return the next available (non-cooled-down) proxy, or None for direct."""
        if not self._proxies:
            return None
        now = time.time()
        for _ in range(len(self._proxies)):
            proxy = next(self._cycle)
            if self._cooldowns.get(proxy, 0) <= now:
                return proxy
        # All proxies on cooldown — return first one anyway (can't wait forever)
        return self._proxies[0]

    def mark_failed(self, proxy_url: str):
        """Cool down a proxy that returned 429/403/blocked."""
        if proxy_url:
            self._cooldowns[proxy_url] = time.time() + self.COOLDOWN_SECONDS


class WebsiteCrawler:
    """
    Crawls business websites to extract contact info (emails).
    Supports rotating proxy pool via PROXY_LIST env var.
    """

    TARGET_PATHS = ["", "/", "/contact", "/contact-us", "/about", "/about-us",
                    "/kontakt", "/impressum", "/imprint"]

    def __init__(self, max_pages_per_domain: int = 5, concurrency: int = 10):
        self.max_pages = max_pages_per_domain
        self.semaphore = asyncio.Semaphore(concurrency)
        self.email_extractor = EmailExtractor()
        self._domain_cache: dict = {}
        self.proxy_pool = ProxyPool.from_env()

    async def crawl_lead(self, lead: Lead) -> None:
        """Crawl a lead's website and enrich it with discovered emails."""
        if not lead.website:
            return

        base_url = lead.website
        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        domain = urlparse(base_url).netloc

        # Return cached results instantly
        if domain in self._domain_cache:
            for email_obj in self._domain_cache[domain]:
                if email_obj.email not in lead.emails:
                    lead.emails[email_obj.email] = email_obj
            return

        self._domain_cache[domain] = []

        proxy = self.proxy_pool.get_next()
        client_kwargs = dict(timeout=12.0, verify=False, follow_redirects=True)
        if proxy:
            client_kwargs["proxy"] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            tasks = [
                self._fetch_and_extract(client, urljoin(base_url, path), lead, domain, path, proxy)
                for path in self.TARGET_PATHS
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_and_extract(self, client: httpx.AsyncClient, url: str,
                                  lead: Lead, domain: str, path: str,
                                  proxy: Optional[str]) -> None:
        async with self.semaphore:
            try:
                response = await client.get(url)

                # Cool down proxy on rate-limit responses
                if response.status_code in (429, 403) and proxy:
                    self.proxy_pool.mark_failed(proxy)

                if response.status_code != 200:
                    return

                text = response.text
                emails = self.email_extractor.extract_from_text(text, url, method="text")
                soup = BeautifulSoup(text, "html.parser")

                # Extract business name from page title (overrides domain-derived name)
                if path in ("", "/"):
                    title_tag = soup.find("title")
                    if title_tag and title_tag.text:
                        candidate = title_tag.text.strip()[:100]
                        # Only update if current name looks like a raw domain
                        if "." in lead.business_name or lead.business_name.islower():
                            lead.business_name = candidate
                            lead.normalized_name = candidate.lower()

                    meta_desc = soup.find("meta", attrs={"name": "description"})
                    if meta_desc and meta_desc.get("content"):
                        lead.category = meta_desc["content"].strip()[:200]

                # Also extract mailto: links
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if href.lower().startswith("mailto:"):
                        mailto_email = href[7:].split("?")[0].strip()
                        emails.extend(
                            self.email_extractor.extract_from_text(mailto_email, url, method="mailto")
                        )

                for email_obj in emails:
                    if email_obj.email not in lead.emails:
                        lead.emails[email_obj.email] = email_obj
                        self._domain_cache[domain].append(email_obj)

            except Exception:
                pass
