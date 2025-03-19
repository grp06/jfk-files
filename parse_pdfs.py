import os
import glob
from concurrent.futures import ThreadPoolExecutor
import pdf2image
import anthropic
import time
import json
from tqdm import tqdm
from dotenv import load_dotenv
import datetime

# Load environment variables from .env file
load_dotenv()

# Config
PDF_DIR = "jfk_pdfs"
OUTPUT_DIR = f"output_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
MAX_WORKERS = 6  # Parallel PDFs to process
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
print(ANTHROPIC_API_KEY)
# Create Anthropic client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-3-5-haiku-20241022"

# Categories to look for in documents
CONSPIRACY_CATEGORIES = [
    "OSWALD_ASSOCIATIONS",
    "ORGANIZED_CRIME_CONNECTIONS",
    "CIA_FBI_ACTIVITIES",
    "AUTOPSY_MEDICAL_EVIDENCE",
    "WITNESS_TESTIMONIES",
    "FOREIGN_GOVERNMENT_REACTIONS",
    "INTERNAL_GOVT_COMMUNICATIONS",
    "SURVEILLANCE_RECORDS",
    "TRAVEL_FINANCIAL_RECORDS",
    "PHOTOGRAPHIC_VIDEO_EVIDENCE"
]

def ensure_dir(directory):
    """Create directory if it doesn't exist"""
    os.makedirs(directory, exist_ok=True)

def pdf_to_images(pdf_path):
    """Convert PDF to list of images"""
    try:
        return pdf2image.convert_from_path(pdf_path)
    except Exception as e:
        print(f"Error converting PDF to images: {pdf_path} - {e}")
        return []

def analyze_image(image, pdf_name, page_num):
    """Analyze image for JFK conspiracy evidence using Claude"""
    try:
        # Convert image to base64
        import io
        import base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Construct the prompt
        prompt = f"""Analyze this JFK assassination document page in detail, focusing on the following key areas:

IMPORTANT CONTEXT: These JFK files have already been released to the public. Any text referring to future release dates is outdated as these documents are now declassified and publicly available.

KEY AREAS TO ANALYZE:

1. OSWALD_ASSOCIATIONS: Evidence of Lee Harvey Oswald's connections with CIA, KGB, FBI, or anti-Castro groups. Look for meetings, communications, training, handlers, or operational involvement.

2. ORGANIZED_CRIME_CONNECTIONS: Links between Oswald, Jack Ruby, and organized crime figures (especially Carlos Marcello, Sam Giancana, Santo Trafficante). Note any mob connections to CIA operations.

3. CIA_FBI_ACTIVITIES: Internal communications about Oswald before/after assassination. Look for surveillance records, memos discussing Oswald, operations in Mexico City or New Orleans, or attempts to influence investigation.

4. AUTOPSY_MEDICAL_EVIDENCE: Inconsistencies in autopsy reports, chain of custody issues with evidence, missing X-rays or photographs, conflicting medical testimonies, or evidence tampering.

5. WITNESS_TESTIMONIES: Statements from Dealey Plaza witnesses, especially those contradicting the official narrative. Note witnesses reporting grassy knoll shooters or intimidation by officials.

6. FOREIGN_GOVERNMENT_REACTIONS: Soviet/Cuban intelligence about the assassination, diplomatic communications, or knowledge of Oswald during his USSR time or Mexico City visit.

7. INTERNAL_GOVT_COMMUNICATIONS: Memos between agencies (White House, Secret Service, CIA, FBI) discussing assassination theories, evidence suppression, or investigation concerns.

8. SURVEILLANCE_RECORDS: Logs or recordings of Oswald or associates before/after assassination. Note surveillance gaps, destroyed recordings, or unusual monitoring patterns.

9. TRAVEL_FINANCIAL_RECORDS: Oswald's unexplained travel, funding sources, or financial transactions inconsistent with his known income.

10. PHOTOGRAPHIC_VIDEO_EVIDENCE: Analysis of Zapruder film or other visual evidence, authentication concerns, or missing frames/footage.

ANALYSIS GUIDELINES:
- Identify exact names, dates, locations, and document references
- Note redactions or partial information that seems significant
- Look for inconsistencies with the official Warren Commission narrative
- Distinguish between factual statements and speculative comments
- Consider how this information connects to other known evidence

Respond with ONLY a valid JSON object with this structure:
{{
  "document_id": "{pdf_name}",
  "page_number": {page_num},
  "relevant_findings": [
    {{
      "category": "CATEGORY_NAME",
      "confidence": 1-10,
      "description": "Brief description of finding",
      "direct_quote": "Exact text from document if available",
      "significance": "Why this is important to the investigation"
    }}
  ],
  "overall_page_relevance": 1-10
}}

Use empty arrays if nothing relevant is found. Confidence and relevance should be numbers from 1-10 (1=low, 10=high).
"""
        
        # Call Claude API with prefilled JSON start to enforce JSON output
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                },
                {
                    "role": "assistant",
                    "content": "{"
                }
            ]
        )
        
        # Get the response and fix JSON format
        result_text = response.content[0].text.strip()
        # Properly reconstruct the JSON by adding the opening brace
        if not result_text.startswith("{"):
            result_text = "{" + result_text
        
        # Clean up any progress bar or other output that might be in the response
        # by trying to find the complete JSON object
        try:
            import re
            # Find a complete JSON object pattern
            json_pattern = r'\{\s*"document_id".*?"overall_page_relevance"\s*:\s*\d+\s*\}'
            match = re.search(json_pattern, result_text, re.DOTALL)
            if match:
                result_text = match.group(0)
            
            # Parse the JSON data
            result_data = json.loads(result_text)
            return result_data
        except (json.JSONDecodeError, re.error) as e:
            # If regex approach fails, try a more manual approach
            try:
                # Remove any progress bar output that might be mixed in with the JSON
                lines = result_text.split('\n')
                clean_lines = []
                for line in lines:
                    # Skip lines with progress bars or other non-JSON content
                    if '%' in line and ('█' in line or '|' in line):
                        continue
                    clean_lines.append(line)
                
                # Rejoin and parse
                clean_json = '\n'.join(clean_lines)
                result_data = json.loads(clean_json)
                return result_data
            except json.JSONDecodeError as e2:
                print(f"Error parsing JSON response: {e2}")
                print(f"Raw response: {result_text[:100]}...")
                return {
                    "document_id": pdf_name,
                    "page_number": page_num,
                    "relevant_findings": [],
                    "overall_page_relevance": 1,
                    "error": "Failed to parse JSON response"
                }
            
    except Exception as e:
        print(f"Error analyzing image: {e}")
        return {
            "document_id": pdf_name,
            "page_number": page_num,
            "relevant_findings": [],
            "overall_page_relevance": 1,
            "error": str(e)
        }

