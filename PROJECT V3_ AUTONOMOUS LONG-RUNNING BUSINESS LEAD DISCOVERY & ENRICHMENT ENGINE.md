# PROJECT V3: AUTONOMOUS LONG-RUNNING BUSINESS LEAD DISCOVERY & ENRICHMENT ENGINE

## ROLE

You are a senior software architect and engineer specializing in:

- Python
- asynchronous systems
- browser automation
- web crawling
- search-driven discovery
- ETL pipelines
- lead generation systems
- entity resolution
- data enrichment
- Google Sheets integration
- fault-tolerant long-running jobs
- resumable pipelines
- web UI development
- observability
- production systems

You are working on an EXISTING business lead scraping/discovery repository.

This is a major V3 evolution.

DO NOT throw away working components without first understanding them.

The existing system already contains functionality for business discovery, Google Maps/Justdial extraction, auto-scrolling, deduplication, website enrichment, and email extraction.

The new objective is to transform it into a:

> LONG-RUNNING, AUTONOMOUS, SEARCH-DRIVEN BUSINESS LEAD DISCOVERY AND WEBSITE ENRICHMENT PLATFORM.

---

# 1. NEW PRODUCT OBJECTIVE

The application should no longer primarily operate around:

    "Give me 300 businesses."

Instead, it should operate around:

    QUERY
    REGION
    RUN DURATION
    SOURCES
    OUTPUT

Example:

    Query:
        restaurants

    Region:
        Switzerland

    Duration:
        10 hours

The system should continuously discover relevant businesses throughout the specified region for the duration of the run.

The system should continue discovering new businesses until:

- the user manually stops it,
- the configured duration expires,
- the system reaches a configured optional maximum,
- or all configured discovery strategies are temporarily exhausted.

The system must NOT stop simply because one source has stopped producing results.

---

# 2. PRIMARY PRODUCT BEHAVIOR

Example user request:

    restaurants
    Switzerland
    10 hours

The system should:

1. Interpret the query.
2. Generate relevant search variations.
3. Generate location-aware variations.
4. Search multiple discovery sources.
5. Discover business listings and business websites.
6. Follow relevant publicly accessible business websites.
7. Extract business information.
8. Extract publicly available business emails.
9. Normalize all information.
10. Deduplicate businesses.
11. Deduplicate emails.
12. Score data quality.
13. Immediately persist results.
14. Stream results to Google Sheets.
15. Continue discovering additional businesses.
16. Recover from temporary internet failures.
17. Resume automatically after connectivity returns.
18. Recover from process/browser failures where possible.
19. Detect blocked/CAPTCHA pages.
20. Isolate affected sources.
21. Continue using other available sources.
22. Continue until the run duration expires or the user stops it.

---

# 3. VERY IMPORTANT: DO NOT MAKE ONE WEBSITE THE CORE

The system must NOT be architected as:

    Google Maps → leads

or:

    Google Search → leads

Instead:

    QUERY
       ↓
    QUERY EXPANSION
       ↓
    DISCOVERY ORCHESTRATOR
       ↓
    MULTIPLE DISCOVERY SOURCES
       ↓
    SEARCH RESULTS
       ↓
    BUSINESS/DIRECTORY PAGES
       ↓
    BUSINESS WEBSITES
       ↓
    NORMALIZATION
       ↓
    DEDUPLICATION
       ↓
    ENRICHMENT
       ↓
    EMAIL EXTRACTION
       ↓
    QUALITY SCORING
       ↓
    DATABASE
       ↓
    GOOGLE SHEETS
       ↓
    WEB UI

---

# 4. SEARCH-DRIVEN DISCOVERY

The new system should heavily use search-driven discovery.

The objective is NOT simply to scrape one search-results page.

Instead, the application should continuously generate and execute different relevant searches.

For:

    restaurants in Switzerland

generate appropriate variations such as:

    restaurants Switzerland
    restaurants Zurich
    restaurants Geneva
    restaurants Basel
    restaurants Bern
    restaurants Lausanne

and other relevant regional/local variations.

Also use query variations such as:

    restaurants
    fine dining restaurants
    family restaurants
    Italian restaurants
    Indian restaurants
    Japanese restaurants
    vegetarian restaurants
    cafes
    bistros
    brasseries

ONLY generate variations that remain relevant to the user's original intent.

Do not generate random unrelated keywords.

---

# 5. QUERY GENERATION ENGINE

Create a dedicated:

    QueryExpansionEngine

Input:

    original_query
    region

Output:

    search_queries[]

The engine should support:

### Keyword expansion

Example:

    restaurant

→

    restaurants
    dining restaurant
    food restaurant
    local restaurant
    fine dining
    family restaurant

### Industry/category expansion

Use a configurable category vocabulary.

### Geographic expansion

Break large regions into relevant locations.

For Switzerland, potentially:

    Zurich
    Geneva
    Basel
    Bern
    Lausanne
    Lucerne
    St. Gallen
    Lugano
    Winterthur

and relevant smaller localities.

Do not hard-code one country.

The architecture must support:

    Switzerland
    India
    United States
    United Kingdom
    etc.

---

# 6. SEARCH QUERY SCHEDULER

Do not execute all queries once and stop.

Create a query scheduler.

