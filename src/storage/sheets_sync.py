"""
Google Sheets Real-time Sync Manager

Streams enriched leads into a Google Sheet as they are discovered.
One row per validated email:
  Business | Website | Email | Email Status | Score | Role-Based | Discovered At | Query | Location

Setup:
1. Create a Google Cloud project
2. Enable Google Sheets API + Google Drive API
3. Create a Service Account, download credentials.json
4. Share your target Google Sheet with the service account email
5. Set env vars:
   GOOGLE_SHEET_ID=your_spreadsheet_id
   GOOGLE_CREDS_PATH=credentials.json  (default)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

HEADERS = [
    "Business Name",
    "Website",
    "Email",
    "Email Status",
    "Validation Score",
    "Role-Based",
    "Discovered At",
    "Query",
    "Location",
    "Job ID",
]


class GoogleSheetsSyncManager:
    """
    Streams validated leads into a Google Sheet in real-time.
    Uses an internal asyncio queue + background worker pattern.
    Batches writes every BATCH_SIZE rows or FLUSH_INTERVAL seconds.
    """

    BATCH_SIZE = 20
    FLUSH_INTERVAL = 5.0  # seconds

    def __init__(self,
                 spreadsheet_id: str,
                 credentials_path: str = "credentials.json",
                 sheet_name: str = "Leads"):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.queue: asyncio.Queue = asyncio.Queue()
        self._worksheet = None
        self._client = None
        self._enabled = bool(spreadsheet_id)

    # ── PUBLIC API ──────────────────────────────────────────────────────────

    async def add_lead(self, business_name: str, website: str,
                       email: str, email_status: str, score: int,
                       is_role_based: bool, query: str, location: str,
                       job_id: str = ""):
        """Queue one email row for writing to Sheets."""
        if not self._enabled:
            return
        row = [
            business_name,
            website,
            email,
            email_status,
            score,
            "Yes" if is_role_based else "No",
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            query,
            location,
            job_id,
        ]
        await self.queue.put(row)

    async def start_sync_worker(self, job_id: str):
        """
        Long-running background task.
        Call as asyncio.create_task(manager.start_sync_worker(job_id)).
        Send None to the queue to stop it.
        """
        if not self._enabled:
            logger.info("[Sheets] No GOOGLE_SHEET_ID set — skipping sync")
            # Drain queue to prevent memory leak
            while True:
                item = await self.queue.get()
                self.queue.task_done()
                if item is None:
                    break
            return

        if not await self._initialize():
            logger.error("[Sheets] Failed to initialize. Sync disabled for this job.")
            return

        logger.info(f"[Sheets] Sync worker started → {self.spreadsheet_id}")
        pending = []

        while True:
            # Wait up to FLUSH_INTERVAL for the next item
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=self.FLUSH_INTERVAL)
                if item is None:
                    # Shutdown signal — flush remaining and exit
                    if pending:
                        await self._write_batch(pending)
                    break
                pending.append(item)
                self.queue.task_done()
            except asyncio.TimeoutError:
                # Nothing came in — flush what we have
                pass

            # Flush if batch is full or on timeout
            if len(pending) >= self.BATCH_SIZE:
                await self._write_batch(pending)
                pending = []

        # Final flush
        if pending:
            await self._write_batch(pending)

        logger.info("[Sheets] Sync worker stopped.")

    async def stop(self):
        """Signal the sync worker to stop after flushing remaining rows."""
        await self.queue.put(None)

    # ── INTERNAL ────────────────────────────────────────────────────────────

    async def _initialize(self) -> bool:
        """Connect to Google Sheets API and ensure header row exists."""
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials

            creds_path = self.credentials_path
            if not os.path.exists(creds_path):
                logger.error(f"[Sheets] credentials.json not found at: {creds_path}")
                return False

            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            loop = asyncio.get_event_loop()

            def _connect():
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_key(self.spreadsheet_id)
                try:
                    ws = sheet.worksheet(self.sheet_name)
                except gspread.WorksheetNotFound:
                    ws = sheet.add_worksheet(title=self.sheet_name, rows=10000, cols=20)
                # Add header row if sheet is empty
                if ws.row_count == 0 or not ws.row_values(1):
                    ws.append_row(HEADERS, value_input_option="USER_ENTERED")
                return ws

            self._worksheet = await loop.run_in_executor(None, _connect)
            return True

        except ImportError:
            logger.error("[Sheets] gspread not installed. Run: pip install gspread oauth2client")
            return False
        except Exception as e:
            logger.error(f"[Sheets] Initialization error: {e}")
            return False

    async def _write_batch(self, rows: list):
        """Append rows to the worksheet."""
        if not rows or not self._worksheet:
            return
        try:
            loop = asyncio.get_event_loop()
            ws = self._worksheet

            def _append():
                ws.append_rows(rows, value_input_option="USER_ENTERED")

            await loop.run_in_executor(None, _append)
            logger.info(f"[Sheets] ✓ Wrote {len(rows)} rows")

        except Exception as e:
            logger.error(f"[Sheets] Write error: {e}")
            # Re-queue failed rows (backoff + retry)
            await asyncio.sleep(10)
            for row in rows:
                await self.queue.put(row)
