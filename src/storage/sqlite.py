import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime
from src.models.lead import Lead
from src.models.job import Job
from src.models.email import Email, EmailConfidence

class SQLiteManager:
    def __init__(self, db_path: str = "leads.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create Jobs table
            cursor.execute('''
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
            cursor.execute('''
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id TEXT,
                    email TEXT,
                    source_url TEXT,
                    discovery_method TEXT,
                    confidence TEXT,
                    UNIQUE(lead_id, email),
                    FOREIGN KEY(lead_id) REFERENCES leads(id)
                )
            ''')
            
            # Create Phones table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS phones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id TEXT,
                    phone TEXT,
                    UNIQUE(lead_id, phone),
                    FOREIGN KEY(lead_id) REFERENCES leads(id)
                )
            ''')
            
            conn.commit()

    def save_job(self, job: Job):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO jobs (
                    id, query, location, target, sources, discovered_count, 
                    enriched_count, email_count, status, source_statuses, 
                    started_at, updated_at, finished_at, errors
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job.id, job.query, job.location, job.target, 
                json.dumps(job.sources), job.discovered_count,
                job.enriched_count, job.email_count, job.status,
                json.dumps(job.source_statuses), job.started_at.isoformat() if job.started_at else None,
                datetime.utcnow().isoformat(),
                job.finished_at.isoformat() if job.finished_at else None,
                json.dumps(job.errors)
            ))
            conn.commit()

    def save_lead(self, lead: Lead, job_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Save main lead
            cursor.execute('''
                INSERT OR REPLACE INTO leads (
                    id, business_name, normalized_name, category, description,
                    address, locality, city, state, country, postal_code,
                    website, domain, rating, review_count, latitude, longitude,
                    source_names, source_urls, discovered_at, enriched_at, job_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                lead.id, lead.business_name, lead.normalized_name, lead.category, lead.description,
                lead.address, lead.locality, lead.city, lead.state, lead.country, lead.postal_code,
                lead.website, lead.domain, lead.rating, lead.review_count, lead.latitude, lead.longitude,
                json.dumps(lead.source_names), json.dumps(lead.source_urls),
                lead.discovered_at.isoformat() if lead.discovered_at else None,
                lead.enriched_at.isoformat() if lead.enriched_at else None,
                job_id
            ))
            
            # Save emails
            for email_obj in lead.emails.values():
                cursor.execute('''
                    INSERT OR REPLACE INTO emails (lead_id, email, source_url, discovery_method, confidence)
                    VALUES (?, ?, ?, ?, ?)
                ''', (lead.id, email_obj.email, email_obj.source_url, email_obj.discovery_method, email_obj.confidence.value))
                
            # Save phones
            for phone in lead.phone_numbers:
                cursor.execute('''
                    INSERT OR REPLACE INTO phones (lead_id, phone)
                    VALUES (?, ?)
                ''', (lead.id, phone))
                
            conn.commit()