Conceptually:

    Query Queue

        ↓

    restaurants Switzerland
    restaurants Zurich
    restaurants Geneva
    restaurants Basel
    Italian restaurants Zurich
    Indian restaurants Geneva
    vegetarian restaurants Basel
    ...

        ↓

    Search workers

        ↓

    Results

The scheduler should:

- avoid duplicate queries
- track completed queries
- track partially completed queries
- prioritize unexplored locations
- prioritize high-value variations
- continuously generate new queries where appropriate
- persist query state

---

# 7. CONTINUOUS DISCOVERY MODE

The core system must support:

    --duration 10h

or equivalent.

Examples:

    --duration 1h
    --duration 6h
    --duration 10h
    --duration 24h

The job should remain active for the requested duration.

It should continuously:

    discover
    enrich
    deduplicate
    persist
    discover more

until the duration expires.

---

# 8. MANUAL STOP

The user must be able to stop the job from the UI.

Example:

    [ STOP JOB ]

When stopped:

1. Finish currently safe persistence operations.
2. Flush pending Google Sheets writes.
3. Save checkpoint.
4. Close browser resources.
5. Mark job as STOPPED.
6. Preserve all collected data.

Do not lose already collected records.

---

# 9. JOB STATES

Implement:

    CREATED
    STARTING
    RUNNING
    PAUSED
    INTERNET_DISCONNECTED
    RECOVERING
    DEGRADED
    STOPPING
    STOPPED
    COMPLETED
    FAILED

The UI should display the current state.

---

# 10. LONG-RUNNING JOB ARCHITECTURE

The application must be designed for:

    1 hour
    6 hours
    10 hours
    24 hours

Do NOT assume the process will only run for a few minutes.

Implement:

- periodic checkpointing
- memory control
- browser lifecycle management
- worker health monitoring
- persistent queues
- incremental database writes
- Google Sheets batching
- automatic recovery
- structured logging

---

# 11. INTERNET FAILURE HANDLING

This is a mandatory feature.

Detect:

- internet disconnection
- DNS failure
- connection timeout
- connection reset
- network unreachable
- repeated connection failures

When internet connectivity disappears:

    RUNNING
       ↓
    INTERNET_DISCONNECTED
       ↓
    save checkpoint
       ↓
    pause network workers
       ↓
    wait
       ↓
    connectivity restored
       ↓
    RECOVERING
       ↓
    resume from checkpoint
       ↓
    RUNNING

Do NOT restart the entire job.

Do NOT lose collected records.

---

# 12. CONNECTIVITY MONITOR

Create a dedicated ConnectivityMonitor.

It should periodically test connectivity using lightweight health checks.

Do not continuously make expensive external requests.

When connectivity fails:

    pause discovery
    pause enrichment
    preserve state

When connectivity returns:

    resume workers

The system should use backoff rather than hammering the network while disconnected.

---

# 13. RESUMABILITY

Every job must have a persistent Job ID.

Example:

    JOB-20260904-0001

Persist:

    job_id
    query
    region
    start_time
    end_time
    duration
    status

    query_queue
    completed_queries

    discovered_businesses
    enriched_businesses
    email_count

    source_status
    checkpoints
    errors
    warnings

If the application crashes:

    restart application

and resume the active job.

---

# 14. CRASH RECOVERY

The system should recover from:

- browser crash
- worker crash
- application crash
- temporary network failure
- database interruption
- Google Sheets API failure
- source failure

Already persisted records must never be lost.

Use idempotent writes.

---

# 15. GOOGLE SHEETS AS LIVE OUTPUT

Google Sheets is a PRIMARY OUTPUT, not merely a final export.

The user should be able to provide a Google Sheets destination.

The system should continuously append/update results as they are discovered.

Example:

    Lead discovered
       ↓
    Normalize
       ↓
    Deduplicate
       ↓
    Save SQLite
       ↓
    Queue Sheets write
       ↓
    Batch write to Google Sheets

Do NOT perform one API request per lead if batching can be used.

Use efficient batching.

---

# 16. GOOGLE SHEETS FAILURE

If Google Sheets becomes unavailable:

    continue scraping
    save to local SQLite
    queue pending Sheets writes
    retry later
    synchronize when Sheets becomes available

Google Sheets failure must NEVER stop the scraper.

The local database is the source of truth.

Google Sheets is a synchronized output.

---

# 17. GOOGLE SHEETS SYNCHRONIZATION

Create:

    GoogleSheetsSyncManager

Responsibilities:

- authentication
- sheet validation
- header creation
- batch writes
- retry
- deduplication
- synchronization state
- failed-write queue
- recovery

Store:

    last_synced_record
    pending_records
    last_sync_time
    sync_errors

Use idempotent identifiers so records are not duplicated when retrying.

---

# 18. SHEET STRUCTURE

Create columns such as:

    Lead ID
    Business Name
    Category
    Address
    City
    Region
    Country
    Phone
    Website
    Email
    Email Source
    Email Confidence
    Source
    Source URL
    Rating
    Review Count
    Social Links
    Lead Quality
    First Discovered
    Last Updated

Additional columns can be added where useful.

---

# 19. LIVE UI

Create a simple web UI.

It should be intentionally simple.

