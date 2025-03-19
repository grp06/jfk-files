import os
import argparse
import glob
import json
import pandas as pd
import anthropic
import pdf2image
from dotenv import load_dotenv
import base64
import io
import re
from datetime import datetime

# Load environment variables
load_dotenv()

# Configuration
PDF_DIR = "jfk_pdfs"  # Directory containing original PDFs
FINDINGS_DIR = "output_20250318_180803"  # Directory with analysis results
HIGH_CONFIDENCE_CSV = os.path.join(FINDINGS_DIR, "high_confidence_findings.csv")
OUTPUT_DIR = f"doc_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  # Output directory

# Claude 3.7 Sonnet API configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-3-7-sonnet-20250219"  # Using the most powerful model for the deep analysis

def ensure_dir(directory):
    """Create directory if it doesn't exist"""
    os.makedirs(directory, exist_ok=True)

def find_pdf_file(document_id):
    """Find the PDF file matching the document ID"""
    # Try exact match first
    pdf_files = glob.glob(os.path.join(PDF_DIR, f"{document_id}.pdf"))
    if pdf_files:
        return pdf_files[0]
    
    # If no exact match, try partial match
    pdf_files = glob.glob(os.path.join(PDF_DIR, f"*{document_id}*.pdf"))
    if pdf_files:
        return pdf_files[0]
    
    return None

def extract_page_from_pdf(pdf_path, page_num):
    """Extract a specific page from a PDF and convert to image"""
    try:
        # Adjust page number (might use 1-indexing while pdf2image uses 0-indexing)
        try:
            page_idx = int(page_num) - 1
            if page_idx < 0:
                page_idx = 0
        except ValueError:
            # If page_num is not a valid integer, default to first page
            page_idx = 0
        
        # Convert only the specific page
        images = pdf2image.convert_from_path(pdf_path, first_page=page_idx+1, last_page=page_idx+1)
        
        if images:
            return images[0]
        return None
    except Exception as e:
        print(f"Error extracting page {page_num} from {pdf_path}: {e}")
        return None

def find_relevant_pages(document_id):
    """Find the most relevant pages for a document based on existing analysis"""
    # First check high confidence findings
    if os.path.exists(HIGH_CONFIDENCE_CSV):
        df = pd.read_csv(HIGH_CONFIDENCE_CSV)
        doc_findings = df[df['Document'] == document_id]
        
        if not doc_findings.empty:
            # Sort by confidence
            doc_findings = doc_findings.sort_values('Confidence', ascending=False)
            relevant_pages = doc_findings['Page'].unique().tolist()
            
            print(f"Found {len(relevant_pages)} relevant pages in high confidence findings")
            return relevant_pages[:3]  # Return top 3 pages
    
    # If no high confidence findings, check if we have a JSON analysis file
    analysis_path = glob.glob(os.path.join(FINDINGS_DIR, document_id, f"{document_id}-analysis.json"))
    if analysis_path and os.path.exists(analysis_path[0]):
        try:
            with open(analysis_path[0], 'r') as f:
                analysis = json.load(f)
            
            # Look for pages with high relevance scores
            relevant_pages = []
            for page in analysis:
                if page.get('overall_page_relevance', 0) >= 5:
                    relevant_pages.append((page.get('page_number'), page.get('overall_page_relevance', 0)))
            
            # Sort by relevance score, highest first
            relevant_pages.sort(key=lambda x: x[1], reverse=True)
            
            if relevant_pages:
                print(f"Found {len(relevant_pages)} relevant pages in analysis JSON")
                return [p[0] for p in relevant_pages[:3]]  # Return top 3 pages
        except Exception as e:
            print(f"Error reading analysis file: {e}")
    
    print("No relevant pages found, will use page 1")
    return [1]  # Default to page 1 if nothing else found

