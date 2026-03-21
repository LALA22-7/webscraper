import argparse
import csv
import re
import sys
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import hashlib

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class PlaceRow:
    name: str
    phone: str
    url: str


def _generate_unique_key(name: str, phone: str) -> str:
    """Generate unique key for duplicate detection based on name and phone"""
    # Clean and normalize data for comparison
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', name.lower().strip())
    clean_phone = re.sub(r'[^0-9]', '', phone)
    combined = f"{clean_name}_{clean_phone}"
    return hashlib.md5(combined.encode()).hexdigest()


def _is_duplicate(row: PlaceRow, existing_keys: set[str]) -> bool:
    """Check if a row is duplicate based on name and phone"""
    key = _generate_unique_key(row.name, row.phone)
    return key in existing_keys


def _clean_phone(s: str) -> str:
    s = s.strip()
    # Keep digits, spaces, +, -, parentheses
    s = re.sub(r"[^\d+\-() ]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _maybe_accept_consent(page) -> None:
    # Consent UI varies by region/account. Best-effort only.
    candidates = [
        "#introAgreeButton",  # common on consent.google.com
        'button:has-text("I agree")',
        'button:has-text("Agree")',
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        'button:has-text("Reject all")',
        'button:has-text("Reject")',
        'button:has-text("Yes, I\'m in")',
        'button[type="submit"]',
    ]

    targets = [page]
    try:
        targets += list(page.frames)
    except Exception:
        pass

    for tgt in targets:
        for sel in candidates:
            try:
                btn = tgt.locator(sel).first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1000)
                    return
            except Exception:
                pass


def _search(page, query: str) -> None:
    page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
    page.wait_for_timeout(800)  # Reduced from 1200
    _maybe_accept_consent(page)

    # Sometimes Google redirects to consent / "unusual traffic" pages where Maps UI is absent.
    url = page.url.lower()
    if "consent.google.com" in url:
        _maybe_accept_consent(page)
        try:
            page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
            page.wait_for_timeout(800)  # Reduced from 1200
        except Exception:
            pass

    url = page.url.lower()
    if "/sorry/" in url:
        raise RuntimeError(
            "Google blocked the automated browser (URL contains '/sorry/'). "
            "Try running without --headless, wait a bit, or use a different network/profile."
        )

    searchbox = page.locator(
        "#searchboxinput, input[aria-label*='Search'][role='combobox'], input[role='combobox']"
    ).first
    try:
        searchbox.wait_for(state="visible", timeout=45_000)  # Reduced from 60_000
    except PlaywrightTimeoutError:
        _maybe_accept_consent(page)
        try:
            searchbox.wait_for(state="visible", timeout=15_000)  # Reduced from 20_000
        except PlaywrightTimeoutError as e:
            # Save a screenshot to help diagnose what loaded (consent, captcha, etc).
            try:
                page.screenshot(path="debug_maps.png", full_page=True)
            except Exception:
                pass
            raise RuntimeError(
                "Could not find the Google Maps search box. "
                "A screenshot may have been saved as 'debug_maps.png' in this folder. "
                "Common causes: cookie consent screen, CAPTCHA/unusual-traffic block."
            ) from e

    searchbox.fill(query)
    searchbox.press("Enter")

    # Wait until results list or place details appear.
    page.wait_for_timeout(1000)  # Reduced from 1500
    page.wait_for_load_state("domcontentloaded")


def _get_results_feed(page):
    # Search results list container.
    feed = page.locator('div[role="feed"]').first
    try:
        feed.wait_for(state="visible", timeout=20_000)
        return feed
    except PlaywrightTimeoutError:
        return None


def _canonicalize_place_url(url: str) -> str:
    """
    Keep the place URL stable for dedupe. Google appends noisy query params.
    """
    try:
        p = urlparse(url)
        q = dict(parse_qsl(p.query, keep_blank_values=True))
        for noisy in ("authuser", "hl", "entry", "g_ep", "g_st", "g_mvn"):
            q.pop(noisy, None)
        query = urlencode(q, doseq=True)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, query, p.fragment))
    except Exception:
        return url


