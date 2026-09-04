from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Job(BaseModel):
    id: str
    query: str
    location: str
    target: Optional[int] = None
    duration_seconds: Optional[int] = None
    sources: List[str]
    
    discovered_count: int = 0
    enriched_count: int = 0
    email_count: int = 0
    total_websites_crawled: int = 0
    
    require_email: bool = False
    
    status: str = "running" # running, paused, completed, failed
    source_statuses: dict[str, str] = Field(default_factory=dict)
    
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    
    errors: List[str] = Field(default_factory=list)
