import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def normalize_business_name(name: str) -> str:
    """Normalize business name for matching."""
    if not name:
        return ""
    # Lowercase, strip, remove non-alphanumeric except spaces
    clean_name = name.lower().strip()
    clean_name = re.sub(r'[^a-z0-9\s]', '', clean_name)
    # Remove common suffixes that might vary
    suffixes = [r'\bpvt\b', r'\bprivate\b', r'\bltd\b', r'\blimited\b', r'\bllp\b', r'\binc\b', r'\bco\b', r'\bcompany\b']
    for suffix in suffixes:
        clean_name = re.sub(suffix, '', clean_name)
    # Collapse multiple spaces
    return re.sub(r'\s+', ' ', clean_name).strip()

def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits only (potentially keeping + for country code)."""
    if not phone:
        return ""
    s = phone.strip()
    # Keep digits, +
    s = re.sub(r"[^\d+]+", "", s)
    return s

def normalize_url(url: str) -> str:
    """Normalize URL by standardizing scheme, www, and removing tracking params."""
    if not url:
        return ""
    try:
        # Prepend http if no scheme
        if not url.startswith('http'):
            url = 'https://' + url
            
        p = urlparse(url)
        netloc = p.netloc.lower()
        
        # Remove www.
        if netloc.startswith("www."):
            netloc = netloc[4:]
            
        # Strip trailing slash from path
        path = p.path
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
            
        # Remove tracking query parameters
        q = dict(parse_qsl(p.query, keep_blank_values=True))
        noisy_params = {"authuser", "hl", "entry", "g_ep", "g_st", "g_mvn", "utm_source", "utm_medium", "utm_campaign"}
        for noisy in noisy_params:
            q.pop(noisy, None)
            
        query = urlencode(q, doseq=True)
        return urlunparse(('https', netloc, path, p.params, query, p.fragment))
    except Exception:
        return url

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    try:
        if not url.startswith('http'):
            url = 'https://' + url
        p = urlparse(url)
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""
