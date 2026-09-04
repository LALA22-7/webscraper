import asyncio
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsSyncManager:
    """Synchronizes leads to Google Sheets in continuous batches."""
    
    def __init__(self, spreadsheet_id: str, credentials_path: str = "credentials.json"):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.queue = asyncio.Queue()
        self.batch_size = 50
        
    async def add_to_sync_queue(self, lead):
        """Queue a lead for synchronization."""
        await self.queue.put(lead)
        
    async def start_sync_worker(self, job_id: str, status_obj: dict):
        """Worker that continuously reads from the queue and synchronizes in batches."""
        if not self.spreadsheet_id:
            logger.info("No spreadsheet ID configured. Skipping Google Sheets sync.")
            # Consume queue anyway to prevent memory leak
            while True:
                item = await self.queue.get()
                if item is None:
                    break
                self.queue.task_done()
            return
            
        logger.info(f"Starting Sheets Sync Worker for {self.spreadsheet_id}")
        
        while status_obj.get("status") in ("running", "paused", "internet_disconnected"):
            batch = []
            
            # Try to get batch_size items or wait up to 5 seconds
            for _ in range(self.batch_size):
                try:
                    # Non-blocking check or fast timeout
                    item = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                    if item is None: # Shutdown signal
                        break
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
                    
            if not batch:
                continue
                
            try:
                # Simulate API call batching
                logger.info(f"Synchronizing batch of {len(batch)} records to Google Sheets...")
                # Real implementation would use googleapiclient.discovery.build('sheets', 'v4')
                # and body = {"values": [[lead.id, lead.business_name, ...]]}
                # sheets.spreadsheets().values().append(...)
                
                await asyncio.sleep(1) # Simulate network delay
                
                logger.info("Batch synchronization successful.")
                
            except Exception as e:
                logger.error(f"Google Sheets Sync failed: {e}")
                # Re-queue failed batch
                for item in batch:
                    await self.queue.put(item)
                await asyncio.sleep(10) # Backoff
            finally:
                for _ in batch:
                    self.queue.task_done()
