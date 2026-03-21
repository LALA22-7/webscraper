from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import threading
import time
import uuid
import csv
import io
from datetime import datetime
import os
import sys
from google_maps_scraper import scrape_google_maps, PlaceRow

app = Flask(__name__)
CORS(app)

# Global storage for scraping tasks
scraping_tasks = {}

class ScrapingTask:
    def __init__(self, task_id, profession, location, max_leads):
        self.task_id = task_id
        self.profession = profession
        self.location = location
        self.max_leads = max_leads
        self.status = "pending"
        self.progress = 0
        self.current_location = ""
        self.results = []
        self.start_time = None
        self.end_time = None
        self.error = None
        self.estimated_time_remaining = 0

def estimate_time_remaining(progress, elapsed_time):
    """Estimate remaining time based on current progress"""
    if progress <= 0:
        return 0
    total_estimated = elapsed_time / progress * 100
    remaining = total_estimated - elapsed_time
    return max(0, remaining)

def run_scraping_task(task_id):
    """Run scraping task in background thread"""
    task = scraping_tasks[task_id]
    task.status = "running"
    task.start_time = time.time()
    
    try:
        query = f"{task.profession} in {task.location}"
        
        # Define progress callback for real-time updates
        def progress_callback(progress_data):
            # Update task with progress information
            if 'current_location' in progress_data:
                task.current_location = f"Searching: {progress_data['current_location']}"
            
            if 'current_search' in progress_data:
                task.current_location = f"Searching: {progress_data['current_search']}"
            
            if 'results_found' in progress_data:
                task.results_count = progress_data['results_found']
                
                # Calculate progress percentage
                target = progress_data.get('target', task.max_leads)
                task.progress = min(100, int((progress_data['results_found'] / target) * 100))
                
                # Update estimated time remaining
                elapsed = time.time() - task.start_time
                if task.progress > 0:
                    task.estimated_time_remaining = estimate_time_remaining(task.progress, elapsed)
            
            if 'status' in progress_data and progress_data['status'] == 'completed':
                task.status = 'completed'
                task.progress = 100
        
        # Run the scraper with progress callback
        output_csv = f"temp_{task.task_id}.csv"
        count = scrape_google_maps(query, task.max_leads, output_csv, headless=True, progress_callback=progress_callback)
        
        # Read final results
        if os.path.exists(output_csv):
            with open(output_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not any(r['name'] == row['name'] and r['phone'] == row['phone'] for r in task.results):
                        task.results.append({
                            'name': row['name'],
                            'phone': row['phone'],
                            'url': row['url']
                        })
            os.remove(output_csv)  # Clean up temp file
        
        task.status = "completed"
        task.progress = 100
        task.results_count = len(task.results)
        
    except Exception as e:
        task.error = str(e)
        task.status = "failed"
    
    task.end_time = time.time()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start_scraping', methods=['POST'])
def start_scraping():
    data = request.json
    profession = data.get('profession')
    location = data.get('location')
    max_leads = max(10, int(data.get('max_leads', 10)))  # Minimum 10 leads
    
    task_id = str(uuid.uuid4())
    task = ScrapingTask(task_id, profession, location, max_leads)
    scraping_tasks[task_id] = task
    
    # Start scraping in background thread
    thread = threading.Thread(target=run_scraping_task, args=(task_id,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/api/scraping_status/<task_id>')
def scraping_status(task_id):
    if task_id not in scraping_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = scraping_tasks[task_id]
    
    response = {
        'status': task.status,
        'progress': task.progress,
        'current_location': task.current_location,
        'results_count': len(task.results),
        'estimated_time_remaining': task.estimated_time_remaining
    }
    
    if task.status == "completed":
        response['results'] = task.results
    elif task.status == "failed":
        response['error'] = task.error
    
    return jsonify(response)

@app.route('/api/export/<task_id>/<format>')
def export_results(task_id, format):
    if task_id not in scraping_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = scraping_tasks[task_id]
    if task.status != "completed" or not task.results:
        return jsonify({'error': 'No results to export'}), 400
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{task.profession}_{task.location}_{timestamp}"
    
    if format == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['Name', 'Phone', 'URL'])
        writer.writeheader()
        for result in task.results:
            writer.writerow({
                'Name': result['name'],
                'Phone': result['phone'],
                'URL': result['url']
            })
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{filename}.csv'
        )
    
    elif format == 'excel':
        # Simple Excel-like CSV format (since pandas doesn't work with Python 3.14)
        output = io.StringIO()
        output.write("Business Name\tPhone Number\tURL\n")
        for result in task.results:
            output.write(f"{result['name']}\t{result['phone']}\t{result['url']}\n")
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # UTF-8 with BOM for Excel
            mimetype='text/tab-separated-values',
            as_attachment=True,
            download_name=f'{filename}.tsv'
        )
    
    elif format == 'pdf':
        # Simple text-based PDF (since reportlab doesn't work with Python 3.14)
        output = io.BytesIO()
        
        # Create a simple text file that can be opened as PDF
        content = f"Scraping Results: {task.profession} in {task.location}\n"
        content += f"Total Results: {len(task.results)}\n"
        content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += "="*80 + "\n\n"
        
        for i, result in enumerate(task.results, 1):
            content += f"{i}. {result['name']}\n"
            content += f"   Phone: {result['phone']}\n"
            content += f"   URL: {result['url']}\n\n"
        
        output.write(content.encode('utf-8'))
        output.seek(0)
        return send_file(
            output,
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'{filename}_report.txt'
        )
    
    return jsonify({'error': 'Unsupported format'}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
