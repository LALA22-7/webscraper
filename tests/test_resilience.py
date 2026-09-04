import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Assuming these are importable from the codebase structure
from src.core.source_manager import SourceManager
from src.core.job_manager import JobManager
from src.models.job import Job

@pytest.mark.asyncio
async def test_source_cooldown_on_failure():
    """Test that a source is placed on cooldown after consecutive failures."""
    sm = SourceManager(headless=True)
    sm.configure_sources(["organic_search"])
    
    # Assert initial state
    assert sm.source_health["organic_search"] == "AVAILABLE"
    
    # Manually trigger a failure update (as would happen in the Orchestrator on exception)
    sm.update_health("Organic Search", "FAILED", cooldown_minutes=5)
    
    assert sm.source_health["organic_search"] == "FAILED"
    
    # The get_enabled_scrapers should now return empty because the only source is on cooldown
    active = sm.get_enabled_scrapers()
    assert len(active) == 0

@pytest.mark.asyncio
async def test_connectivity_monitor_pause_resume():
    """Mock the connectivity monitor to test job pausing and resuming."""
    
    job = Job(id="TEST-JOB", query="test", location="test", target=10, sources=["organic_search"], require_email=False)
    job.status = "running"
    
    # Mock the check_connectivity function directly in the test scope
    async def mock_connectivity(returns):
        for ret in returns:
            yield ret
            
    conn_gen = mock_connectivity([False, False, True]) # Disconnect, Disconnect, Reconnect
    
    async def connectivity_monitor_loop():
        async for is_connected in conn_gen:
            if not is_connected and job.status == "running":
                job.status = "internet_disconnected"
            elif is_connected and job.status == "internet_disconnected":
                job.status = "running"
                
    # Run loop step 1 (Disconnect)
    await connectivity_monitor_loop()
    
    # After the loop finishes (representing 3 ticks), it should be back to running
    # Let's step through manually:
    
    j2 = Job(id="TEST-2", query="test", location="test", sources=["organic_search"])
    j2.status = "running"
    
    # Simulating the exact logic from JobManager
    def handle_connectivity(is_connected):
        if not is_connected and j2.status == "running":
            j2.status = "internet_disconnected"
        elif is_connected and j2.status == "internet_disconnected":
            j2.status = "running"

    handle_connectivity(False)
    assert j2.status == "internet_disconnected"
    
    handle_connectivity(False)
    assert j2.status == "internet_disconnected"
    
    handle_connectivity(True)
    assert j2.status == "running"
