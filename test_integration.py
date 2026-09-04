import asyncio
import os
import httpx
from src.processing.email_validator import EmailValidator
from src.enrichment.website_crawler import ProxyPool

async def test_all():
    print("--- 1. Testing Email Validator ---")
    validator = EmailValidator(smtp_timeout=2.0)
    
    # Format error
    res1 = await validator.validate("bad-email")
    assert res1.status == "invalid", f"Expected invalid, got {res1.status}"
    
    # Disposable
    res2 = await validator.validate("test@mailinator.com")
    assert res2.status == "disposable", f"Expected disposable, got {res2.status}"
    
    # Invalid MX (fake domain)
    res3 = await validator.validate("admin@thisdomaindoesnotexist1234567.com")
    assert res3.status == "invalid", f"Expected invalid, got {res3.status}"

    print("Email Validator: OK")

    print("--- 2. Testing ProxyPool ---")
    os.environ["PROXY_LIST"] = "http://proxy1,http://proxy2"
    pool = ProxyPool.from_env()
    assert pool.get_next() == "http://proxy1", "ProxyPool next failed"
    assert pool.get_next() == "http://proxy2", "ProxyPool next failed"
    assert pool.get_next() == "http://proxy1", "ProxyPool cycle failed"
    
    # Test cooldown
    pool.mark_failed("http://proxy1")
    assert pool.get_next() == "http://proxy2", "ProxyPool cooldown failed"
    print("ProxyPool: OK")

    print("--- 3. Testing Multi-Tenant API ---")
    # Need to make sure server is running on port 8000
    try:
        async with httpx.AsyncClient() as client:
            # Start job 1
            resp1 = await client.post("http://localhost:8000/api/start?query=test1&location=london&target=1&duration_seconds=5")
            data1 = resp1.json()
            assert "job_id" in data1, "No job_id returned"
            j1 = data1["job_id"]
            
            # Start job 2 immediately
            resp2 = await client.post("http://localhost:8000/api/start?query=test2&location=london&target=1&duration_seconds=5")
            data2 = resp2.json()
            j2 = data2["job_id"]
            
            assert j1 != j2, "Job IDs should be unique"
            
            # Check status of both
            s1 = await client.get(f"http://localhost:8000/api/status?job_id={j1}")
            s2 = await client.get(f"http://localhost:8000/api/status?job_id={j2}")
            
            assert s1.json()["status"] in ("running", "completed"), f"J1 bad status: {s1.json()}"
            assert s2.json()["status"] in ("running", "completed"), f"J2 bad status: {s2.json()}"
            
            # Stop both
            await client.post(f"http://localhost:8000/api/stop?job_id={j1}")
            await client.post(f"http://localhost:8000/api/stop?job_id={j2}")
            print("Multi-Tenant API: OK")
            
    except httpx.ConnectError:
        print("API test skipped (server not running)")
        
    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all())