Do NOT build an unnecessarily complex frontend.

Required fields:

### Business Query

Example:

    [ restaurants ]

### Region

Example:

    [ Switzerland ]

### Duration

Example:

    [ 10 hours ]

### Google Sheets

Allow the user to provide/configure the destination sheet.

### Start

    [ START ]

### Stop

    [ STOP ]

---

# 20. LIVE DASHBOARD

While the scraper runs, display:

    Query:
        restaurants

    Region:
        Switzerland

    Runtime:
        04:37:21

    Remaining:
        05:22:39

    Status:
        RUNNING

    ─────────────────────────────

    Businesses discovered:
        12,847

    Unique businesses:
        11,932

    Websites found:
        9,842

    Emails found:
        7,613

    Google Sheets rows:
        7,421

    Queries completed:
        843

    Queries remaining:
        1,294

    Sources active:
        6

    Sources degraded:
        1

---

# 21. LIVE ACTIVITY FEED

Display recent events:

    ✓ Business discovered
      Zurich Restaurant ABC

    ✓ Website found
      example.ch

    ✓ Email found
      info@example.ch

    ✓ Added to Google Sheets

    ⚠ Source temporarily unavailable

    ✓ Internet connection restored

Keep this lightweight.

---

# 22. LIVE COUNTERS

The UI must update continuously.

At minimum:

    Total discovered
    Unique businesses
    Websites found
    Emails found
    Email-qualified leads
    Google Sheets synced
    Duplicates removed
    Sources active
    Sources unavailable
    Queries completed
    Runtime
    Remaining runtime

---

# 23. RATE / THROUGHPUT

Display:

    Leads/hour

Example:

    2,743 leads/hour

Also display:

    Businesses discovered/hour
    Emails discovered/hour

These are measured metrics, not estimates.

---

# 24. TARGET PERFORMANCE

The system should be architected so that very large jobs are possible.

For example:

    10 hours
    25,000-30,000+ leads

This is an ENGINEERING TARGET, not a guaranteed result.

Actual output depends on:

- query
- geographic region
- source coverage
- available businesses
- website availability
- email availability
- source restrictions
- network speed
- hardware
- source response time

The application must measure actual throughput.

Do not fabricate or promise a fixed number of leads.

---

# 25. HIGH-THROUGHPUT PIPELINE

The system should use a pipeline architecture:

    Query Generator
          ↓
    Search Workers
          ↓
    Candidate Queue
          ↓
    Normalization
          ↓
    Deduplication
          ↓
    Website Queue
          ↓
    Website Workers
          ↓
    Contact Extraction
          ↓
    Email Queue
          ↓
    Email Processing
          ↓
    SQLite
          ↓
    Google Sheets Sync

Each stage should operate independently.

---

# 26. BACKPRESSURE

Implement backpressure.

If website enrichment becomes slower than discovery:

    discovery queue grows

The system should not consume unlimited memory.

Use:

- bounded queues
- configurable queue limits
- worker throttling
- incremental persistence

---

# 27. CONCURRENCY

Separate concurrency settings:

    search_concurrency
    browser_concurrency
    website_concurrency
    email_processing_concurrency
    sheets_batch_size

Example:

    Search workers: 5
    Website workers: 20
    Browser workers: 5

Actual values should be configurable and benchmarked.

Do not assume maximum concurrency is maximum performance.

---

# 28. RESOURCE CONTROL

For 24-hour operation:

Monitor:

- RAM
- CPU
- browser processes
- open pages
- open connections
- queue sizes

Periodically recycle unhealthy browser workers.

Do not let one long-lived browser process grow indefinitely.

---

# 29. SEARCH RESULTS DISCOVERY

Search discovery should not depend on a single query.

For each search:

    query
    location
    page/result depth

Track:

    search_id
    query
    location
    source
    page
    status
    records_found

Avoid repeating identical searches unnecessarily.

---

# 30. SEARCH RESULT EXTRACTION

Extract candidate:

- business name
- website URL
- source URL
- snippet
- phone if available
- address if available
- category if available

Do not assume every search result is a business.

Classify results.

---

# 31. RESULT CLASSIFICATION

Classify discovered pages as:

    BUSINESS_WEBSITE
    BUSINESS_DIRECTORY
    BUSINESS_LISTING
    SEARCH_RESULT
    SOCIAL_PROFILE
    IRRELEVANT

Only send relevant candidates into the appropriate downstream pipeline.

---

# 32. BUSINESS WEBSITE DISCOVERY

When a search result appears to represent a business:

    identify candidate website

Then validate the website against:

- business name
- location
- phone
- address
- page title
- content
- domain

Only associate high-confidence websites.

---

# 33. WEBSITE CRAWLING

Once a business website is identified:

Prioritize:

    homepage
    contact
    contact-us
    about
    about-us
    footer
    relevant internal contact pages

Do not crawl an entire website by default.

Implement:

    max_pages
    max_depth
    timeout
    response_size_limit
    same_domain_only

---

# 34. EMAIL EXTRACTION

Email extraction is a primary feature.

Extract publicly displayed business emails from:

- visible text
- mailto links
- contact pages
- about pages
- footer
- structured contact information
- dynamically rendered content when necessary

Support different email providers and domains.