def _collect_place_urls(feed) -> set[str]:
    """
    Collect visible place links from the results feed.
    Google Maps virtualizes the list, so we must collect as we scroll.
    """
    if feed is None:
        return set()

    links = feed.locator('a[href^="https://www.google.com/maps/place"]')
    try:
        hrefs = links.evaluate_all("els => els.map(e => e.href)")
    except Exception:
        hrefs = []

    out: set[str] = set()
    for h in hrefs or []:
        if isinstance(h, str) and ("/maps/place" in h or "/maps/place/" in h):
            out.add(_canonicalize_place_url(h))
    return out


def _scroll_results(feed, max_scrolls: int = 25) -> None:  # Reduced from 40
    if feed is None:
        return

    # Scroll until no new height change for several rounds or until max_scrolls.
    # Google Maps virtualizes the list; we need to scroll enough to trigger loading.
    stagnant_rounds = 0
    last_height = -1

    for _ in range(max_scrolls):
        try:
            height = feed.evaluate("el => el.scrollHeight")
        except Exception:
            break

        if height == last_height:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
            last_height = height

        if stagnant_rounds >= 2:  # Reduced from 3 for faster completion
            break

        try:
            # Scroll more aggressively for faster results
            feed.evaluate("el => { el.scrollTop = el.scrollHeight - 200; }")
            feed.page.wait_for_timeout(150)  # Reduced from 200
            feed.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        except Exception:
            break

        # Give Google time to load more results into the virtualized list
        feed.page.wait_for_timeout(800)  # Reduced from 1200


def _iter_result_cards(feed) -> Iterable:
    # Cards typically expose role="article" inside the feed.
    if feed is None:
        return []
    return feed.locator('div[role="article"]').all()


def _card_place_url(card) -> Optional[str]:
    """
    Try to read the place URL directly from a result card without navigating away.
    This is more stable than clicking and avoids getting stuck on a single details page.
    """
    try:
        link = card.locator('a[href*="/maps/place"]').first
        href = link.get_attribute("href") if link.count() else None
        if isinstance(href, str) and href:
            # Google sometimes returns relative URLs from attributes.
            if href.startswith("/"):
                href = "https://www.google.com" + href
            return href
    except Exception:
        pass
    return None


def _open_card(page, card) -> Optional[str]:
    # Prefer clicking the card; sometimes the card contains a link.
    try:
        card.scroll_into_view_if_needed(timeout=3000)  # Reduced from 5000
    except Exception:
        pass

    # Capture URL change after click to use as stable key.
    before = page.url
    try:
        card.click(timeout=6000)  # Reduced from 8000
    except Exception:
        try:
            link = card.locator('a[href^="https://www.google.com/maps/place"]').first
            link.click(timeout=6000)  # Reduced from 8000
        except Exception:
            return None

    try:
        page.wait_for_timeout(500)  # Reduced from 800
        page.wait_for_load_state("domcontentloaded")
    except Exception:
        pass

    after = page.url
    if after != before and "google.com/maps" in after:
        return after
    return page.url


def _extract_name(page) -> str:
    # Name is typically the H1 at top of the details pane.
    h1 = page.locator("h1").first
    try:
        h1.wait_for(state="visible", timeout=8000)  # Reduced from 10_000
        name = h1.inner_text().strip()
        return name
    except Exception:
        return ""


