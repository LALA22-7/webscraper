import re
from typing import List, Set
from urllib.parse import urljoin, urlparse
from src.models.email import Email, EmailConfidence

class EmailExtractor:
    """Extracts and validates emails from text/HTML."""
    
    # Standard email regex
    EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    
    # Obvious false positives to filter out
    FALSE_POSITIVES = {
        'example@example.com',
        'test@test.com',
        'email@email.com',
        'your@email.com',
        'name@domain.com',
        'sentry@',
        'no-reply@',
        'noreply@',
        'mailer@'
    }
    
    def extract_from_text(self, text: str, source_url: str, method: str = "text") -> List[Email]:
        if not text:
            return []
            
        found_emails = set(self.EMAIL_PATTERN.findall(text))
        valid_emails = []
        
        for email_str in found_emails:
            email_str = email_str.lower().strip()
            
            # Basic validation
            if not self._is_valid(email_str):
                continue
                
            # Assign confidence
            confidence = EmailConfidence.HIGH if method == "mailto" else EmailConfidence.MEDIUM
            
            valid_emails.append(Email(
                email=email_str,
                source_url=source_url,
                discovery_method=method,
                confidence=confidence
            ))
            
        return valid_emails
        
    def _is_valid(self, email: str) -> bool:
        """Filter out obvious false positives, image files mistakenly matched, etc."""
        if len(email) > 100:
            return False
            
        # Filter image extensions that look like domains if a dot is missed
        if email.endswith('.png') or email.endswith('.jpg') or email.endswith('.jpeg') or email.endswith('.gif'):
            return False
            
        for fp in self.FALSE_POSITIVES:
            if fp in email:
                return False
                
        return True
