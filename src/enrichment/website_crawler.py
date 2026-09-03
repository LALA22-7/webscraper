import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import List, Set
from urllib.parse import urljoin, urlparse

from src.models.lead import Lead
from src.enrichment.email_extractor import EmailExtractor

class WebsiteCrawler:
    """Crawls business websites to extract contact info (emails)."""
    
    def __init__(self, max_pages_per_domain: int = 5, concurrency: int = 10):
        self.max_pages = max_pages_per_domain
        self.semaphore = asyncio.Semaphore(concurrency)
        self.email_extractor = EmailExtractor()
        self.target_paths = ["", "/", "/contact", "/contact-us", "/about", "/about-us"]
        self._domain_cache: dict[str, List[Email]] = {}
        
    async def crawl_lead(self, lead: Lead) -> None:
        """Crawl a lead's website and enrich the lead object with discovered emails."""
        if not lead.website:
            return
            
        base_url = lead.website
        if not base_url.startswith("http"):
            base_url = "https://" + base_url
            
        domain = urlparse(base_url).netloc
        
        # Check cache
        if domain in self._domain_cache:
            for email_obj in self._domain_cache[domain]:
                if email_obj.email not in lead.emails:
                    lead.emails[email_obj.email] = email_obj
            return
            
        # Initialize cache for this domain
        self._domain_cache[domain] = []
        
        urls_to_visit = [urljoin(base_url, path) for path in self.target_paths]
        
        async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
            tasks = [self._fetch_and_extract(client, url, lead, domain) for url in urls_to_visit]
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _fetch_and_extract(self, client: httpx.AsyncClient, url: str, lead: Lead, domain: str) -> None:
        async with self.semaphore:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    text = response.text
                    emails = self.email_extractor.extract_from_text(text, url, method="text")
                    
                    soup = BeautifulSoup(text, "html.parser")
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"]
                        if href.lower().startswith("mailto:"):
                            mailto_email = href[7:].split('?')[0].strip()
                            emails.extend(self.email_extractor.extract_from_text(mailto_email, url, method="mailto"))
                            
                    for email_obj in emails:
                        if email_obj.email not in lead.emails:
                            lead.emails[email_obj.email] = email_obj
                            # add to cache
                            self._domain_cache[domain].append(email_obj)
                            
            except Exception:
                pass
