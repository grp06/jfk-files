import os
import csv
import glob
import json
import pandas as pd
import anthropic
import pdf2image
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import time
from tqdm import tqdm
import base64
import io
from datetime import datetime
import re

# Load environment variables
load_dotenv()

# Configuration
PDF_DIR = "jfk_pdfs"  # Directory containing original PDFs
CSV_FILE = "output_20250318_180803/high_confidence_findings.csv"  # Your high confidence findings CSV
OUTPUT_DIR = f"output_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  # Output directory

# Claude 3.7 Sonnet API configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-3-7-sonnet-20250219"  # Using the most powerful model for the deep analysis

# Minimum confidence score to consider for reanalysis
MIN_CONFIDENCE = 7

# Key categories of special interest
PRIORITY_CATEGORIES = [
    "OSWALD_ASSOCIATIONS",
    "AUTOPSY_MEDICAL_EVIDENCE",
    "WITNESS_TESTIMONIES",
    "CIA_FBI_ACTIVITIES",
    "SURVEILLANCE_RECORDS",
    "TRAVEL_FINANCIAL_RECORDS"
]

# Key entities to highlight connections between
KEY_ENTITIES = [
    "Lee Harvey Oswald", "Jack Ruby", "CIA", "FBI", "KGB", "Warren Commission",
    "Cuba", "Soviet", "Mexico City", "Carlos Marcello", "grassy knoll"
]

def ensure_dir(directory):
    """Create directory if it doesn't exist"""
    os.makedirs(directory, exist_ok=True)

def load_high_confidence_findings():
    """Load and filter the high confidence findings CSV"""
    print(f"Loading high confidence findings from {CSV_FILE}")
    
    # Read the CSV file
    df = pd.read_csv(CSV_FILE)
    
    # Convert confidence to numeric
    df['Confidence'] = pd.to_numeric(df['Confidence'])
    
    # Filter for high confidence entries
    df = df[df['Confidence'] >= MIN_CONFIDENCE]
    
    # Give priority to certain categories
    df['Priority'] = df['Category'].apply(lambda x: 2 if x in PRIORITY_CATEGORIES else 1)
    
    # Give additional priority to entries with entity mentions or relationships
    df['HasEntities'] = df['Entities'].apply(lambda x: 0 if pd.isna(x) or x == '' else len(str(x).split('|')))
    df['Priority'] += df['HasEntities']
    
    # Add relationship priority if the "Has Relationship" column is "Yes"
    if 'Has Relationship' in df.columns:
        df['Priority'] += df['Has Relationship'].apply(lambda x: 3 if x == 'Yes' else 0)
    
    # Sort by priority (highest first) and then by confidence
    df = df.sort_values(by=['Priority', 'Confidence'], ascending=False)
    
    print(f"Found {len(df)} high confidence findings to analyze")
    return df

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
        # Adjust page number (CSV might use 1-indexing while pdf2image uses 0-indexing)
        # Also handle cases where page_num might be a string
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