def process_pdf(pdf_path):
    """Process a single PDF"""
    pdf_name = os.path.basename(pdf_path).replace('.pdf', '')
    output_folder = os.path.join(OUTPUT_DIR, pdf_name)
    results_path = os.path.join(output_folder, f"{pdf_name}-analysis.json")
    checkpoint_path = os.path.join(output_folder, ".checkpoint.json")
    
    # Create output folder
    ensure_dir(output_folder)
    
    # Check if already processed
    if os.path.exists(results_path):
        print(f"Skipping {pdf_name} - already processed")
        return
    
    # Initialize or load checkpoint
    checkpoint = {}
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
    
    # Get previously processed pages
    results = checkpoint.get('results', [])
    last_page = checkpoint.get('last_page', -1)
    
    # Convert PDF to images if not already processed
    print(f"Processing {pdf_name}")
    images = pdf_to_images(pdf_path)
    
    # Process each page
    for i, img in enumerate(tqdm(images, desc=f"Analyzing pages in {pdf_name}")):
        # Skip already processed pages
        if i <= last_page:
            continue
            
        # Analyze the page
        page_result = analyze_image(img, pdf_name, i + 1)
        results.append(page_result)
        
        # Update checkpoint after each page
        checkpoint['results'] = results
        checkpoint['last_page'] = i
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint, f)
    
    # Save final results
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate summary report
    generate_summary_report(results, output_folder, pdf_name)
    
    # Clean up checkpoint file
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    
    print(f"Completed processing {pdf_name}")

