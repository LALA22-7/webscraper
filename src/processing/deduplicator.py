import hashlib
from typing import List, Dict, Optional
from src.models.lead import Lead
from src.models.source_result import SourceResult
from src.processing.normalizer import normalize_business_name, normalize_phone, extract_domain

class Deduplicator:
    def __init__(self):
        # In-memory indexes for fast resolution
        self.phone_index: Dict[str, str] = {} # phone -> lead_id
        self.domain_index: Dict[str, str] = {} # domain -> lead_id
        self.name_location_index: Dict[str, str] = {} # name_loc_hash -> lead_id
        self.leads: Dict[str, Lead] = {}

    def _generate_name_loc_hash(self, normalized_name: str, city: Optional[str]) -> str:
        loc = (city or "").strip().lower()
        combined = f"{normalized_name}_{loc}"
        return hashlib.md5(combined.encode()).hexdigest()

    def find_match(self, result: SourceResult) -> Optional[Lead]:
        normalized_name = normalize_business_name(result.business_name)
        phone = normalize_phone(result.phone) if result.phone else None
        domain = extract_domain(result.website) if result.website else None
        
        # 1. Very strong match: Phone number
        if phone and phone in self.phone_index:
            lead_id = self.phone_index[phone]
            return self.leads[lead_id]
            
        # 2. Strong match: Domain + similar name
        # We assume if the domain matches, it's highly likely the same business
        if domain and domain in self.domain_index:
            lead_id = self.domain_index[domain]
            return self.leads[lead_id]
            
        # 3. Strong match: Exact normalized name + same city
        name_loc_hash = self._generate_name_loc_hash(normalized_name, result.city)
        if name_loc_hash in self.name_location_index:
            lead_id = self.name_location_index[name_loc_hash]
            return self.leads[lead_id]
            
        return None
        
    def add_lead(self, lead: Lead) -> None:
        self.leads[lead.id] = lead
        
        for phone in lead.phone_numbers:
            norm_phone = normalize_phone(phone)
            if norm_phone:
                self.phone_index[norm_phone] = lead.id
                
        if lead.domain:
            self.domain_index[lead.domain] = lead.id
            
        name_loc_hash = self._generate_name_loc_hash(lead.normalized_name, lead.city)
        self.name_location_index[name_loc_hash] = lead.id

    def merge_result(self, existing_lead: Lead, result: SourceResult) -> Lead:
        """Merge a new source result into an existing lead."""
        # Update missing fields
        if not existing_lead.website and result.website:
            existing_lead.website = result.website
            existing_lead.domain = extract_domain(result.website)
            if existing_lead.domain:
                self.domain_index[existing_lead.domain] = existing_lead.id
                
        if result.phone:
            norm_phone = normalize_phone(result.phone)
            if norm_phone and result.phone not in existing_lead.phone_numbers:
                existing_lead.phone_numbers.append(result.phone)
                self.phone_index[norm_phone] = existing_lead.id
                
        if not existing_lead.address and result.address:
            existing_lead.address = result.address
        if not existing_lead.locality and result.locality:
            existing_lead.locality = result.locality
        if not existing_lead.city and result.city:
            existing_lead.city = result.city
        if not existing_lead.category and result.category:
            existing_lead.category = result.category
            
        if not existing_lead.latitude and result.latitude:
            existing_lead.latitude = result.latitude
            existing_lead.longitude = result.longitude
            
        # Merge provenance
        if result.source_name not in existing_lead.source_names:
            existing_lead.source_names.append(result.source_name)
        if result.source_url not in existing_lead.source_urls:
            existing_lead.source_urls.append(result.source_url)
        if result.source_id and result.source_id not in existing_lead.source_ids:
            existing_lead.source_ids.append(result.source_id)
            
        return existing_lead