def create_enhanced_prompt(document_id, page_num, category, confidence, description, quote, entities):
    """Create an enhanced analysis prompt for Claude 3.7 Sonnet"""
    # Build a detailed prompt that encourages critical analysis
    prompt = f"""Analyze this JFK assassination document page with the utmost attention to detail, historical context, and investigative significance.

DOCUMENT METADATA:
- Document ID: {document_id}
- Page Number: {page_num}
- Category: {category}
- Initial Confidence Score: {confidence}/10
- Initial Analysis: {description}
- Direct Quote: {quote if quote and quote != 'N/A' else 'None provided'}
- Key Entities Identified: {entities if entities and entities != 'nan' else 'None specifically identified'}

ANALYSIS OBJECTIVES:
1. EVIDENCE EVALUATION
   - Assess the credibility and significance of information on this page
   - Identify specific names, dates, locations, and concrete details
   - Note any inconsistencies with the official Warren Commission narrative
   - Evaluate if this represents primary evidence or hearsay/speculation

2. CONNECTION MAPPING
   - Identify relationships between people, organizations, and events mentioned
   - Connect this information to other known aspects of the JFK assassination
   - Note potential links to organized crime, intelligence agencies, or foreign governments
   - Identify chains of custody or information pathways

3. CODED LANGUAGE & REDACTIONS
   - Interpret any intelligence jargon, code names, or euphemisms
   - Analyze the significance of any redactions or obscured information
   - Consider what might be deliberately omitted or concealed
   - Look for patterns in partial information that suggest larger contexts

4. HISTORICAL SIGNIFICANCE
   - Evaluate how this information might change our understanding of the assassination
   - Consider whether this supports or contradicts specific conspiracy theories
   - Assess whether this provides new avenues for investigation
   - Determine what verifiable follow-up questions this evidence raises

5. SYNTHESIS
   - Provide your expert assessment of what this document actually reveals
   - Assign a new confidence score (1-10) for the document's relevance to understanding the assassination
   - Identify the most important takeaway from this page
   - If you believe this document contains genuinely significant information about the assassination, explicitly state why

I NEED YOUR RESPONSE AS A VALID, PARSEABLE JSON OBJECT. DO NOT include any text, explanations or markdown formatting outside the JSON structure. The response MUST be a single, complete, valid JSON object.

JSON RESPONSE FORMAT:
{{
  "document_id": "{document_id}",
  "page_number": {page_num},
  "category": "{category}",
  "analysis": {{
    "key_findings": [
      {{
        "finding": "Brief description of finding",
        "significance": "Why this matters to the investigation",
        "credibility": 1-10,
        "corroboration_needed": "What would help verify this information"
      }}
    ],
    "entities_identified": [
      {{
        "name": "Person or organization name",
        "role": "Their connection to events",
        "significance": "Why they matter"
      }}
    ],
    "connections_uncovered": [
      {{
        "connection": "Description of relationship or link",
        "significance": "Why this connection matters",
        "confidence": 1-10
      }}
    ],
    "timeline_placement": "Where this fits chronologically",
    "contradictions_with_official_narrative": [
      "List specific contradictions with Warren Commission findings"
    ],
    "consistency_assessment": "How internally consistent the information is",
    "expert_interpretation": "Your overall analysis of what this document actually reveals",
    "new_confidence_score": 1-10,
    "actionable_insights": [
      "List of follow-up questions or investigative leads this raises"
    ],
    "most_important_takeaway": "Single most important insight from this document"
  }}
}}

IMPORTANT: Base your analysis solely on what you can see in this document. While you can reference known historical context, do not invent details or connections not supported by the visible evidence. Be critical and skeptical, but also open to identifying genuinely significant information. If the document appears mundane or administrative with no connection to the assassination, state this clearly.

CRITICALLY IMPORTANT: YOUR ENTIRE RESPONSE MUST BE VALID JSON AND NOTHING ELSE. DO NOT include any text before or after the JSON. DO NOT use markdown code fences (```). ONLY return the JSON object.
"""
    return prompt

