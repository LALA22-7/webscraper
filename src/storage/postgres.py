import json
import asyncpg
from typing import List, Dict, Optional
from datetime import datetime
from src.models.lead import Lead
from src.models.job import Job
from src.models.email import Email, EmailConfidence
import logging

logger = logging.getLogger(__name__)

class PostgresManager:
    """High-concurrency PostgreSQL Database Manager using asyncpg."""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Initialize the connection pool and database schema."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.dsn, min_size=5, max_size=50)
            await self._init_db()
            logger.info("PostgreSQL connection pool initialized.")
            
    async def disconnect(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            
    async def _init_db(self):
        async with self.pool.acquire() as conn:
            # Create Jobs table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    query TEXT,
                    location TEXT,
                    target INTEGER,
                    sources TEXT,
                    discovered_count INTEGER,
                    enriched_count INTEGER,
                    email_count INTEGER,
                    status TEXT,
                    source_statuses TEXT,
                    started_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    errors TEXT
                )
            ''')
            
            # Create Leads table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    business_name TEXT,
                    normalized_name TEXT,
                    category TEXT,
                    description TEXT,
                    address TEXT,
                    locality TEXT,
                    city TEXT,
                    state TEXT,
                    country TEXT,
                    postal_code TEXT,
                    website TEXT,
                    domain TEXT,
                    rating REAL,
                    review_count INTEGER,
                    latitude REAL,
                    longitude REAL,
                    source_names TEXT,
                    source_urls TEXT,
                    discovered_at TIMESTAMP,
                    enriched_at TIMESTAMP,
                    job_id TEXT
                )
            ''')
            
            # Create Emails table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS emails (
                    id SERIAL PRIMARY KEY,
                    lead_id TEXT,
                    email TEXT,
                    source_url TEXT,
                    discovery_method TEXT,
                    confidence TEXT,
                    UNIQUE(lead_id, email),
                    FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
                )
            ''')
            
            # Create Phones table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS phones (
                    id SERIAL PRIMARY KEY,
                    lead_id TEXT,
                    phone TEXT,
                    UNIQUE(lead_id, phone),
                    FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_leads_normalized_name ON leads(normalized_name)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_emails_email ON emails(email)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_phones_phone ON phones(phone)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_leads_job_id ON leads(job_id)')

    async def save_job(self, job: Job):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO jobs (
                    id, query, location, target, sources, discovered_count, 
                    enriched_count, email_count, status, source_statuses, 
                    started_at, updated_at, finished_at, errors
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (id) DO UPDATE SET
                    query = EXCLUDED.query,
                    location = EXCLUDED.location,
                    target = EXCLUDED.target,
                    sources = EXCLUDED.sources,
                    discovered_count = EXCLUDED.discovered_count,
                    enriched_count = EXCLUDED.enriched_count,
                    email_count = EXCLUDED.email_count,
                    status = EXCLUDED.status,
                    source_statuses = EXCLUDED.source_statuses,
                    updated_at = EXCLUDED.updated_at,
                    finished_at = EXCLUDED.finished_at,
                    errors = EXCLUDED.errors
            ''', 
                job.id, job.query, job.location, job.target, 
                json.dumps(job.sources), job.discovered_count,
                job.enriched_count, job.email_count, job.status,
                json.dumps(job.source_statuses), 
                job.started_at,
                datetime.utcnow(),
                job.finished_at,
                json.dumps(job.errors)
            )

    async def save_lead(self, lead: Lead, job_id: str):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Save main lead
                await conn.execute('''
                    INSERT INTO leads (
                        id, business_name, normalized_name, category, description,
                        address, locality, city, state, country, postal_code,
                        website, domain, rating, review_count, latitude, longitude,
                        source_names, source_urls, discovered_at, enriched_at, job_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
                    ON CONFLICT (id) DO UPDATE SET
                        business_name = EXCLUDED.business_name,
                        category = EXCLUDED.category,
                        description = EXCLUDED.description,
                        address = EXCLUDED.address,
                        locality = EXCLUDED.locality,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        country = EXCLUDED.country,
                        postal_code = EXCLUDED.postal_code,
                        website = EXCLUDED.website,
                        domain = EXCLUDED.domain,
                        rating = EXCLUDED.rating,
                        review_count = EXCLUDED.review_count,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        source_names = EXCLUDED.source_names,
                        source_urls = EXCLUDED.source_urls,
                        enriched_at = EXCLUDED.enriched_at
                ''', 
                    lead.id, lead.business_name, lead.normalized_name, lead.category, lead.description,
                    lead.address, lead.locality, lead.city, lead.state, lead.country, lead.postal_code,
                    lead.website, lead.domain, lead.rating, lead.review_count, lead.latitude, lead.longitude,
                    json.dumps(lead.source_names), json.dumps(lead.source_urls),
                    lead.discovered_at,
                    lead.enriched_at,
                    job_id
                )
                
                # Save emails
                if lead.emails:
                    email_records = [
                        (lead.id, email_obj.email, email_obj.source_url, email_obj.discovery_method, email_obj.confidence.value)
                        for email_obj in lead.emails.values()
                    ]
                    await conn.executemany('''
                        INSERT INTO emails (lead_id, email, source_url, discovery_method, confidence)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (lead_id, email) DO NOTHING
                    ''', email_records)
                    
                # Save phones
                if lead.phone_numbers:
                    phone_records = [(lead.id, phone) for phone in lead.phone_numbers]
                    await conn.executemany('''
                        INSERT INTO phones (lead_id, phone)
                        VALUES ($1, $2)
                        ON CONFLICT (lead_id, phone) DO NOTHING
                    ''', phone_records)

    async def deduplicate_leads(self, job_id: str):
        """Perform a final deduplication pass in the database based on domain."""
        async with self.pool.acquire() as conn:
            # Find domains with multiple leads
            duplicates = await conn.fetch('''
                SELECT domain, MIN(id) as keep_id, STRING_AGG(id, ',') as all_ids
                FROM leads
                WHERE job_id = $1 AND domain IS NOT NULL AND domain != ''
                GROUP BY domain
                HAVING COUNT(id) > 1
            ''', job_id)
            
            for record in duplicates:
                domain = record['domain']
                keep_id = record['keep_id']
                all_ids = record['all_ids']
                
                ids_to_remove = [id for id in all_ids.split(',') if id != keep_id]
                
                if not ids_to_remove:
                    continue
                    
                async with conn.transaction():
                    # Re-assign emails and phones to the kept lead before deleting
                    await conn.execute("UPDATE emails SET lead_id = $1 WHERE lead_id = ANY($2::text[])", keep_id, ids_to_remove)
                    await conn.execute("UPDATE phones SET lead_id = $1 WHERE lead_id = ANY($2::text[])", keep_id, ids_to_remove)
                    
                    # Delete duplicate leads
                    await conn.execute("DELETE FROM leads WHERE id = ANY($1::text[])", ids_to_remove)