Examples:

    info@business.com
    contact@business.org
    sales@business.ch
    company@gmail.com
    business@outlook.com

Do not restrict extraction to:

    @company.com

A legitimate business may use Gmail, Outlook, Yahoo, Proton, country-specific domains, or organizational domains.

---

# 35. EMAIL EXTRACTION MUST BE GENERIC

Do NOT hardcode only:

    @gmail.com
    @org

Instead:

    detect syntactically valid email addresses

and classify them.

Potential classification:

    CORPORATE_DOMAIN
    FREE_EMAIL_PROVIDER
    EDUCATIONAL
    GOVERNMENT
    ORGANIZATION
    UNKNOWN

The actual email domain must never be discarded merely because it is not a corporate domain.

---

# 36. EMAIL QUALITY

For each email store:

    email
    domain
    source_url
    discovery_method
    confidence

Confidence examples:

    HIGH
    MEDIUM
    LOW

Email found directly on official business contact page:

    HIGH

Email found on official website footer:

    HIGH

Email found on third-party directory:

    MEDIUM

Do not claim an email is verified merely because it matches a regex.

---

# 37. FALSE POSITIVE FILTERING

Filter obvious artifacts:

    example@example.com
    test@example.com
    user@example.com

Also filter:

- image filename artifacts
- CSS artifacts
- JavaScript artifacts
- documentation examples
- malformed email strings

Do not accidentally remove legitimate business emails.

---

# 38. MULTIPLE EMAILS

A business can have:

    info@
    contact@
    sales@
    support@

Store multiple emails.

Deduplicate them.

Rank them.

Preserve all useful public business addresses.

---

# 39. BUSINESS CONTACT DATA

Where publicly available, also extract:

- business phone
- alternate phone
- website
- address
- city
- region
- postal code
- social links
- WhatsApp business link
- rating
- review count
- opening hours where reliably available

Prioritize business information.

Avoid unnecessary personal data.

---

# 40. ENTITY RESOLUTION

Cross-source deduplication must be strong.

Example:

    ABC Restaurant
    ABC Restaurant Zurich
    A.B.C. Restaurant

may be one business.

Signals:

- normalized name
- phone
- domain
- address
- location
- coordinates
- source IDs

Use confidence-based matching.

Do not merge businesses merely because names are similar.

---

# 41. GLOBAL DEDUPLICATION

Because the job may run for 24 hours, deduplication cannot happen only at the end.

Every new candidate should be checked against the persistent database.

Example:

    Candidate discovered
         ↓
    normalize
         ↓
    entity resolution
         ↓
    existing business?
       YES → update record
       NO  → create record

This prevents the database from exploding with duplicates.

---

# 42. DOMAIN-LEVEL DEDUPLICATION

If:

    https://www.example.com
    https://example.com
    http://example.com/

are discovered:

normalize to:

    example.com

Use normalized domains as strong identity signals.

---

# 43. QUERY DEDUPLICATION

Do not repeatedly execute:

    restaurants Zurich

hundreds of times.

Persist query state.

Track:

    pending
    running
    completed
    failed
    exhausted

---

# 44. SEARCH DEPTH

Search depth should be configurable.

Do not hardcode:

    first 10 results only

The system should be able to continue exploring deeper results where the source permits it.

However, detect diminishing returns.

If a query produces no meaningful new businesses after repeated attempts:

    mark exhausted
    move to another query

---

# 45. DYNAMIC QUERY GENERATION

The system should learn from discovered data.

Example:

Initial:

    restaurants Switzerland

Discovery reveals:

    Zurich
    Geneva
    Basel

The query scheduler can then expand into:

    restaurants Zurich
    restaurants Geneva
    restaurants Basel

Similarly, discovered categories can inform additional searches where appropriate.

Do not create an uncontrolled infinite query generator.

---

# 46. GEOGRAPHIC COVERAGE

For large regions, create a geographic coverage strategy.

For country-level requests:

    country
       ↓
    regions/cantons/states
       ↓
    cities
       ↓
    relevant localities

Avoid searching the exact same geography repeatedly.

Persist geographic coverage.

Example:

    Zurich:
        COMPLETE

    Geneva:
        IN_PROGRESS

    Basel:
        PENDING

---

# 47. SEARCH COVERAGE MATRIX

Track:

    Query × Location × Source

Example:

    restaurants × Zurich × source A
    restaurants × Zurich × source B
    restaurants × Geneva × source A

This makes coverage measurable.

---

# 48. ANTI-BOT / CAPTCHA HANDLING

This system must be autonomous.

The user should NOT need to sit in front of the computer solving CAPTCHAs during a 10-24 hour run.

However, do NOT implement CAPTCHA solving or mechanisms intended to circumvent anti-bot/access-control systems.

Instead:

### Detect

Identify:

- CAPTCHA
- challenge page
- access denied
- rate limiting
- repeated abnormal responses

### Isolate

Mark the affected source:

    CAPTCHA_DETECTED

### Cooldown

Stop requesting that source for a configured period.

### Continue

Move work to:

- other discovery sources
- other queries
- other geographic areas
- website enrichment
- search discovery

### Recover

Optionally retry the source later according to a conservative policy.

Never hammer a blocked source.

---