def create_focused_prompt(document_id, page_num, previous_findings=None):
    """Create a focused prompt for analyzing a specific document page"""
    context = ""
    if previous_findings:
        context = f"""
PREVIOUS ANALYSIS:
The following information was previously extracted from this document:
{previous_findings}

Use this as context, but conduct your own independent analysis. Feel free to correct, expand, or disagree with the previous analysis.
"""

    prompt = f"""Analyze this JFK assassination document with the utmost attention to detail and historical context.

DOCUMENT ID: {document_id}
PAGE NUMBER: {page_num}
{context}

CRITICAL ANALYSIS DIRECTIVES:
1. Look for names, dates, locations, and operational details that might connect to the Kennedy assassination
2. Pay special attention to any mentions of Lee Harvey Oswald, Jack Ruby, CIA, FBI, Cuba, Mexico City, or the Soviet Union
3. Identify any inconsistencies with the official Warren Commission narrative
4. Note any coded language, euphemisms, or intelligence jargon that might obscure the true meaning
5. Analyze any redactions or obscured information - what might be hidden and why?
6. Consider the document's authenticity, provenance, and chain of custody
7. Evaluate whether this document reveals new avenues for investigation

FOCUS ON EXTRACTING ACTIONABLE INTELLIGENCE:
- What new facts does this document establish?
- What connections between people or events does it reveal?
- What timeline information can be established?
- What might this document mean in the broader context of the assassination?
- If significant, why hasn't this information been more widely publicized?

I NEED YOUR RESPONSE AS A VALID, PARSEABLE JSON OBJECT with the following structure:

{{
  "document_id": "{document_id}",
  "page_number": {page_num},
  "visible_content": "Brief summary of what is physically visible on the page",
  "document_type": "Memo/Report/Cable/etc",
  "date_of_document": "Date if visible",
  "classification_level": "Any security classification visible",
  "analysis": {{
    "key_facts": [
      "List each concrete fact established by the document"
    ],
    "entities_identified": [
      {{
        "name": "Person's name",
        "position": "Their role/job",
        "significance": "Why they matter to the investigation"
      }}
    ],
    "connections_uncovered": [
      {{
        "connection": "Description of relationship or link between entities",
        "evidence_quality": "How clearly this is established (speculative vs. explicit)",
        "significance": "Why this connection matters"
      }}
    ],
    "alternative_interpretations": [
      "Different ways this document could be interpreted"
    ],
    "contradictions_with_official_narrative": [
      "Specific ways this contradicts the Warren Commission findings"
    ],
    "redacted_content_assessment": "Analysis of what might be in redacted portions",
    "credibility_assessment": "How reliable this document appears to be",
    "historical_significance": "Overall significance to understanding the assassination",
    "additional_research_needed": [
      "Specific follow-up investigations this document suggests"
    ],
    "most_important_finding": "The single most important revelation from this document"
  }}
}}

IMPORTANT: Base your analysis solely on what you can see in this document. While you can reference historical context, do not invent details or connections not supported by visible evidence. If this document appears mundane with no connection to the assassination, state this clearly.

CRITICALLY IMPORTANT: YOUR ENTIRE RESPONSE MUST BE VALID JSON AND NOTHING ELSE. NO text before or after the JSON. NO markdown code fences. ONLY return the JSON object.
"""
    return prompt

def get_previous_findings(document_id, page_num):
    """Get previous findings about this document to provide context"""
    # Check high confidence findings CSV
    if os.path.exists(HIGH_CONFIDENCE_CSV):
        df = pd.read_csv(HIGH_CONFIDENCE_CSV)
        page_findings = df[(df['Document'] == document_id) & (df['Page'] == page_num)]
        
        if not page_findings.empty:
            findings = []
            for _, row in page_findings.iterrows():
                finding = f"- {row['Description']}"
                if row['Quote'] != "N/A":
                    finding += f" Quote: '{row['Quote']}'"
                findings.append(finding)
            
            return "\n".join(findings)
    
    # Check if we have a detailed analysis JSON
    analysis_files = glob.glob(os.path.join("output_final_*", f"{document_id}_page{page_num}.json"))
    if analysis_files:
        most_recent = max(analysis_files, key=os.path.getctime)
        try:
            with open(most_recent, 'r') as f:
                analysis = json.load(f)
            
            findings = []
            for finding in analysis.get("analysis", {}).get("key_findings", []):
                findings.append(f"- {finding.get('finding', '')}")
            
            if findings:
                return "\n".join(findings)
        except Exception as e:
            print(f"Error reading previous detailed analysis: {e}")
    
    return None