def scrape_justdial(page, query: str, max_places: int) -> list[PlaceRow]:
    """Scrape Justdial as alternative source"""
    rows = []
    try:
        # Extract profession and location from query
        if " in " in query:
            profession, location = query.split(" in ", 1)
            justdial_query = f"{profession} in {location}"
        else:
            justdial_query = query
            
        page.goto("https://www.justdial.com", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)  # Reduced from 2000
        
        # Search on Justdial
        searchbox = page.locator("input[type='search'], input[placeholder*='Search']").first
        try:
            searchbox.wait_for(state="visible", timeout=8000)  # Reduced from 10_000
            searchbox.fill(justdial_query)
            searchbox.press("Enter")
            page.wait_for_timeout(2000)  # Reduced from 3000
        except:
            return rows
            
        # Scroll and collect results
        for _ in range(15):  # Reduced from 20 scrolls
            if len(rows) >= max_places:
                break
                
            # Get business listings
            listings = page.locator(".srvr-title, .resultbox, .store-info").all()
            
            for listing in listings[:10]:  # Process first 10 per scroll
                if len(rows) >= max_places:
                    break
                    
                try:
                    # Extract name
                    name_elem = listing.locator("h2, .title, .name").first
                    name = name_elem.inner_text().strip() if name_elem.count() else ""
                    
                    # Extract phone
                    phone_elem = listing.locator("[class*='phone'], [class*='contact'], .mobile").first
                    phone = phone_elem.inner_text().strip() if phone_elem.count() else ""
                    phone = _clean_phone(phone)
                    
                    # Extract URL if available
                    url_elem = listing.locator("a[href]").first
                    url = url_elem.get_attribute("href") if url_elem.count() else ""
                    
                    if name and phone:
                        rows.append(PlaceRow(name=name, phone=phone, url=url or "https://www.justdial.com"))
                except:
                    continue
                    
            # Scroll down
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)  # Reduced from 1500
            except:
                break
                
    except Exception as e:
        print(f"Justdial scraping error: {e}")
        
    return rows


