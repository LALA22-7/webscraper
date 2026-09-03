from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Lead(BaseModel):
    id: str = Field(..., description="Unique ID for the lead (typically a UUID or normalized hash)")
    business_name: str
    normalized_name: str
    
    category: Optional[str] = None
    description: Optional[str] = None
    
    address: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    postal_code: Optional[str] = None
    
    phone_numbers: List[str] = Field(default_factory=list)
    website: Optional[str] = None
    domain: Optional[str] = None
    
    # Nested email objects mapped by email address for uniqueness
    emails: Dict[str, 'Email'] = Field(default_factory=dict)
    
    rating: Optional[float] = None
    review_count: Optional[int] = None
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Source provenance
    source_names: List[str] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    
    social_links: Dict[str, str] = Field(default_factory=dict)
    
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    enriched_at: Optional[datetime] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Resolve forward references
from .email import Email
Lead.model_rebuild()