def analyze_document_page(document_id, page_num):
    """Process a specific document page with Claude 3.7 Sonnet"""
    try:
        # Find the PDF file
        pdf_path = find_pdf_file(document_id)
        if not pdf_path:
            print(f"Could not find PDF for document {document_id}")
            return None
        
        # Extract the page as an image
        image = extract_page_from_pdf(pdf_path, page_num)
        if not image:
            print(f"Could not extract page {page_num} from {pdf_path}")
            return None
        
        # Get previous findings about this document/page if available
        previous_findings = get_previous_findings(document_id, page_num)
        
        # Convert image to base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Create the focused prompt
        prompt = create_focused_prompt(document_id, page_num, previous_findings)
        
        # Call Claude API
        print(f"Analyzing {document_id} page {page_num} with Claude 3.7 Sonnet...")
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
                }
            ]
        )
        
        # Get the response
        response_text = response.content[0].text.strip()
        
        # Save the raw response for debugging
        raw_output_path = os.path.join(OUTPUT_DIR, f"{document_id}_page{page_num}_raw.txt")
        with open(raw_output_path, 'w') as f:
            f.write(response_text)
        
        # Try to parse as JSON
        try:
            # Try direct parsing first
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try to extract JSON from the response
                # Look for JSON content between ```json and ``` markers
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                
                if json_match:
                    json_content = json_match.group(1)
                    result = json.loads(json_content)
                else:
                    # Try to find the JSON object using regex
                    json_pattern = r'(\{\s*"document_id"\s*:.*?\}\s*\})'
                    json_match = re.search(json_pattern, response_text, re.DOTALL)
                    
                    if json_match:
                        json_content = json_match.group(1)
                        result = json.loads(json_content)
                    else:
                        # If all parsing attempts fail, create a minimal JSON structure
                        print(f"All JSON parsing failed, creating fallback result")
                        result = {
                            "document_id": document_id,
                            "page_number": page_num,
                            "visible_content": "JSON parsing failed. See raw response.",
                            "analysis": {
                                "key_facts": ["JSON parsing failed. See raw response."],
                                "most_important_finding": "JSON parsing failed. See raw response."
                            }
                        }
            
            # Save to output directory
            output_path = os.path.join(OUTPUT_DIR, f"{document_id}_page{page_num}.json")
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            print(f"Error processing JSON response: {e}")
            return None
        
    except Exception as e:
        print(f"Error analyzing document: {e}")
        return None

