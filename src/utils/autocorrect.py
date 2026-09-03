import httpx
from urllib.parse import quote_plus

def autocorrect(text: str) -> str:
    """
    Uses Google Suggest API to attempt to autocorrect typos.
    If no obvious correction is found, returns the original text.
    """
    if not text:
        return text
        
    try:
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote_plus(text)}"
        resp = httpx.get(url, timeout=5.0)
        
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1 and data[1]:
                suggestions = data[1]
                best_match = suggestions[0]
                
                # If the first suggestion is a single word or matches word count, use it.
                if len(best_match.split()) <= len(text.split()) + 1:
                    return best_match.title()
                    
    except httpx.RequestError:
        pass
        
    return text.title()