def generate_summary_report(results, output_folder, pdf_name):
    """Generate a human-readable summary from the analysis results"""
    summary_path = os.path.join(output_folder, f"{pdf_name}-summary.txt")
    
    # Filter for pages with relevant findings
    relevant_pages = [r for r in results if r.get('overall_page_relevance', 0) > 3]
    
    # Create a summary by category
    categories = {cat: [] for cat in CONSPIRACY_CATEGORIES}
    
    for page in relevant_pages:
        for finding in page.get('relevant_findings', []):
            category = finding.get('category')
            if category in categories:
                categories[category].append({
                    'page': page.get('page_number'),
                    'confidence': finding.get('confidence'),
                    'description': finding.get('description'),
                    'quote': finding.get('direct_quote', 'N/A')
                })
    
    # Write the summary
    with open(summary_path, 'w') as f:
        f.write(f"JFK ANALYSIS SUMMARY: {pdf_name}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Document contains {len(relevant_pages)} pages with relevant information.\n\n")
        
        # List highest relevance pages
        if relevant_pages:
            f.write("TOP RELEVANT PAGES:\n")
            top_pages = sorted(relevant_pages, key=lambda x: x.get('overall_page_relevance', 0), reverse=True)[:5]
            for page in top_pages:
                f.write(f"- Page {page.get('page_number')}: Relevance {page.get('overall_page_relevance')}/10\n")
            f.write("\n")
        
        # Write findings by category
        f.write("FINDINGS BY CATEGORY:\n")
        for cat, findings in categories.items():
            if findings:
                f.write(f"\n{cat.replace('_', ' ')}:\n")
                f.write("-" * 40 + "\n")
                for finding in sorted(findings, key=lambda x: x.get('confidence', 0), reverse=True):
                    f.write(f"Page {finding['page']} (Confidence: {finding['confidence']}/10)\n")
                    f.write(f"  {finding['description']}\n")
                    if finding['quote'] != 'N/A':
                        f.write(f"  QUOTE: \"{finding['quote']}\"\n")
                    f.write("\n")
    
    print(f"Summary report generated: {summary_path}")

def main():
    """Main function to process all PDFs"""
    ensure_dir(OUTPUT_DIR)
    
    # Get list of all PDFs
    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIR}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Process PDFs in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        list(executor.map(process_pdf, pdf_files))
    
    # Generate a global summary
    generate_global_summary()
    
    print("All PDFs processed successfully")

def generate_global_summary():
    """Generate a global summary across all documents"""
    summary_path = os.path.join(OUTPUT_DIR, "global_summary.txt")
    
    # Collect all analysis files
    analysis_files = []
    for root, _, files in os.walk(OUTPUT_DIR):
        for file in files:
            if file.endswith('-analysis.json'):
                analysis_files.append(os.path.join(root, file))
    
    if not analysis_files:
        print("No analysis files found for global summary")
        return
    
    # Collect findings from all documents
    all_findings = []
    
    for file_path in analysis_files:
        with open(file_path, 'r') as f:
            results = json.load(f)
            
        doc_id = results[0]['document_id'] if results else "unknown"
        
        for page in results:
            for finding in page.get('relevant_findings', []):
                if finding.get('confidence', 0) >= 7:  # Only high confidence findings
                    all_findings.append({
                        'document': doc_id,
                        'page': page.get('page_number'),
                        'category': finding.get('category'),
                        'confidence': finding.get('confidence'),
                        'description': finding.get('description'),
                        'quote': finding.get('direct_quote', 'N/A')
                    })
    
    # Sort by category and confidence
    all_findings.sort(key=lambda x: (x['category'], -x['confidence']))
    
    # Write global summary
    with open(summary_path, 'w') as f:
        f.write("JFK DOCUMENTS GLOBAL ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total documents analyzed: {len(analysis_files)}\n")
        f.write(f"Total high-confidence findings: {len(all_findings)}\n\n")
        
        # Write findings by category
        current_category = None
        for finding in all_findings:
            if finding['category'] != current_category:
                current_category = finding['category']
                f.write(f"\n{current_category.replace('_', ' ')}:\n")
                f.write("-" * 40 + "\n")
            
            f.write(f"[{finding['document']}, Page {finding['page']}] (Confidence: {finding['confidence']}/10)\n")
            f.write(f"  {finding['description']}\n")
            if finding['quote'] != 'N/A':
                f.write(f"  QUOTE: \"{finding['quote']}\"\n")
            f.write("\n")
    
    print(f"Global summary generated: {summary_path}")

if __name__ == "__main__":
    main()