def _extract_phone(page) -> str:
    # Commonly stored in a button with data-item-id="phone" or aria-label starting with "Phone:"
    selectors = [
        'button[data-item-id*="phone"]',
        'button[aria-label^="Phone:"]',
        'button[aria-label*="Phone:"]',
        'div[role="region"] button[aria-label*="Phone"]',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible():
                aria = (btn.get_attribute("aria-label") or "").strip()
                if "Phone" in aria:
                    # e.g. "Phone: +91 98xxxxxx"
                    phone = aria.split(":", 1)[-1].strip() if ":" in aria else aria
                    phone = _clean_phone(phone)
                    if phone:
                        return phone
                text = _clean_phone(btn.inner_text() or "")
                if text:
                    return text
        except Exception:
            pass
    return ""


def _get_profession_specific_searches(profession: str, location: str) -> list[str]:
    """Get profession-specific search variations"""
    profession_lower = profession.lower()
    
    # Medical professions get medical-specific searches
    if any(medical in profession_lower for medical in ['doctor', 'clinic', 'hospital', 'dental', 'dentist', 'medical', 'physician', 'surgeon']):
        return [
            f"{profession} in {location}",
            f"{profession} near {location}",
            f"best {profession} in {location}",
            f"{profession} clinic in {location}",
            f"{profession} hospital in {location}"
        ]
    
    # Food-related professions get food-specific searches
    elif any(food in profession_lower for food in ['restaurant', 'food', 'cafe', 'bakery', 'pizza', 'burger']):
        return [
            f"{profession} in {location}",
            f"{profession} near {location}",
            f"best {profession} in {location}",
            f"good {profession} in {location}",
            f"top {profession} in {location}"
        ]
    
    # Service professions get service-specific searches
    elif any(service in profession_lower for service in ['salon', 'spa', 'gym', 'fitness', 'parlor']):
        return [
            f"{profession} in {location}",
            f"{profession} near {location}",
            f"best {profession} in {location}",
            f"good {profession} in {location}",
            f"{profession} center in {location}"
        ]
    
    # Education professions
    elif any(edu in profession_lower for edu in ['school', 'college', 'university', 'institute', 'tuition']):
        return [
            f"{profession} in {location}",
            f"{profession} near {location}",
            f"best {profession} in {location}",
            f"top {profession} in {location}"
        ]
    
    # Default generic searches for other professions
    else:
        return [
            f"{profession} in {location}",
            f"{profession} near {location}",
            f"best {profession} in {location}"
        ]


def scrape_google_maps(query: str, max_places: int, output_csv: str, headless: bool, progress_callback=None) -> int:
    rows: list[PlaceRow] = []
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()  # For duplicate detection

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        context = browser.new_context(
            locale="en-US",
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # Extract profession and location from query
        if " in " in query:
            profession, location = query.split(" in ", 1)
        else:
            # Fallback parsing
            parts = query.split()
            if len(parts) >= 2:
                profession = " ".join(parts[:-1])
                location = parts[-1]
            else:
                profession = query
                location = "India"  # Default fallback

        # Get canonical location name
        canonical_location = _LOCATION_GUESS.get(location.lower(), location.title())
        
        print(f"=== Smart Lead Generation ===")
        print(f"Target: {max_places} {profession.lower()}")
        print(f"Starting from: {canonical_location}")
        
        # Smart search strategy - prioritize high-yield searches
        search_queue = []
        search_results = {}  # Track yield per search type
        
        # Phase 1: Primary location with best searches first
        primary_searches = _get_profession_specific_searches(profession, canonical_location)
        
        # Sort searches by priority (put most likely to succeed first)
        primary_searches.sort(key=lambda x: 0 if "in " in x else (1 if "near " in x else 2))
        
        for search_query in primary_searches:
            search_queue.append((search_query, canonical_location, "primary"))
        
        # Track search performance
        consecutive_zero_results = 0
        max_zero_results = 3  # Stop after 3 consecutive zero-result searches
        
        while len(rows) < max_places and search_queue:
            search_query, current_location, search_type = search_queue.pop(0)
            
            # Skip if we already have enough leads
            if len(rows) >= max_places:
                break
                
            print(f"\n--- Searching: {search_query} ({len(rows)}/{max_places} collected) ---")
            
            # Perform search
            _search(page, search_query)
            feed = _get_results_feed(page)
            
            # Collect results
            remaining_needed = max_places - len(rows)
            new_results = _collect_results_from_feed(page, feed, remaining_needed, seen_urls, seen_keys)
            rows.extend(new_results)
            
            # Track performance
            yield_count = len(new_results)
            search_results[search_query] = yield_count
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback({
                    'current_location': current_location,
                    'current_search': search_query,
                    'results_found': len(rows),
                    'target': max_places,
                    'search_yield': yield_count,
                    'status': 'searching'
                })
            
            print(f"    Found {yield_count} results (Total: {len(rows)})")
            
            # Early termination if target reached
            if len(rows) >= max_places:
                print(f"  ✓ Target reached! Collected {len(rows)} leads.")
                if progress_callback:
                    progress_callback({
                        'status': 'completed',
                        'results_found': len(rows),
                        'target': max_places
                    })
                break
            
            # Track consecutive zero results
            if yield_count == 0:
                consecutive_zero_results += 1
                print(f"    ⚠ No results found ({consecutive_zero_results}/{max_zero_results} consecutive)")
                
                # Stop if too many consecutive failures
                if consecutive_zero_results >= max_zero_results:
                    print(f"    🛑 Stopping search due to low yield")
                    break
            else:
                consecutive_zero_results = 0  # Reset counter on success
            
            # Smart radius expansion - only add nearby cities if needed
            if (search_type == "primary" and len(rows) < max_places and 
                yield_count > 0 and canonical_location in _NEARBY_CITIES):
                
                # Calculate how many more we need
                remaining_needed = max_places - len(rows)
                
                # Add nearby cities based on how many we need
                nearby_cities = _NEARBY_CITIES[canonical_location]
                cities_to_add = min(3, len(nearby_cities))  # Add max 3 cities
                
                print(f"    📍 Expanding to {cities_to_add} nearby cities...")
                
                for city in nearby_cities[:cities_to_add]:
                    if len(rows) >= max_places:
                        break
                    
                    # Get city-specific searches (fewer variations for efficiency)
                    city_searches = [
                        f"{profession} in {city}",
                        f"{profession} near {city}"
                    ]
                    
                    for city_search in city_searches:
                        if len(rows) >= max_places:
                            break
                        search_queue.append((city_search, city, "nearby"))
        
        # Phase 2: Alternative sources only if still needed and primary search was productive
        if len(rows) < max_places and len(rows) > 0:
            remaining_needed = max_places - len(rows)
            print(f"\n=== Trying Justdial for {remaining_needed} more results ===")
            
            # Try only primary location for Justdial (more efficient)
            justdial_query = f"{profession} in {canonical_location}"
            print(f"Justdial: {justdial_query}")
            justdial_results = scrape_justdial(page, justdial_query, remaining_needed)
            
            for result in justdial_results:
                if len(rows) >= max_places:
                    break
                if not _is_duplicate(result, seen_keys):
                    seen_keys.add(_generate_unique_key(result.name, result.phone))
                    rows.append(result)
                    
            print(f"Justdial added {len(justdial_results)} results")
            
            if len(rows) >= max_places:
                print(f"  ✓ Target reached! Collected {len(rows)} leads.")

        context.close()
        browser.close()

    # Write CSV with duplicate prevention
    final_rows = []
    final_keys = set()
    
    for row in rows:
        if not _is_duplicate(row, final_keys):
            final_keys.add(_generate_unique_key(row.name, row.phone))
            final_rows.append(row)
    
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "phone", "url"])
        writer.writeheader()
        for r in final_rows:
            writer.writerow({"name": r.name, "phone": r.phone, "url": r.url})

    print(f"\n=== Final Results ===")
    print(f"Total unique results: {len(final_rows)}")
    print(f"Search efficiency: {len(final_rows)/len(search_results)*100:.1f}% avg yield per search")
    print(f"Saved to: {output_csv}")

    return len(final_rows)


