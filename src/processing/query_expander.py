from typing import List

class QueryExpander:
    """Expands base queries and locations into multiple variations for broader discovery."""
    
    # Common industry expansions
    EXPANSIONS = {
        "gym": ["gym", "fitness center", "health club", "fitness studio"],
        "gyms": ["gyms", "fitness centers", "health clubs", "fitness studios"],
        "real estate": ["real estate agency", "property dealer", "real estate consultant", "real estate company"],
        "dentist": ["dentist", "dental clinic", "orthodontist"],
        "dentists": ["dentists", "dental clinics"],
    }
    
    # Common location subdivisions
    LOCATIONS = {
        "noida": ["Noida", "Noida Sector 18", "Noida Sector 62", "Noida Sector 63", "Noida Sector 137"],
        "greater noida": ["Greater Noida", "Greater Noida West", "Knowledge Park"],
        "delhi": ["Delhi", "South Delhi", "Connaught Place", "Dwarka"],
    }
    
    @classmethod
    def expand_query(cls, query: str) -> List[str]:
        """Return a list of expanded queries, starting with the original."""
        q_lower = query.lower().strip()
        variations = [query]
        
        # Add predefined expansions if matched
        if q_lower in cls.EXPANSIONS:
            for variant in cls.EXPANSIONS[q_lower]:
                if variant.lower() != q_lower:
                    variations.append(variant)
                    
        return variations
        
    @classmethod
    def expand_location(cls, location: str) -> List[str]:
        """Return a list of expanded locations, starting with the original."""
        l_lower = location.lower().strip()
        variations = [location]
        
        if l_lower in cls.LOCATIONS:
            for variant in cls.LOCATIONS[l_lower]:
                if variant.lower() != l_lower:
                    variations.append(variant)
                    
        return variations
        
    @classmethod
    def generate_combinations(cls, query: str, location: str) -> List[tuple[str, str]]:
        """Return all pairs of (query, location) variants."""
        queries = cls.expand_query(query)
        locations = cls.expand_location(location)
        
        combinations = []
        for loc in locations:
            for q in queries:
                combinations.append((q, loc))
                
        return combinations