def analyze_document_page(row):
    """Process a single high-confidence document page with Claude 3.7 Sonnet"""
    try:
        document_id = row['Document']
        page_num = row['Page']
        category = row['Category']
        confidence = row['Confidence']
        description = row['Description']
        quote = row['Quote']
        entities = row['Entities']
        
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
        
        # Convert image to base64
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Create the enhanced prompt
        prompt = create_enhanced_prompt(document_id, page_num, category, confidence, description, quote, entities)
        
        # Call Claude API
        print(f"Analyzing {document_id} page {page_num}")
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
        raw_output_dir = os.path.join(OUTPUT_DIR, "raw_responses")
        ensure_dir(raw_output_dir)
        raw_output_path = os.path.join(raw_output_dir, f"{document_id}_page{page_num}_raw.txt")
        with open(raw_output_path, 'w') as f:
            f.write(response_text)
        
        # Try to fix and parse as JSON
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
                        print(f"All JSON parsing failed for {document_id} page {page_num}, creating fallback result")
                        result = {
                            "document_id": document_id,
                            "page_number": page_num,
                            "category": category,
                            "analysis": {
                                "key_findings": [{
                                    "finding": "Analysis generated but not in valid JSON format. See raw response.",
                                    "significance": "Raw analysis may contain useful information.",
                                    "credibility": 5,
                                    "corroboration_needed": "Manual review of raw output required"
                                }],
                                "entities_identified": [],
                                "connections_uncovered": [],
                                "timeline_placement": "Unknown",
                                "contradictions_with_official_narrative": [],
                                "consistency_assessment": "Unable to assess",
                                "expert_interpretation": "JSON parsing failed, see raw output.",
                                "new_confidence_score": 5,
                                "actionable_insights": ["Review raw output manually"],
                                "most_important_takeaway": "JSON parsing failed, see raw output"
                            }
                        }
            
            # Save to output directory
            output_path = os.path.join(OUTPUT_DIR, f"{document_id}_page{page_num}.json")
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            
            # If this is a high confidence result, also save to a separate directory
            new_confidence = result.get("analysis", {}).get("new_confidence_score", 0)
            if new_confidence >= 8:
                significant_dir = os.path.join(OUTPUT_DIR, "significant_findings")
                ensure_dir(significant_dir)
                with open(os.path.join(significant_dir, f"{document_id}_page{page_num}.json"), 'w') as f:
                    json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            print(f"Error processing JSON response for {document_id} page {page_num}: {e}")
            # Still return a minimal result so the pipeline doesn't break
            return {
                "document_id": document_id,
                "page_number": page_num,
                "category": category,
                "analysis": {
                    "key_findings": [{
                        "finding": f"Exception during JSON processing: {str(e)}",
                        "significance": "Error occurred during analysis",
                        "credibility": 1,
                        "corroboration_needed": "Manual review of raw output required"
                    }],
                    "entities_identified": [],
                    "connections_uncovered": [],
                    "new_confidence_score": 1
                }
            }
        
    except Exception as e:
        print(f"Error analyzing {row['Document']} page {row['Page']}: {e}")
        return None