def _collect_results_from_feed(page, feed, max_needed: int, seen_urls: set[str], seen_keys: set[str]) -> list[PlaceRow]:
    """Collect results from a single search feed"""
    rows = []
    
    if feed is None:
        # Single place page
        name = _extract_name(page)
        phone = _extract_phone(page)
        if name and name.strip().lower() != "results":
            url = page.url
            if url not in seen_urls:
                seen_urls.add(url)
                row = PlaceRow(name=name, phone=phone, url=url)
                if not _is_duplicate(row, seen_keys):
                    seen_keys.add(_generate_unique_key(name, phone))
                    rows.append(row)
        return rows

    # Multiple results page - collect URLs first
    stagnant_rounds = 0
    last_seen = 0
    scroll_rounds = 80  # Reduced from 120 for faster processing

    for _ in range(scroll_rounds):
        if len(seen_urls) >= max_needed * 1.3:  # Reduced from 1.5 to be faster
            break

        cards = feed.locator('div[role="article"]')
        try:
            card_count = cards.count()
        except Exception:
            card_count = 0

        for i in range(card_count):
            try:
                card = cards.nth(i)
                url = _card_place_url(card)
            except Exception:
                continue

            if not url:
                continue
            url = _canonicalize_place_url(url)
            if "/maps/place" not in url:
                continue
            if url in seen_urls:
                continue

            seen_urls.add(url)

        if len(seen_urls) == last_seen:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
            last_seen = len(seen_urls)

        if stagnant_rounds >= 4:  # Reduced from 6 for faster processing
            break

        _scroll_results(feed, max_scrolls=5)  # Reduced from 8
        page.wait_for_timeout(300)  # Reduced from 500

    # Extract details from collected URLs
    for url in list(seen_urls):
        if len(rows) >= max_needed:
            break
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25_000)  # Reduced from 30_000
        except Exception:
            continue

        page.wait_for_timeout(400)  # Reduced from 600
        name = _extract_name(page)
        if not name or name.strip().lower() == "results":
            continue
        phone = _extract_phone(page)
        row = PlaceRow(name=name, phone=phone, url=url)
        if not _is_duplicate(row, seen_keys):
            seen_keys.add(_generate_unique_key(name, phone))
            rows.append(row)

    return rows


MIN_LEADS = 10
MAX_LEADS = 1000
DEFAULT_LEADS = 50