def format_analysis_for_display(analysis):
    """Format the analysis results for display in the terminal"""
    if not analysis:
        return "No analysis results available."
    
    display = f"ANALYSIS OF DOCUMENT {analysis.get('document_id', 'unknown')} PAGE {analysis.get('page_number', 'unknown')}\n"
    display += "=" * 80 + "\n\n"
    
    display += f"DOCUMENT TYPE: {analysis.get('document_type', 'Unknown')}\n"
    display += f"DATE: {analysis.get('date_of_document', 'Unknown')}\n"
    display += f"CLASSIFICATION: {analysis.get('classification_level', 'Unknown')}\n\n"
    
    display += "VISIBLE CONTENT:\n"
    display += f"{analysis.get('visible_content', 'Not provided')}\n\n"
    
    analysis_data = analysis.get('analysis', {})
    
    display += "KEY FACTS:\n"
    for fact in analysis_data.get('key_facts', []):
        display += f"- {fact}\n"
    display += "\n"
    
    display += "ENTITIES IDENTIFIED:\n"
    for entity in analysis_data.get('entities_identified', []):
        display += f"- {entity.get('name', 'Unknown')}: {entity.get('position', 'Unknown position')}\n"
        display += f"  Significance: {entity.get('significance', 'Unknown')}\n"
    display += "\n"
    
    display += "CONNECTIONS UNCOVERED:\n"
    for connection in analysis_data.get('connections_uncovered', []):
        display += f"- {connection.get('connection', 'Unknown connection')}\n"
        display += f"  Evidence quality: {connection.get('evidence_quality', 'Unknown')}\n"
        display += f"  Significance: {connection.get('significance', 'Unknown')}\n"
    display += "\n"
    
    if analysis_data.get('contradictions_with_official_narrative'):
        display += "CONTRADICTIONS WITH OFFICIAL NARRATIVE:\n"
        for contradiction in analysis_data.get('contradictions_with_official_narrative', []):
            display += f"- {contradiction}\n"
        display += "\n"
    
    display += "ALTERNATIVE INTERPRETATIONS:\n"
    for interpretation in analysis_data.get('alternative_interpretations', []):
        display += f"- {interpretation}\n"
    display += "\n"
    
    if analysis_data.get('redacted_content_assessment'):
        display += f"REDACTED CONTENT ASSESSMENT:\n{analysis_data.get('redacted_content_assessment')}\n\n"
    
    display += f"CREDIBILITY ASSESSMENT:\n{analysis_data.get('credibility_assessment', 'Not provided')}\n\n"
    
    display += f"HISTORICAL SIGNIFICANCE:\n{analysis_data.get('historical_significance', 'Not provided')}\n\n"
    
    display += "ADDITIONAL RESEARCH NEEDED:\n"
    for research in analysis_data.get('additional_research_needed', []):
        display += f"- {research}\n"
    display += "\n"
    
    display += f"MOST IMPORTANT FINDING:\n{analysis_data.get('most_important_finding', 'Not provided')}\n"
    
    return display

def main():
    parser = argparse.ArgumentParser(description="Analyze a specific JFK document with Claude 3.7 Sonnet")
    parser.add_argument("document_id", help="Document ID to analyze (e.g., 104-10332-10023)")
    parser.add_argument("--page", "-p", type=int, help="Specific page number to analyze")
    parser.add_argument("--all-pages", "-a", action="store_true", help="Analyze all relevant pages")
    parser.add_argument("--output-dir", "-o", help="Custom output directory")
    
    args = parser.parse_args()
    
    # Set output directory
    global OUTPUT_DIR
    if args.output_dir:
        OUTPUT_DIR = args.output_dir
    
    ensure_dir(OUTPUT_DIR)
    print(f"Results will be saved to {OUTPUT_DIR}")
    
    # Determine which pages to analyze
    pages_to_analyze = []
    if args.page is not None:
        pages_to_analyze = [args.page]
        print(f"Will analyze page {args.page} as specified")
    else:
        relevant_pages = find_relevant_pages(args.document_id)
        if args.all_pages:
            pages_to_analyze = relevant_pages
            print(f"Will analyze all {len(relevant_pages)} relevant pages")
        else:
            # If no specific page and not all pages, just do the most relevant page
            pages_to_analyze = [relevant_pages[0]] if relevant_pages else [1]
            print(f"Will analyze the most relevant page {pages_to_analyze[0]}")
    
    # Analyze each selected page
    results = []
    for page in pages_to_analyze:
        result = analyze_document_page(args.document_id, page)
        if result:
            results.append(result)
            # Display a summary of the analysis
            print("\n" + format_analysis_for_display(result))
    
    if results:
        print(f"\nAnalysis complete! {len(results)} pages analyzed.")
        print(f"Full results saved to {OUTPUT_DIR}")
    else:
        print("No results generated. Please check for errors.")

if __name__ == "__main__":
    main() 