def process_findings(df, max_workers=4, max_documents=50):
    """Process the filtered findings with multiple workers"""
    ensure_dir(OUTPUT_DIR)
    
    # Limit to max_documents if specified
    if max_documents > 0 and len(df) > max_documents:
        print(f"Limiting analysis to top {max_documents} documents")
        df = df.head(max_documents)
    
    results = []
    
    # Process documents in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_row = {executor.submit(analyze_document_page, row): row for _, row in df.iterrows()}
        
        for future in tqdm(future_to_row, total=len(future_to_row), desc="Analyzing documents"):
            row = future_to_row[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error processing {row['Document']} page {row['Page']}: {e}")
    
    return results

def generate_summary_report(results):
    """Generate a summary report of the enhanced analysis"""
    if not results:
        print("No results to summarize")
        return
    
    # Create a summary by category
    categories = {}
    significant_findings = []
    entities = {}
    connections = []
    
    for result in results:
        try:
            document_id = result.get("document_id", "unknown")
            page_num = result.get("page_number", "unknown")
            category = result.get("category", "unknown")
            analysis = result.get("analysis", {})
            
            # Add to category summary
            if category not in categories:
                categories[category] = []
            
            # Add key findings
            for finding in analysis.get("key_findings", []):
                if finding.get("credibility", 0) >= 7:
                    categories[category].append({
                        "document": document_id,
                        "page": page_num,
                        "finding": finding.get("finding", ""),
                        "significance": finding.get("significance", ""),
                        "credibility": finding.get("credibility", 0)
                    })
                    
                    # Add to significant findings if credibility is high
                    if finding.get("credibility", 0) >= 8:
                        significant_findings.append({
                            "document": document_id,
                            "page": page_num,
                            "category": category,
                            "finding": finding.get("finding", ""),
                            "significance": finding.get("significance", ""),
                            "credibility": finding.get("credibility", 0)
                        })
            
            # Add entities
            for entity in analysis.get("entities_identified", []):
                entity_name = entity.get("name", "unknown")
                if entity_name not in entities:
                    entities[entity_name] = []
                
                entities[entity_name].append({
                    "document": document_id,
                    "page": page_num,
                    "role": entity.get("role", ""),
                    "significance": entity.get("significance", "")
                })
            
            # Add connections
            for connection in analysis.get("connections_uncovered", []):
                if connection.get("confidence", 0) >= 7:
                    connections.append({
                        "document": document_id,
                        "page": page_num,
                        "connection": connection.get("connection", ""),
                        "significance": connection.get("significance", ""),
                        "confidence": connection.get("confidence", 0)
                    })
        
        except Exception as e:
            print(f"Error processing result: {e}")
    
    # Generate the report
    report = "JFK ASSASSINATION DOCUMENT ANALYSIS - ENHANCED FINDINGS\n"
    report += "=" * 80 + "\n\n"
    report += f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"Documents Analyzed: {len(results)}\n\n"
    
    # Most significant findings
    report += "MOST SIGNIFICANT FINDINGS\n"
    report += "-" * 50 + "\n"
    for i, finding in enumerate(sorted(significant_findings, key=lambda x: x["credibility"], reverse=True), 1):
        report += f"{i}. [{finding['document']}, Page {finding['page']}] ({finding['category']})\n"
        report += f"   {finding['finding']}\n"
        report += f"   Significance: {finding['significance']}\n"
        report += f"   Credibility: {finding['credibility']}/10\n\n"
    
    # Key connections
    report += "\nKEY CONNECTIONS UNCOVERED\n"
    report += "-" * 50 + "\n"
    for i, connection in enumerate(sorted(connections, key=lambda x: x["confidence"], reverse=True), 1):
        report += f"{i}. [{connection['document']}, Page {connection['page']}]\n"
        report += f"   {connection['connection']}\n"
        report += f"   Significance: {connection['significance']}\n"
        report += f"   Confidence: {connection['confidence']}/10\n\n"
    
    # Important entities
    report += "\nKEY ENTITIES AND THEIR ROLES\n"
    report += "-" * 50 + "\n"
    for entity_name, instances in sorted(entities.items(), key=lambda x: len(x[1]), reverse=True):
        if len(instances) >= 2:  # Only show entities that appear in multiple documents
            report += f"{entity_name}:\n"
            for instance in instances[:5]:  # Limit to 5 instances per entity
                report += f"   - [{instance['document']}, Page {instance['page']}] {instance['role']}\n"
            report += "\n"
    
    # Findings by category
    report += "\nFINDINGS BY CATEGORY\n"
    report += "-" * 50 + "\n"
    for category, findings in sorted(categories.items()):
        if findings:
            report += f"\n{category}:\n"
            report += "." * 40 + "\n"
            
            # Sort by credibility
            sorted_findings = sorted(findings, key=lambda x: x["credibility"], reverse=True)
            
            for i, finding in enumerate(sorted_findings[:5], 1):  # Top 5 per category
                report += f"{i}. [{finding['document']}, Page {finding['page']}] (Credibility: {finding['credibility']}/10)\n"
                report += f"   {finding['finding']}\n"
                report += f"   Significance: {finding['significance']}\n\n"
    
    # Save the report
    report_path = os.path.join(OUTPUT_DIR, "enhanced_analysis_summary.txt")
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"Summary report generated: {report_path}")
    return report

def main():
    """Main function to process high confidence findings with enhanced analysis"""
    print("Starting enhanced analysis of high confidence JFK document findings")
    
    # Load and filter the high confidence findings
    df = load_high_confidence_findings()
    
    # Process the findings with Claude 3.7 Sonnet - limit to top 5 documents
    results = process_findings(df, max_workers=4, max_documents=5)
    
    # Generate summary report
    if results:
        generate_summary_report(results)
        print(f"Analysis complete! Results saved to {OUTPUT_DIR}")
    else:
        print("No results generated. Please check for errors.")

if __name__ == "__main__":
    main()