# Common location misspellings/variants -> canonical name (for best-guess suggestion).
_LOCATION_GUESS: dict[str, str] = {
    # India
    "noda": "Noida",
    "noidaa": "Noida",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "gurgon": "Gurugram",
    "gurgao": "Gurugram",
    "delhi": "Delhi",
    "new delhi": "New Delhi",
    "mumbai": "Mumbai",
    "bomaby": "Mumbai",
    "bombay": "Mumbai",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "bangalor": "Bengaluru",
    "chennai": "Chennai",
    "madras": "Chennai",
    "hyderabad": "Hyderabad",
    "hydrabad": "Hyderabad",
    "hyd": "Hyderabad",
    "pune": "Pune",
    "puna": "Pune",
    "kolkata": "Kolkata",
    "calcutta": "Kolkata",
    "ahmedabad": "Ahmedabad",
    "ahmadabad": "Ahmedabad",
    "jaipur": "Jaipur",
    "lucknow": "Lucknow",
    "kanpur": "Kanpur",
    "nagpur": "Nagpur",
    "indore": "Indore",
    "thane": "Thane",
    "bhopal": "Bhopal",
    "visakhapatnam": "Visakhapatnam",
    "vizag": "Visakhapatnam",
    "patna": "Patna",
    "vadodara": "Vadodara",
    "baroda": "Vadodara",
    "ghaziabad": "Ghaziabad",
    "faridabad": "Faridabad",
    "meerut": "Meerut",
    "rajkot": "Rajkot",
    "cochin": "Kochi",
    "kochi": "Kochi",
    "coimbatore": "Coimbatore",
    "chandigarh": "Chandigarh",
    "guwahati": "Guwahati",
    "srinagar": "Srinagar",
    "dehradun": "Dehradun",
    # International (common)
    "new york": "New York",
    "los angeles": "Los Angeles",
    "san francisco": "San Francisco",
    "london": "London",
    "dubai": "Dubai",
    "singapore": "Singapore",
    "sydney": "Sydney",
    "melbourne": "Melbourne",
    "toronto": "Toronto",
    "vancouver": "Vancouver",
}

# Nearby cities for expansion search
_NEARBY_CITIES: dict[str, list[str]] = {
    "Patna": ["Hajipur", "Gaya", "Nalanda", "Mokama", "Bihar Sharif", "Ara", "Chhapra", "Muzaffarpur", "Samastipur", "Darbhanga"],
    "Delhi": ["Gurgaon", "Noida", "Ghaziabad", "Faridabad", "Bahadurgarh", "Karnal", "Panipat", "Sonipat", "Rohtak"],
    "Mumbai": ["Thane", "Navi Mumbai", "Kalyan", "Vasai", "Virar", "Palghar", "Bhiwandi", "Ulhasnagar"],
    "Bangalore": ["Whitefield", "Electronic City", "Hosur", "Kolar", "Tumkur", "Chikkaballapur", "Mandya", "Mysore"],
    "Chennai": ["Tambaram", "Avadi", "Kanchipuram", "Tiruvallur", "Sriperumbudur", "Pondicherry", "Vellore"],
    "Kolkata": ["Howrah", "Durgapur", "Asansol", "Siliguri", "Burdwan", "Kharagpur", "Haldia"],
    "Hyderabad": ["Secunderabad", "Cyberabad", "Medchal", "Sangareddy", "Vikarabad", "Nalgonda", "Warangal"],
    "Pune": ["Pimpri-Chinchwad", "Lonavala", "Khandala", "Satara", "Sangli", "Kolhapur", "Ahmednagar"],
    "Ahmedabad": ["Gandhinagar", "Vadodara", "Surat", "Rajkot", "Bhavnagar", "Jamnagar", "Junagadh"],
    "Jaipur": ["Ajmer", "Kota", "Udaipur", "Bikaner", "Jodhpur", "Alwar", "Bharatpur"],
    "Lucknow": ["Kanpur", "Agra", "Allahabad", "Varanasi", "Gorakhpur", "Bareilly", "Aligarh"],
    "Noida": ["Delhi", "Gurgaon", "Ghaziabad", "Faridabad", "Meerut", "Modinagar", "Hapur"],
    # Add more as needed
}


def _suggest_location(entered: str) -> tuple[str, str | None]:
    """
    Return (best_guess_location, message_or_none).
    If we have a known correction (e.g. noda -> Noida), return it and a short message.
    Otherwise return entered (title-cased) and None.
    """
    if not entered or not entered.strip():
        return entered, None
    raw = entered.strip()
    key = raw.lower()
    if key in _LOCATION_GUESS:
        canonical = _LOCATION_GUESS[key]
        if canonical != raw:
            return canonical, f"Did you mean '{canonical}'?"
        return canonical, None
    # Title-case as mild normalization; no correction message
    return raw.title(), None