# 49. SOURCE HEALTH MANAGER

Create:

    SourceHealthManager

Track:

    success_rate
    error_rate
    response_time
    CAPTCHA_count
    block_count
    last_failure
    cooldown_until

The orchestrator should use this information.

If a source becomes unreliable:

    reduce priority

If a source becomes blocked:

    temporarily disable it

If it recovers:

    gradually resume it

---

# 50. NO SINGLE POINT OF FAILURE

The system must be capable of continuing if:

- Google search discovery fails
- Google Maps fails
- a directory fails
- one website fails
- Google Sheets fails
- internet disconnects temporarily

The local database must remain authoritative.

---

# 51. LOCAL DATABASE

SQLite should be the primary local data store.

Do NOT make Google Sheets the database.

Use:

    SQLite = source of truth

    Google Sheets = synchronized live output

This is critical for reliability.

---

# 52. DATABASE PERFORMANCE

For tens of thousands of records:

- index normalized business names
- index domains
- index phone numbers
- index emails
- index job IDs
- use transactions
- batch inserts
- batch updates

Avoid one expensive database transaction per field.

---

# 53. GOOGLE SHEETS BATCHING

Do not perform:

    API call
    API call
    API call

for every individual lead.

Instead:

    accumulate 50-500 records
        ↓
    batch write
        ↓
    mark synchronized

Batch size should be configurable.

---

# 54. GOOGLE SHEETS IDEMPOTENCY

Each lead should have a stable:

    lead_id

When synchronizing:

    if lead_id exists:
        update

    else:
        insert

This prevents duplicates after retries.

---

# 55. UI GOOGLE SHEETS INPUT

The UI should allow:

    Google Sheets URL

The backend should extract the spreadsheet identifier safely.

Do not expose credentials in the UI.

Authentication must be handled securely.

---

# 56. AUTHENTICATION

Use an appropriate Google authentication flow.

Never:

- hardcode OAuth secrets
- commit tokens
- expose credentials to frontend JavaScript
- store credentials in plain text unnecessarily

Provide setup documentation.

---

# 57. WEB UI BACKEND

Use a lightweight architecture.

Potential:

    FastAPI backend

with:

    simple HTML/JS frontend

or another lightweight framework already compatible with the repository.

Do not introduce unnecessary frontend complexity.

---

# 58. LIVE UPDATES

The UI should receive live job statistics.

Use:

- WebSocket
- Server-Sent Events
- or efficient polling

Prefer the simplest reliable solution.

---

# 59. UI JOB HISTORY

Show previous jobs:

    JOB ID
    QUERY
    REGION
    START
    DURATION
    STATUS
    BUSINESSES
    EMAILS
    SHEET SYNC

Allow:

    View
    Resume
    Stop
    Export

where appropriate.

---

# 60. PAUSE / RESUME

Support:

    Pause

and:

    Resume

if feasible.

Pause should:

- stop starting new work
- allow safe persistence
- preserve queues
- preserve state

Resume should continue from checkpoint.

---

# 61. MANUAL STOP SAFETY

When STOP is clicked:

    STOP REQUESTED

Workers should finish safe operations and terminate gracefully.

Do not abruptly kill the process unless necessary.

---

# 62. 24-HOUR STABILITY

For long-running jobs:

Implement periodic:

- worker health checks
- browser recycling
- queue monitoring
- database checkpointing
- Google Sheets synchronization
- memory checks
- connectivity checks
- source health checks

The process should not rely on a single browser page surviving for 24 hours.

---

# 63. MEMORY SAFETY

Never retain every HTML page in memory.

After extraction:

    process
    persist
    release

Use bounded caches.

Implement cache expiration where necessary.

---

# 64. BROWSER RECYCLING

Long-running browser automation can become unstable.

Implement worker/browser lifecycle management.

If a worker becomes unhealthy:

    terminate worker
    clean resources
    create replacement worker
    continue from queue/checkpoint

Do not restart the entire job.

---

# 65. DATA QUALITY

Never fabricate:

- business names
- websites
- emails
- phone numbers
- addresses

If uncertain:

    store candidate
    mark confidence
    do not present as verified fact

---

# 66. LEAD ID

Generate deterministic or persistent Lead IDs.

A Lead ID should remain stable across:

- sources
- retries
- enrichment
- Google Sheets synchronization
- job restarts

This is critical for deduplication and synchronization.

---

# 67. SOURCE PROVENANCE

For every business retain:

    source_names
    source_urls
    source_ids
    first_discovered
    last_seen

For every email:

    source_url
    discovery_method
    confidence

---

# 68. MULTI-SOURCE CONFIRMATION

If a business appears on:

    Google Search
    Justdial
    Sulekha
    official website

store:

    source_count = 4

This can increase data confidence.

---

# 69. LEAD QUALITY SCORE

Create an explainable score based on:

- business identity completeness
- website availability
- email availability
- email confidence
- phone availability
- address completeness
- source agreement
- website-business match

Do not hide raw data behind the score.

---

# 70. CONTINUOUS METRICS

Track throughout the job:

    raw candidates
    unique businesses
    duplicates
    websites
    successful website fetches
    emails
    unique emails
    email-qualified businesses
    queries completed
    queries exhausted
    source failures
    CAPTCHA detections
    network failures
    Sheets synchronization count

