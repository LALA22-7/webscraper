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
    query: str = typer.Option(..., "--query", "-q", help="Search query (e.g., 'gyms')"),
    location: str = typer.Option(..., "--location", "-l", help="Location (e.g., 'Noida')"),
    target: int = typer.Option(100, "--target", "-t", help="Target number of unique businesses"),
    require_email: bool = typer.Option(False, "--require-email", help="Only export leads that contain emails"),
    sources: str = typer.Option("google_maps,justdial", "--sources", help="Comma-separated list of sources to use"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode")
):
    """Start a new discovery and enrichment job."""
    console.print(f"[bold blue]Starting Scrape Job[/bold blue]")
    console.print(f"Query: [green]{query}[/green]")
    console.print(f"Location: [green]{location}[/green]")
    console.print(f"Target: [green]{target}[/green]")
    console.print(f"Require Email: [green]{require_email}[/green]")
    
    source_list = [s.strip() for s in sources.split(',')]
    
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
        console.print(f"Discovered: {job.discovered_count}")
        console.print(f"Enriched: {job.enriched_count}")
        console.print(f"Emails found: {job.email_count}")
        
    asyncio.run(run())

if __name__ == "__main__":
    app()