def _ask_number_of_leads(default: int = DEFAULT_LEADS) -> int:
    """Ask user how many leads they want; must be between MIN_LEADS and MAX_LEADS."""
    while True:
        raw = input(
            f"How many leads do you want? ({MIN_LEADS}-{MAX_LEADS}, default {default}): "
        ).strip()
        if not raw:
            return max(MIN_LEADS, min(MAX_LEADS, default))
        try:
            n = int(raw)
            if n < MIN_LEADS:
                print(f"Minimum is {MIN_LEADS}. Please enter between {MIN_LEADS} and {MAX_LEADS}.")
                continue
            if n > MAX_LEADS:
                print(f"Maximum is {MAX_LEADS}. Please enter between {MIN_LEADS} and {MAX_LEADS}.")
                continue
            return n
        except ValueError:
            print("Please enter a valid number.")


def _verify_location_profession(profession: str, location: str) -> tuple[str, str]:
    """
    Suggest best-guess location (e.g. noda -> Noida), show what will be scraped,
    and ask for confirmation. If user does not verify, prompt to re-enter until verified.
    """
    while True:
        suggested_location, correction_msg = _suggest_location(location)
        print(f"\n  Profession: {profession}")
        print(f"  Location:  {suggested_location}")
        if correction_msg:
            print(f"  -> {correction_msg}")
        print(f"\n  We'll scrape data for: \"{profession}\" in \"{suggested_location}\".")
        confirm = input("Proceed? (y/n): ").strip().lower()
        if confirm in ("y", "yes"):
            return profession, suggested_location
        if confirm in ("n", "no"):
            profession = input("Enter profession again (e.g. Gyms): ").strip() or profession
            location = input("Enter location again (e.g. Noida): ").strip() or location
        else:
            print("Please answer 'y' or 'n'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Google Maps results to CSV (name + phone).")
    parser.add_argument("--query", help="Full search query, e.g. 'Gyms in Noida'")
    parser.add_argument("--profession", help="Profession, e.g. 'Gyms'")
    parser.add_argument("--location", help="Location/city, e.g. 'Noida'")
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help=f"Max number of leads to export ({MIN_LEADS}-{MAX_LEADS}; if omitted, you will be prompted)",
    )
    parser.add_argument("--out", help="Output CSV path (defaults to '<profession>_<location>.csv')")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless (default is headed for stability)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip location/profession verification prompt",
    )
    args = parser.parse_args()

    # Build query either from --query or from profession + location (or prompt the user).
    if args.query:
        query = args.query.strip()
        profession = None
        location = None
    else:
        profession = (args.profession or input("Enter profession (e.g. Gyms): ")).strip() or "Gyms"
        location = (args.location or input("Enter location (e.g. Noida): ")).strip() or "Noida"
        if not args.no_verify:
            profession, location = _verify_location_profession(profession, location)
        query = f"{profession} in {location}"

    # Number of leads: use --max if set (clamped to range), otherwise ask (or default when non-interactive).
    if args.max is not None:
        max_places = max(MIN_LEADS, min(MAX_LEADS, args.max))
    else:
        try:
            max_places = _ask_number_of_leads(DEFAULT_LEADS)
        except EOFError:
            max_places = DEFAULT_LEADS  # non-interactive (e.g. piped input)

    # Default CSV name if not provided.
    if args.out:
        out_path = args.out
    else:
        if profession and location:
            safe_prof = profession.replace(" ", "_").lower()
            safe_loc = location.replace(" ", "_").lower()
            out_path = f"{safe_prof}_{safe_loc}.csv"
        else:
            out_path = "results.csv"

    try:
        count = scrape_google_maps(
            query=query,
            max_places=max_places,
            output_csv=out_path,
            headless=args.headless,
            progress_callback=None  # CLI doesn't need progress callbacks
        )
        print(f"Saved {count} rows -> {out_path}")
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