---

# 71. THROUGHPUT METRICS

Calculate:

    businesses/hour
    unique businesses/hour
    emails/hour
    Sheets rows/hour

Display both:

    current rate
    average rate

---

# 72. GOAL OF 25,000-30,000 LEADS

The system should be architected to support large-scale runs.

A desired benchmark could be:

    10 hours
    25,000-30,000 leads

BUT:

This is not a guarantee.

The actual result must depend on the data available for the selected query and region.

The system should report:

    Actual leads:
        27,413

rather than claiming:

    Expected:
        30,000

unless that is an actual measured result.

---

# 73. PERFORMANCE OPTIMIZATION

Prioritize performance in this order:

1. Avoid duplicate work.
2. Avoid unnecessary browser usage.
3. Use HTTP fetching where sufficient.
4. Use bounded async concurrency.
5. Batch database writes.
6. Batch Google Sheets writes.
7. Cache website enrichment.
8. Parallelize independent pipeline stages.
9. Recycle unhealthy workers.

Do NOT sacrifice reliability simply to increase requests per second.

---

# 74. WEBSITE CRAWLING EFFICIENCY

For each domain:

    fetch homepage
       ↓
    detect contact links
       ↓
    crawl highest-value pages
       ↓
    stop when sufficient data found

If an email is found on the homepage:

    no need to crawl 20 additional pages

This saves enormous time at scale.

---

# 75. DOMAIN CACHE

If multiple businesses point to:

    example.com

do not repeatedly crawl the same pages unnecessarily.

Use:

    domain cache

with timestamps.

Validate business-domain relationships before sharing extracted information between records.

---

# 76. SEARCH RESULT CACHE

Cache search results where appropriate.

Do not repeatedly request the exact same query during one job.

---

# 77. SMART ENRICHMENT PRIORITY

Prioritize businesses:

1. with websites
2. with high-confidence website matches
3. with no existing email
4. with strong business identity

This should maximize email yield.

---

# 78. EMAIL-FIRST ENRICHMENT MODE

If the user's primary objective is leads with emails:

    prioritize businesses likely to have websites/contact pages.

Do not waste equal enrichment effort on obviously low-value candidates.

---

# 79. CONTINUOUS SHEET VIEW

The user should be able to open Google Sheets while the scraper is running and see new rows arriving.

Example:

    10:00 → 1,200 rows
    10:30 → 2,847 rows
    11:00 → 4,912 rows
    12:00 → 7,103 rows

The application should synchronize continuously.

---

# 80. GOOGLE SHEETS SYNC DELAY

Display:

    Last Sheets sync:
        12 seconds ago

    Pending sync:
        37 records

This makes synchronization health visible.

---

# 81. FAILURE DASHBOARD

Display:

    Network:
        CONNECTED

    Google Sheets:
        HEALTHY

    Google Search:
        DEGRADED

    Source A:
        COOLING DOWN

    Source B:
        ACTIVE

This helps diagnose long-running jobs.

---

# 82. LOGGING

Use structured logs.

Events:

    JOB_STARTED
    QUERY_GENERATED
    SEARCH_STARTED
    BUSINESS_DISCOVERED
    DUPLICATE_DETECTED
    WEBSITE_FOUND
    WEBSITE_CRAWLED
    EMAIL_FOUND
    SHEETS_SYNC
    NETWORK_DISCONNECTED
    NETWORK_RESTORED
    SOURCE_BLOCKED
    SOURCE_COOLDOWN
    WORKER_RESTARTED
    JOB_STOPPED
    JOB_COMPLETED

---

# 83. LOG ROTATION

Because jobs can run for 24 hours:

Implement log rotation.

Do not allow logs to grow without limits.

---

# 84. HEALTH ENDPOINTS

If using FastAPI, implement appropriate health endpoints.

For example:

    /health

and:

    /status

The status endpoint should report:

- application health
- active job
- worker health
- database health
- Sheets synchronization health
- connectivity

---

# 85. API STRUCTURE

Potential endpoints:

    POST /jobs
    GET /jobs
    GET /jobs/{id}
    POST /jobs/{id}/stop
    POST /jobs/{id}/pause
    POST /jobs/{id}/resume
    GET /jobs/{id}/stats
    GET /jobs/{id}/events
    GET /sources
    GET /health

Adapt to the existing application.

---

# 86. SECURITY

Protect:

- Google authentication credentials
- OAuth tokens
- configuration secrets
- local database
- API endpoints

Do not expose administrative endpoints publicly without authentication if deployed remotely.

---

# 87. CONFIGURATION

Configuration should include:

    search sources
    source priorities
    search concurrency
    browser concurrency
    enrichment concurrency
    crawl depth
    max pages
    retry limits
    cooldown
    Sheets batch size
    checkpoint interval
    job duration
    memory thresholds

Provide:

    .env.example

Do not commit secrets.

---

# 88. TESTING

Add unit tests for:

- query expansion
- location expansion
- query scheduler
- deduplication
- email extraction
- email validation
- website matching
- source health
- checkpointing
- job states
- Sheets synchronization
- retry behavior
- connectivity recovery

---

# 89. FAILURE TESTING

