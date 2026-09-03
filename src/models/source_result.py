from typing import Optional
from pydantic import BaseModel

class SourceResult(BaseModel):
    """Raw result collected directly from a source adapter."""
    source_name: str
    source_url: str
    source_id: Optional[str] = None
    
    business_name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    
    address: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    
    category: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
