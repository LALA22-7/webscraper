import asyncio
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from src.core.source_manager import SourceManager
from src.core.orchestrator import DiscoveryOrchestrator
from src.core.job_manager import JobManager
from src.processing.deduplicator import Deduplicator
from src.enrichment.website_crawler import WebsiteCrawler

app = typer.Typer(help="Business Lead Discovery & Email Enrichment Platform")
console = Console()

@app.command()
def scrape(
    query: str = typer.Option(None, "--query", "-q", prompt="What type of businesses are you looking for? (e.g., gyms)", help="Search query"),
    location: str = typer.Option(None, "--location", "-l", prompt="In which city or area? (e.g., Noida)", help="Location"),
    target: int = typer.Option(50, "--target", "-t", prompt="How many businesses do you want to find?", help="Target number of unique businesses"),
    require_email: bool = typer.Option(False, "--require-email", prompt="Do you only want leads that have emails? (y/n)", help="Only export leads that contain emails"),
    sources: str = typer.Option("all", "--sources", help="Comma-separated list of sources, or 'all' for auto-fallback"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and show planned job without running")
):
    """Start a new discovery and enrichment job."""
    from src.utils.autocorrect import autocorrect
    
    # Auto-correct query and location to fix typos
    corrected_query = autocorrect(query) if query else query
    corrected_location = autocorrect(location) if location else location
    
    if corrected_query != query or corrected_location != location:
        console.print(f"[bold yellow]✨ Auto-corrected search terms to:[/bold yellow] '{corrected_query}' in '{corrected_location}'")
        query = corrected_query
        location = corrected_location
        
    console.print(f"[bold blue]Starting Scrape Job[/bold blue]")
    console.print(f"Query: [green]{query}[/green]")
    console.print(f"Location: [green]{location}[/green]")
    console.print(f"Target: [green]{target}[/green]")
    console.print(f"Require Email: [green]{require_email}[/green]")
    
    if sources.lower() == "all":
        source_list = ["sulekha", "indiamart", "tradeindia", "duckduckgo", "google_maps", "justdial"]
    else:
        source_list = [s.strip() for s in sources.split(',')]
    
    if dry_run:
        console.print("\n[bold yellow]DRY RUN - Planned Job details:[/bold yellow]")
        console.print("Planned sources:")
        for s in source_list:
            console.print(f"  - {s}")
        console.print(f"\nTarget will be dynamically managed based on `require_email`: {require_email}")
        return

    
    # Initialize components
    source_manager = SourceManager(headless=headless)
    deduplicator = Deduplicator()
    orchestrator = DiscoveryOrchestrator(source_manager, deduplicator)
    crawler = WebsiteCrawler(max_pages_per_domain=5, concurrency=10)
    job_manager = JobManager(orchestrator, crawler)
    
    async def run():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task(description=f"Discovering {query} in {location}...", total=target)
            
            # Since the orchestrator logs to stdout, it might interfere with rich progress bar.
            # In a real app we'd pass a progress callback. Here we just await the job manager.
            job = await job_manager.create_and_run_job(query, location, target, source_list, require_email=require_email)
            
            progress.update(task_id, completed=job.discovered_count, description="Job completed")
            
        console.print("\n[bold green]Job Completed[/bold green]")
        console.print(f"Job ID: {job.id}")
        console.print(f"Discovered: {job.discovered_count}")
        console.print(f"Enriched: {job.enriched_count}")
        console.print(f"Emails found: {job.email_count}")
        
        # Auto export
        safe_query = query.replace(" ", "_").lower()
        safe_loc = location.replace(" ", "_").lower()
        output_file = f"leads_{safe_query}_{safe_loc}.csv"
        
        from src.storage.sqlite import SQLiteManager
        db = SQLiteManager()
        db.export_csv(job.id, output_file)
        console.print(f"\n[bold magenta]Automatically exported results to {output_file}[/bold magenta]")
        
    asyncio.run(run())



@app.command()
def sources():
    """List available sources and their status."""
    manager = SourceManager()
    console.print("\n[bold]Available Sources[/bold]")
    for name, scraper in manager._available_sources.items():
        console.print(f"{scraper.name.ljust(20)} ENABLED (Priority {manager.PRIORITIES.get(name, 999)})")
        
@app.command()
def resume(job_id: str):
    """Resume a previously paused or failed job."""
    console.print(f"[bold yellow]Resuming Job:[/bold yellow] {job_id}")
    console.print("[red]Resume functionality is wired to DB but not fully implemented in CLI yet.[/red]")
    
@app.command()
def export(
    job_id: str = typer.Argument(..., help="Job ID to export"),
    format: str = typer.Option("csv", "--format", "-f", help="Output format (csv)"),
    output: str = typer.Option("leads.csv", "--output", "-o", help="Output file path")
):
    """Export leads from a specific job."""
    from src.storage.sqlite import SQLiteManager
    db = SQLiteManager()
    
    if format.lower() == "csv":
        db.export_csv(job_id, output)
        console.print(f"[bold green]Exported job {job_id} to {output}[/bold green]")
    else:
        console.print(f"[bold red]Format {format} not supported yet.[/bold red]")

if __name__ == "__main__":
    app()
