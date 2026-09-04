import asyncio
from typing import Tuple, Set, Optional

class QueryScheduler:
    """Schedules, queues, and tracks search queries to ensure continuous discovery without duplication."""
    
    def __init__(self, query_expander):
        self.query_expander = query_expander
        self.queue = asyncio.Queue()
        self.completed_queries: Set[Tuple[str, str, str]] = set() # (source, query, location)
        self.pending_queries: Set[Tuple[str, str, str]] = set()
        
    async def initialize(self, base_query: str, base_location: str, sources: list[str]):
        """Generate initial combinations and seed the queue."""
        combinations = self.query_expander.generate_combinations(base_query, base_location)
        for q, loc in combinations:
            for source in sources:
                await self.add_query(source, q, loc)
                
    async def add_query(self, source: str, query: str, location: str):
        """Add a query to the queue if it hasn't been completed or already queued."""
        query_key = (source, query, location)
        if query_key not in self.completed_queries and query_key not in self.pending_queries:
            self.pending_queries.add(query_key)
            await self.queue.put(query_key)
            
    async def get_next(self) -> Optional[Tuple[str, str, str]]:
        """Get the next query from the queue."""
        try:
            return await self.queue.get()
        except asyncio.QueueEmpty:
            return None
            
    def mark_completed(self, source: str, query: str, location: str):
        """Mark a query as completed."""
        query_key = (source, query, location)
        if query_key in self.pending_queries:
            self.pending_queries.remove(query_key)
        self.completed_queries.add(query_key)
        self.queue.task_done()
        
    def mark_failed(self, source: str, query: str, location: str):
        """Mark a query as failed (could be re-queued later if needed)."""
        query_key = (source, query, location)
        if query_key in self.pending_queries:
            self.pending_queries.remove(query_key)
        self.queue.task_done()
        # Optionally re-add to queue or track separately
