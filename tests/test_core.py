import pytest
from src.processing.normalizer import normalize_business_name, normalize_phone, extract_domain
from src.processing.deduplicator import Deduplicator
from src.processing.query_expander import QueryExpander
from src.models.source_result import SourceResult
from src.models.lead import Lead

def test_normalize_business_name():
    assert normalize_business_name("  ABC Fitness Gym  ") == "abc fitness gym"
    assert normalize_business_name("A.B.C. Fitness") == "abc fitness"

def test_normalize_phone():
    assert normalize_phone("+91-9876543210") == "+919876543210"
    assert normalize_phone("098765 43210") == "09876543210"

def test_extract_domain():
    assert extract_domain("https://www.abcfitness.in/about") == "abcfitness.in"
    assert extract_domain("http://abcfitness.in") == "abcfitness.in"

def test_deduplicator():
    dedup = Deduplicator()
    
    r1 = SourceResult(source_name="Justdial", source_url="http://jd.com", business_name="ABC Fitness", phone="+919876543210", city="Noida")
    r2 = SourceResult(source_name="Google", source_url="http://g.com", business_name="ABC Fitness Gym", phone="+919876543210", city="Noida")
    r3 = SourceResult(source_name="Sulekha", source_url="http://s.com", business_name="XYZ Gym", phone="+918888888888", city="Delhi")
    
    # Emulate orchestrator logic
    dedup.add_lead(Lead(
        id="1", business_name=r1.business_name, normalized_name=normalize_business_name(r1.business_name),
        phone_numbers=[r1.phone]
    ))
    
    match = dedup.find_match(r2)
    assert match is not None
    
    match2 = dedup.find_match(r3)
    assert match2 is None

def test_query_expander():
    expansions = QueryExpander.expand_query("gym")
    assert "fitness center" in expansions
    
    combinations = QueryExpander.generate_combinations("gym", "noida")
    assert ("fitness center", "Noida Sector 18") in combinations