Simulate:

- internet disconnect
- internet reconnect
- Google Sheets unavailable
- Google Sheets API timeout
- browser crash
- worker crash
- source CAPTCHA
- source rate limiting
- malformed HTML
- duplicate businesses
- duplicate emails
- database restart
- application restart

The system should recover without losing persisted data.

---

# 90. LONG-RUNNING TEST

Run a controlled test for:

    1 hour

Measure:

- memory growth
- CPU
- throughput
- duplicate rate
- browser stability
- database size
- Sheets synchronization
- source failures

Then run a longer soak test where practical.

Do not claim 24-hour stability without actually testing it.

---

# 91. PERFORMANCE BENCHMARK

Benchmark:

    1 hour
    3 hours
    6 hours
    10 hours

Record:

    candidates
    unique businesses
    emails
    throughput
    average latency
    memory usage
    source failures

Use these results to optimize the system.

---

# 92. README

Rewrite the README as a serious production project.

Include:

## Overview

## Architecture

## Features

## Supported Sources

## Installation

## Configuration

## CLI

## Web UI

## Google Sheets Setup

## Long-Running Jobs

## Checkpoint / Resume

## Failure Recovery

## Email Extraction

## Data Schema

## Performance Benchmarks

## Adding New Sources

## Troubleshooting

---

# 93. ARCHITECTURE DIAGRAM

Include a clear architecture diagram:

    USER
      |
      v
    WEB UI
      |
      v
    JOB MANAGER
      |
      v
    QUERY EXPANSION
      |
      v
    QUERY SCHEDULER
      |
      +-----------------------------+
      |             |               |
      v             v               v
    SEARCH       DIRECTORIES      OTHER
    DISCOVERY    / SOURCES        SOURCES
      |             |               |
      +-------------+---------------+
                    |
                    v
             CANDIDATE QUEUE
                    |
                    v
              NORMALIZATION
                    |
                    v
             ENTITY RESOLUTION
                    |
                    v
             UNIQUE BUSINESSES
                    |
                    v
            WEBSITE DISCOVERY
                    |
                    v
            WEBSITE CRAWLING
                    |
                    v
            CONTACT EXTRACTION
                    |
                    v
             EMAIL EXTRACTION
                    |
                    v
             QUALITY SCORING
                    |
                    +----------+
                    |          |
                    v          v
                 SQLITE    SHEETS QUEUE
                               |
                               v
                         GOOGLE SHEETS

Parallel systems:

    Connectivity Monitor
    Source Health Manager
    Checkpoint Manager
    Worker Manager
    Observability

---

# 94. IMPORTANT SOURCE STRATEGY

Do not hard-code the product around only:

    Google Maps
    Justdial

Treat them as optional source adapters.

Potential discovery sources should be evaluated and added according to:

- geographic coverage
- business-category relevance
- data quality
- website availability
- stability
- permitted access
- maintenance requirements

Potential source categories:

### Search discovery

Search engines and public search results.

### Indian business directories

Sulekha
IndiaMART
TradeIndia
ExportersIndia
Yellow Pages India
and other relevant directories.

### International/local business directories

Add high-value sources appropriate to the target geography.

### Niche directories

For categories such as:

    restaurants
    hotels
    clinics
    real estate
    gyms
    schools
    manufacturers

support category-specific sources where appropriate.

The source architecture must allow these to be added independently.

---

# 95. SOURCE PLUGINS

Make adding a source easy.

A developer should be able to:

    create adapter
    implement BaseScraper
    register source
    configure source

without modifying the core pipeline.

---

# 96. NO SOURCE SHOULD BE REQUIRED

The system must still operate if:

    Google Maps = unavailable
    Justdial = unavailable

provided that other configured discovery sources remain available.

---

# 97. QUERY/REGION EXAMPLE

For:

    restaurants
    Switzerland

the system should progressively explore:

    Switzerland
    Zurich
    Geneva
    Basel
    Bern
    Lausanne
    Lucerne
    St. Gallen
    Lugano
    Winterthur
    relevant localities

combined with relevant restaurant search variations.

The exact geographic hierarchy should be generated from reliable geographic data rather than a tiny hardcoded list.

---

# 98. SEARCH DIVERSITY

Do not run only:

    restaurants Switzerland

over and over.

Use dimensions:

    category
    subcategory
    geography
    language where relevant
    business-type terminology

For multilingual regions, consider relevant language variations where appropriate.

Example for Switzerland:

    restaurant
    restaurants
    restaurant suisse
    restaurante
    ristorante

ONLY where the terminology is genuinely relevant to the region and query.

---

# 99. DYNAMIC DISCOVERY LOOP

Conceptually:

    while job_running:

        generate_next_query()

        execute_query()

        extract_candidates()

        normalize()

        deduplicate()

        persist()

        enqueue_websites()

        enrich_websites()

        extract_emails()

        persist()

        synchronize_sheets()

        update_dashboard()

        monitor_health()

        continue

The loop must never depend on one source.

---

# 100. STOP CONDITIONS

The job stops when:

### User stop

    STOP clicked

OR:

### Duration

    configured duration reached

OR:

### Optional maximum

    maximum records reached

OR:

### Fatal application failure

    only if recovery is impossible

