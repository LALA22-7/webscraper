from enum import Enum
from pydantic import BaseModel

class EmailConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Email(BaseModel):
    email: str
    source_url: str
    discovery_method: str  # e.g., "mailto", "text", "regex"
    confidence: EmailConfidence