Do NOT stop because:

- one source failed
- one search query failed
- one website failed
- one CAPTCHA appeared
- Google Sheets temporarily failed
- internet temporarily disconnected

---

# 101. FINAL DATA GUARANTEE

The system should guarantee:

    No intentionally fabricated data.

It should NOT guarantee:

    "30000 leads in every 10-hour run."

Instead guarantee:

    continuous discovery attempts
    persistent storage
    deduplication
    recovery
    measurable throughput

Actual output depends on available data.

---

# 102. FINAL ACCEPTANCE TEST

Create a test job:

    Query:
        restaurants

    Region:
        Switzerland

    Duration:
        1 hour

Verify:

- web UI starts job
- query expansion works
- multiple searches run
- businesses are discovered
- websites are discovered
- emails are extracted
- duplicates are removed
- SQLite is updated continuously
- Google Sheets receives batches
- UI counters update
- source failure does not kill job
- internet failure pauses workers
- internet restoration resumes job
- job can be manually stopped
- checkpoint is saved
- final statistics are correct

---

# 103. SECOND ACCEPTANCE TEST

Run:

    restaurants
    Switzerland
    3 hours

Measure:

    businesses/hour
    emails/hour
    unique businesses
    duplicate percentage
    website success rate
    email yield
    Sheets synchronization

Use actual measured numbers.

---

# 104. FINAL ENGINEERING REQUIREMENT

This project must evolve from:

    "a website scraper"

into:

    "an autonomous long-running business lead discovery and enrichment platform."

The permanent architecture should be:

    USER
      ↓
    QUERY + REGION + DURATION
      ↓
    QUERY EXPANSION
      ↓
    CONTINUOUS DISCOVERY
      ↓
    MULTI-SOURCE COLLECTION
      ↓
    NORMALIZATION
      ↓
    ENTITY RESOLUTION
      ↓
    WEBSITE DISCOVERY
      ↓
    WEBSITE ENRICHMENT
      ↓
    EMAIL EXTRACTION
      ↓
    QUALITY SCORING
      ↓
    SQLITE
      ↓
    GOOGLE SHEETS
      ↓
    LIVE WEB DASHBOARD

Supporting infrastructure:

    CHECKPOINTING
    CONNECTIVITY MONITOR
    SOURCE HEALTH
    RETRY/BACKOFF
    WORKER MANAGEMENT
    RESOURCE MANAGEMENT
    OBSERVABILITY

The system must be able to run unattended for long periods.

The user should only need to:

    1. Enter business query.
    2. Enter region.
    3. Select duration.
    4. Configure Google Sheets.
    5. Press START.

After that, the system should autonomously discover, enrich, deduplicate, persist, synchronize, monitor itself, recover from temporary failures, and continue until the configured stop condition.

---

# 105. IMPLEMENTATION ORDER

DO NOT immediately rewrite everything.

FIRST:

1. Inspect the entire existing repository.
2. Map current architecture.
3. Identify reusable components.
4. Identify current bottlenecks.
5. Identify current browser/resource problems.
6. Identify existing auto-scroll logic.
7. Identify existing email extraction logic.
8. Identify existing source adapters.
9. Identify existing database/storage.
10. Identify existing UI, if any.

THEN:

Produce:

    CURRENT ARCHITECTURE
    CURRENT BOTTLENECKS
    TARGET ARCHITECTURE
    MIGRATION PLAN
    IMPLEMENTATION PHASES
    RISK ANALYSIS

Only after that should implementation begin.

---

# 106. IMPLEMENTATION PHASES

### PHASE 1

Repository audit.

### PHASE 2

Persistent job/state architecture.

### PHASE 3

SQLite source-of-truth database.

### PHASE 4

Query expansion engine.

### PHASE 5

Query scheduler.

### PHASE 6

Multi-source discovery.

### PHASE 7

Improved auto-scroll/pagination where applicable.

### PHASE 8

Website discovery.

### PHASE 9

Website crawler.

### PHASE 10

Email extraction.

### PHASE 11

Entity resolution.

### PHASE 12

Continuous enrichment pipeline.

### PHASE 13

Connectivity monitor.

### PHASE 14

Source health manager.

### PHASE 15

Checkpoint/resume.

### PHASE 16

Google Sheets synchronization.

### PHASE 17

Live web UI.

### PHASE 18

Long-running worker/resource management.

### PHASE 19

Testing.

### PHASE 20

Performance optimization.

### PHASE 21

Documentation.

---

# 107. FINAL RULE

Do not optimize this system around defeating individual websites.

Optimize it around:

    SOURCE REDUNDANCY
    SEARCH DIVERSITY
    QUERY EXPANSION
    GEOGRAPHIC COVERAGE
    WEBSITE ENRICHMENT
    EMAIL YIELD
    DEDUPLICATION
    PERSISTENCE
    RECOVERY
    THROUGHPUT
    DATA QUALITY

If one source says:

    "No."

the system should effectively say:

    "Fine. There are other discovery paths."

The system should continue working autonomously.

START BY INSPECTING THE EXISTING REPOSITORY.
DO NOT MAKE MAJOR CHANGES BEFORE PRODUCING THE ARCHITECTURE AUDIT AND MIGRATION PLAN.