import os
import re
import glob
import json
from collections import Counter, defaultdict
import argparse
import csv
from datetime import datetime

# Config
DEFAULT_OUTPUT_DIR = "output"  # Default to original directory
MIN_CONFIDENCE = 6  # Minimum confidence level to consider "interesting"
MIN_RELEVANCE = 5   # Minimum page relevance to consider "interesting"
DEBUG = False  # Enable debugging output

# Important entities to track
KEY_ENTITIES = [
    "Lee Harvey Oswald", "Jack Ruby", "CIA", "FBI", "KGB", "Warren Commission", 
    "Carlos Marcello", "Sam Giancana", "Santo Trafficante", "Cuba", "Soviet",
    "Mexico City", "New Orleans", "Dallas", "Dealey Plaza", "grassy knoll"
]

# Connections between entities to track
ENTITY_RELATIONSHIPS = [
    "met with", "worked for", "communicated with", "traveled to", 
    "received money from", "surveilled by", "trained by", "killed",
    "connected to", "associated with"
]

def get_latest_output_dir():
    """Find the most recent output directory based on timestamp in name"""
    output_dirs = glob.glob("output_*")
    if not output_dirs:
        return DEFAULT_OUTPUT_DIR
    
    # Sort by name (timestamp) in descending order
    output_dirs.sort(reverse=True)
    return output_dirs[0]

def parse_args():
    """Parse command line arguments"""
    global MIN_CONFIDENCE, MIN_RELEVANCE, DEBUG
    
    parser = argparse.ArgumentParser(description="Analyze JFK document analysis results")
    parser.add_argument("--output", "-o", 
                        help="Output directory to analyze (default: most recent)")
    parser.add_argument("--min-confidence", type=int, default=MIN_CONFIDENCE,
                        help=f"Minimum confidence level (1-10, default: {MIN_CONFIDENCE})")
    parser.add_argument("--min-relevance", type=int, default=MIN_RELEVANCE,
                        help=f"Minimum page relevance (1-10, default: {MIN_RELEVANCE})")
    parser.add_argument("--format", choices=["txt", "json", "csv", "all"], default="all",
                        help="Output format(s) for findings (default: all)")
    parser.add_argument("--category", 
                        help="Filter results to specific category")
    parser.add_argument("--entity", 
                        help="Filter results to mentions of specific entity")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug output")
    parser.add_argument("--connections-only", action="store_true",
                        help="Only show findings that establish connections between entities")
    args = parser.parse_args()
    
    # If no output directory specified, use most recent
    if not args.output:
        args.output = get_latest_output_dir()
        print(f"No output directory specified, using: {args.output}")
    
    # Update global config based on args
    MIN_CONFIDENCE = args.min_confidence
    MIN_RELEVANCE = args.min_relevance
    DEBUG = args.debug
    
    return args

def get_analysis_files(output_dir):
    """Get all analysis.json files in output folders"""
    analysis_files = glob.glob(os.path.join(output_dir, "*", "*-analysis.json"))
    return analysis_files

def extract_entities(text):
    """Extract key entities mentioned in text"""
    found_entities = []
    for entity in KEY_ENTITIES:
        if re.search(r'\b' + re.escape(entity) + r'\b', text, re.IGNORECASE):
            found_entities.append(entity)
    return found_entities

def extract_relationships(text):
    """Extract relationships between entities in text"""
    relationships = []
    
    # First find all entities in the text
    entities = extract_entities(text)
    
    if len(entities) < 2:
        return []  # Need at least 2 entities to have a relationship
    
    # Look for relationship patterns
    for relationship in ENTITY_RELATIONSHIPS:
        for entity1 in entities:
            for entity2 in entities:
                if entity1 != entity2:
                    pattern = f"{entity1}.*{relationship}.*{entity2}"
                    reverse_pattern = f"{entity2}.*{relationship}.*{entity1}"
                    
                    if re.search(pattern, text, re.IGNORECASE) or re.search(reverse_pattern, text, re.IGNORECASE):
                        relationships.append((entity1, relationship, entity2))
    
    return relationships

def analyze_document(file_path):
    """Analyze a JSON analysis file for interesting content"""
    with open(file_path, 'r') as f:
        content = json.load(f)
    
    # Get document name from path
    doc_name = os.path.basename(os.path.dirname(file_path))
    
    # Extract key indicators of "interesting" content
    results = {
        "document": doc_name,
        "file_path": file_path,
        "categories": set(),
        "high_confidence_findings": [],  # Store actual findings for reporting
        "relevant_pages": [],
        "has_quotes": False,
        "entity_mentions": defaultdict(int),  # Count entity mentions
        "relationships": [],  # Store relationship tuples
        "evidence_type": set(),  # Types of evidence (document, testimony, photo, etc)
        "relevance_score": 0
    }
    
    # Debug: Print document ID
    if DEBUG:
        print(f"\nDEBUG: Analyzing {doc_name}")
        print(f"JSON contains {len(content)} pages")
    
    total_findings = 0
    
    # Process each page in the document
    for page in content:
        page_num = page.get("page_number", "unknown")
        page_relevance = page.get("overall_page_relevance", 0)
        
        # Track relevant pages
        if page_relevance >= MIN_RELEVANCE:
            results["relevant_pages"].append((page_num, page_relevance))
            if DEBUG:
                print(f"Found relevant page: {page_num} with score {page_relevance}")
        
        # Process findings on this page
        findings = page.get("relevant_findings", [])
        total_findings += len(findings)
        
        for finding in findings:
            category = finding.get("category", "").upper()
            confidence = finding.get("confidence", 0)
            description = finding.get("description", "")
            quote = finding.get("direct_quote", "N/A")
            significance = finding.get("significance", "")
            
            # Combine text for entity extraction
            all_text = f"{description} {quote} {significance}"
            
            # Add category to the set
            if category:
                results["categories"].add(category)
                if DEBUG:
                    print(f"Found category: {category}")
            
            # Extract and track entities
            entities = extract_entities(all_text)
            for entity in entities:
                results["entity_mentions"][entity] += 1
            
            # Extract and track relationships
            relationships = extract_relationships(all_text)
            for rel in relationships:
                results["relationships"].append({
                    "source": rel[0],
                    "relationship": rel[1],
                    "target": rel[2],
                    "page": page_num,
                    "confidence": confidence,
                    "category": category,
                    "description": description,
                    "quote": quote
                })
            
            # Determine evidence type from category and description
            if "DOCUMENT" in category or "memo" in description.lower() or "report" in description.lower():
                results["evidence_type"].add("document")
            if "WITNESS" in category or "testimony" in description.lower() or "statement" in description.lower():
                results["evidence_type"].add("testimony")
            if "PHOTO" in category or "photograph" in description.lower() or "image" in description.lower():
                results["evidence_type"].add("photograph")
            if "AUTOPSY" in category or "medical" in description.lower():
                results["evidence_type"].add("medical")
            
            # Check for high confidence findings
            if confidence >= MIN_CONFIDENCE:
                results["high_confidence_findings"].append({
                    "page": page_num,
                    "category": category,
                    "confidence": confidence,
                    "description": description,
                    "quote": quote,
                    "significance": significance,
                    "entities": entities,
                    "relationships": relationships
                })
                if DEBUG:
                    print(f"Found high confidence finding ({confidence}/10): {category}")
            
            # Check for quotes
            if quote and quote != "N/A":
                results["has_quotes"] = True
    
    # Calculate an overall "interestingness" score with new metrics
    relevance_score = (
        len(results["categories"]) * 3 +                # Each category adds 3 points
        len(results["high_confidence_findings"]) * 5 +  # Each high confidence finding adds 5 points
        len(results["relevant_pages"]) * 2 +            # Each relevant page adds 2 point
        (5 if results["has_quotes"] else 0) +           # Having quotes adds 5 points
        sum(results["entity_mentions"].values()) +      # Each entity mention adds 1 point
        len(results["relationships"]) * 10 +            # Each relationship adds 10 points (very significant)
        len(results["evidence_type"]) * 3 +             # Each type of evidence adds 3 points
        (total_findings * 1)                            # Each finding adds 1 point
    )
    
    results["relevance_score"] = relevance_score
    
    if DEBUG:
        print(f"Final score for {doc_name}: {relevance_score}")
        print(f"Categories found: {results['categories']}")
        print(f"High confidence findings: {len(results['high_confidence_findings'])}")
        print(f"Entity mentions: {dict(results['entity_mentions'])}")
        print(f"Relationships found: {len(results['relationships'])}")
    
    return results

def filter_results(analysis_results, args):
    """Filter results based on command-line arguments"""
    filtered_results = analysis_results.copy()
    
    # Filter by category if specified
    if args.category:
        filtered_results = [
            r for r in filtered_results 
            if args.category.upper() in r["categories"]
        ]
    
    # Filter by entity if specified
    if args.entity:
        filtered_results = [
            r for r in filtered_results 
            if args.entity in r["entity_mentions"] and r["entity_mentions"][args.entity] > 0
        ]
    
    # Filter to only show documents with relationship findings
    if args.connections_only:
        filtered_results = [
            r for r in filtered_results 
            if len(r["relationships"]) > 0
        ]
    
    return filtered_results

def rank_documents(analysis_results):
    """Rank documents by interestingness"""
    return sorted(analysis_results, key=lambda x: x["relevance_score"], reverse=True)

def generate_knowledge_graph(findings, output_dir):
    """Generate knowledge graph data for visualization"""
    nodes = set()
    edges = []
    
    # Process all relationships across all documents
    for finding in findings:
        for relationship in finding["relationships"]:
            source = relationship["source"]
            target = relationship["target"]
            rel_type = relationship["relationship"]
            confidence = relationship["confidence"]
            document = finding["document"]
            
            nodes.add(source)
            nodes.add(target)
            
            edges.append({
                "source": source,
                "target": target,
                "type": rel_type,
                "confidence": confidence,
                "document": document,
                "category": relationship["category"],
                "description": relationship["description"]
            })
    
    # Convert nodes to list of dicts
    node_list = [{"id": node, "group": 1} for node in nodes]
    
    # Save as JSON for visualization
    graph_data = {
        "nodes": node_list,
        "links": edges
    }
    
    graph_path = os.path.join(output_dir, "knowledge_graph.json")
    with open(graph_path, 'w') as f:
        json.dump(graph_data, f, indent=2)
    
    print(f"Knowledge graph data saved to {graph_path}")
    return graph_data

def export_findings_csv(ranked_results, output_dir):
    """Export findings to CSV format for data analysis"""
    # Export high confidence findings
    findings_path = os.path.join(output_dir, "high_confidence_findings.csv")
    with open(findings_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Document", "Page", "Category", "Confidence", 
            "Description", "Quote", "Entities", "Has Relationship"
        ])
        
        for result in ranked_results:
            doc = result["document"]
            for finding in result["high_confidence_findings"]:
                writer.writerow([
                    doc,
                    finding["page"],
                    finding["category"],
                    finding["confidence"],
                    finding["description"],
                    finding["quote"],
                    "|".join(finding["entities"]),
                    "Yes" if finding["relationships"] else "No"
                ])
    
    # Export relationships
    relationships_path = os.path.join(output_dir, "entity_relationships.csv")
    with open(relationships_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Source Entity", "Relationship", "Target Entity", 
            "Document", "Page", "Category", "Confidence", "Description"
        ])
        
        for result in ranked_results:
            doc = result["document"]
            for rel in result["relationships"]:
                writer.writerow([
                    rel["source"],
                    rel["relationship"],
                    rel["target"],
                    doc,
                    rel["page"],
                    rel["category"],
                    rel["confidence"],
                    rel["description"]
                ])
    
    print(f"CSV exports saved to {findings_path} and {relationships_path}")

def summarize_findings(ranked_results, output_dir, args):
    """Generate a report of the most interesting documents"""
    report = "JFK DOCUMENT ANALYSIS - SIGNIFICANT FINDINGS\n"
    report += "=" * 80 + "\n\n"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report += f"Analysis generated: {timestamp}\n"
    report += f"Minimum confidence threshold: {MIN_CONFIDENCE}/10\n"
    report += f"Minimum page relevance threshold: {MIN_RELEVANCE}/10\n\n"
    
    # SECTION 1: List documents by interestingness score
    report += "DOCUMENTS RANKED BY SIGNIFICANCE:\n"
    report += "-" * 50 + "\n"
    for i, result in enumerate(ranked_results, 1):
        report += f"{i}. {result['document']} (Score: {result['relevance_score']})\n"
        report += f"   Categories: {', '.join(result['categories'])}\n"
        report += f"   Evidence types: {', '.join(result['evidence_type'])}\n"
        report += f"   High confidence findings: {len(result['high_confidence_findings'])}\n"
        report += f"   Entity connections: {len(result['relationships'])}\n"
        
        # Top 3 most mentioned entities
        top_entities = sorted(result["entity_mentions"].items(), key=lambda x: x[1], reverse=True)[:3]
        if top_entities:
            entity_str = ", ".join([f"{e[0]} ({e[1]})" for e in top_entities])
            report += f"   Top entities: {entity_str}\n"
        
        if result["relevant_pages"]:
            pages = ", ".join([f"Page {p[0]} (Relevance: {p[1]})" for p in result["relevant_pages"][:3]])
            report += f"   Key pages: {pages}\n"
        report += "\n"
    
    # SECTION 2: Entity Network - key players and their connections
    report += "\nKEY ENTITY NETWORK:\n"
    report += "-" * 50 + "\n"
    
    # Collect all entity relationships across documents
    all_relationships = []
    entity_importance = Counter()
    
    for result in ranked_results:
        for rel in result["relationships"]:
            all_relationships.append(rel)
            entity_importance[rel["source"]] += 1
            entity_importance[rel["target"]] += 1
    
    # Get top entities by connection count
    top_entities = entity_importance.most_common(10)
    
    if top_entities:
        report += "Most significant entities by connection count:\n"
        for entity, count in top_entities:
            report += f"- {entity}: {count} connections\n"
        report += "\n"
        
        # For each top entity, show its key relationships
        for entity, _ in top_entities[:5]:  # Top 5 only
            entity_rels = [r for r in all_relationships if r["source"] == entity or r["target"] == entity]
            if entity_rels:
                report += f"Connections for {entity}:\n"
                for rel in entity_rels[:5]:  # Top 5 connections per entity
                    try:
                        other = rel["target"] if rel["source"] == entity else rel["source"]
                        report += f"  - {entity} {rel['relationship']} {other} "
                        # Check if the relationship has all required keys
                        if all(key in rel for key in ['document', 'page', 'confidence']):
                            report += f"(Doc: {rel['document']}, Page: {rel['page']}, Confidence: {rel['confidence']}/10)\n"
                        else:
                            # If missing keys, provide a simplified output
                            report += "(Details incomplete)\n"
                    except KeyError as e:
                        # Skip relationships with missing keys
                        print(f"Warning: Relationship missing key {e}, skipping")
                        continue
                report += "\n"
    else:
        report += "No significant entity connections found.\n\n"
    
    # SECTION 3: Category analysis - findings by category
    report += "\nFINDINGS BY CATEGORY:\n"
    report += "-" * 50 + "\n"
    
    # Collect findings by category
    category_findings = defaultdict(list)
    for result in ranked_results:
        for finding in result["high_confidence_findings"]:
            category = finding["category"]
            category_findings[category].append({
                "document": result["document"],
                "page": finding["page"],
                "confidence": finding["confidence"],
                "description": finding["description"],
                "quote": finding["quote"],
                "entities": finding["entities"]
            })
    
    # Report on each category
    for category, findings in sorted(category_findings.items()):
        if not findings:
            continue
            
        report += f"\n{category}:\n"
        report += "." * 40 + "\n"
        report += f"Total findings: {len(findings)}\n"
        
        # Sort by confidence
        sorted_findings = sorted(findings, key=lambda x: x["confidence"], reverse=True)
        
        # Show top findings
        for i, finding in enumerate(sorted_findings[:5], 1):  # Top 5 per category
            report += f"\n  {i}. [{finding['document']}, Page {finding['page']}] (Confidence: {finding['confidence']}/10)\n"
            report += f"     {finding['description']}\n"
            if finding["quote"] != "N/A":
                report += f"     QUOTE: \"{finding['quote']}\"\n"
            if finding["entities"]:
                report += f"     ENTITIES: {', '.join(finding['entities'])}\n"
        
        report += "\n"
    
    # SECTION 4: Most significant individual findings
    report += "\nMOST SIGNIFICANT INDIVIDUAL FINDINGS:\n"
    report += "-" * 50 + "\n"
    
    # Collect all high confidence findings
    all_findings = []
    for result in ranked_results:
        for finding in result["high_confidence_findings"]:
            # Calculate finding significance score
            significance_score = (
                finding["confidence"] * 2 +  # Confidence is most important
                len(finding["entities"]) * 3 +  # More entities = more significant
                len(finding["relationships"]) * 5 +  # Relationships are very significant
                (5 if finding["quote"] != "N/A" else 0)  # Having a quote adds significance
            )
            
            all_findings.append({
                "document": result["document"],
                "page": finding["page"],
                "category": finding["category"],
                "confidence": finding["confidence"],
                "description": finding["description"],
                "quote": finding["quote"],
                "entities": finding["entities"],
                "relationships": finding["relationships"],
                "significance_score": significance_score
            })
    
    # Sort by significance score
    sorted_findings = sorted(all_findings, key=lambda x: x["significance_score"], reverse=True)
    
    # Show top 20 findings
    for i, finding in enumerate(sorted_findings[:20], 1):
        report += f"{i}. [{finding['document']}, Page {finding['page']}] "
        report += f"({finding['category']}, Confidence: {finding['confidence']}/10)\n"
        report += f"   {finding['description']}\n"
        
        if finding["quote"] != "N/A":
            report += f"   QUOTE: \"{finding['quote']}\"\n"
        
        if finding["entities"]:
            report += f"   ENTITIES: {', '.join(finding['entities'])}\n"
        
        if finding["relationships"]:
            rel_strings = []
            for rel in finding["relationships"]:
                try:
                    rel_strings.append(f"{rel[0]} {rel[1]} {rel[2]}")
                except (IndexError, KeyError, TypeError):
                    # Skip relationships with unexpected format
                    continue
            if rel_strings:
                report += f"   RELATIONSHIPS: {'; '.join(rel_strings)}\n"
        
        report += "\n"
    
    # SECTION 5: Inconsistencies with official narrative
    report += "\nPOTENTIAL INCONSISTENCIES WITH OFFICIAL NARRATIVE:\n"
    report += "-" * 50 + "\n"
    
    # Look for findings that might contradict official narrative
    narrative_keywords = [
        "contradict", "inconsistent", "contrary", "different", "conflict", 
        "alternative", "disputed", "challenged", "disprove", "refute",
        "multiple shooters", "grassy knoll", "second shooter", "conspiracy"
    ]
    
    contradicting_findings = []
    for result in ranked_results:
        for finding in result["high_confidence_findings"]:
            description = finding["description"].lower()
            quote = finding["quote"].lower() if finding["quote"] != "N/A" else ""
            combined_text = description + " " + quote
            
            # Check if any keywords appear in the text
            if any(keyword in combined_text for keyword in narrative_keywords):
                contradicting_findings.append({
                    "document": result["document"],
                    "page": finding["page"],
                    "category": finding["category"],
                    "confidence": finding["confidence"],
                    "description": finding["description"],
                    "quote": finding["quote"]
                })
    
    if contradicting_findings:
        for i, finding in enumerate(contradicting_findings, 1):
            report += f"{i}. [{finding['document']}, Page {finding['page']}] "
            report += f"({finding['category']}, Confidence: {finding['confidence']}/10)\n"
            report += f"   {finding['description']}\n"
            if finding["quote"] != "N/A":
                report += f"   QUOTE: \"{finding['quote']}\"\n"
            report += "\n"
    else:
        report += "No significant findings contradicting the official narrative were detected.\n\n"
    
    # Save the report
    report_path = os.path.join(output_dir, "significant_findings.txt")
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\nDetailed analysis report saved to {report_path}")
    return report

def export_json_findings(ranked_results, output_dir):
    """Export findings in structured JSON format"""
    
    # Structure the data hierarchically
    structured_data = {
        "metadata": {
            "generation_time": datetime.now().isoformat(),
            "min_confidence": MIN_CONFIDENCE,
            "min_relevance": MIN_RELEVANCE,
            "document_count": len(ranked_results)
        },
        "documents": [],
        "categories": {},
        "entities": {},
        "relationships": []
    }
    
    # Add document data
    for result in ranked_results:
        doc_data = {
            "document_id": result["document"],
            "relevance_score": result["relevance_score"],
            "categories": list(result["categories"]),
            "evidence_types": list(result["evidence_type"]),
            "entity_mentions": dict(result["entity_mentions"]),
            "relationship_count": len(result["relationships"]),
            "high_confidence_findings": result["high_confidence_findings"]
        }
        structured_data["documents"].append(doc_data)
    
    # Collect data by category
    for result in ranked_results:
        for finding in result["high_confidence_findings"]:
            category = finding["category"]
            if category not in structured_data["categories"]:
                structured_data["categories"][category] = []
            
            structured_data["categories"][category].append({
                "document": result["document"],
                "page": finding["page"],
                "confidence": finding["confidence"],
                "description": finding["description"],
                "quote": finding["quote"],
                "entities": finding["entities"]
            })
    
    # Collect entity data
    for result in ranked_results:
        for entity, count in result["entity_mentions"].items():
            if entity not in structured_data["entities"]:
                structured_data["entities"][entity] = {
                    "mention_count": 0,
                    "documents": [],
                    "relationships": []
                }
            
            structured_data["entities"][entity]["mention_count"] += count
            structured_data["entities"][entity]["documents"].append({
                "document_id": result["document"],
                "mentions": count
            })
    
    # Collect relationship data
    for result in ranked_results:
        for rel in result["relationships"]:
            relationship_data = {
                "source": rel["source"],
                "relationship": rel["relationship"],
                "target": rel["target"],
                "document": result["document"],
                "page": rel["page"],
                "category": rel["category"],
                "confidence": rel["confidence"],
                "description": rel["description"],
                "quote": rel["quote"]
            }
            structured_data["relationships"].append(relationship_data)
            
            # Also add to entity's relationships
            if rel["source"] in structured_data["entities"]:
                structured_data["entities"][rel["source"]]["relationships"].append(relationship_data)
            if rel["target"] in structured_data["entities"]:
                structured_data["entities"][rel["target"]]["relationships"].append(relationship_data)
    
    # Save JSON file
    json_path = os.path.join(output_dir, "structured_findings.json")
    with open(json_path, 'w') as f:
        json.dump(structured_data, f, indent=2)
    
    print(f"Structured JSON data saved to {json_path}")

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    output_dir = args.output
    
    print(f"Analyzing JFK document analyses in: {output_dir}")
    
    # Get all analysis files
    analysis_files = get_analysis_files(output_dir)
    print(f"Found {len(analysis_files)} analysis files")
    
    if len(analysis_files) == 0:
        print("ERROR: No analysis files found. Check that:")
        print(f"1. The output directory is correct (currently set to '{output_dir}')")
        print("2. You've run parse_pdfs.py to generate analyses")
        print("3. The analysis files are named with the pattern *-analysis.json")
        return
    
    # Sample check of first file
    if analysis_files and DEBUG:
        first_file = analysis_files[0]
        try:
            with open(first_file, 'r') as f:
                content = json.load(f)
                print(f"\nSample from {os.path.basename(first_file)}:")
                print(f"File contains {len(content)} analyzed pages")
                if content and len(content) > 0:
                    first_page = content[0]
                    print(f"First page relevance: {first_page.get('overall_page_relevance', 'N/A')}")
                    findings = first_page.get('relevant_findings', [])
                    print(f"First page has {len(findings)} findings")
                    if findings:
                        for i, finding in enumerate(findings[:2]):  # Show first 2 findings
                            print(f"Finding {i+1}: {finding.get('category')} (Confidence: {finding.get('confidence')})")
                            print(f"  {finding.get('description', 'No description')}")
        except Exception as e:
            print(f"Error examining file {first_file}: {e}")
    
    # Analyze each document
    analysis_results = []
    for file_path in analysis_files:
        print(f"Analyzing {os.path.basename(file_path)}")
        result = analyze_document(file_path)
        analysis_results.append(result)
    
    # Filter results if needed
    filtered_results = filter_results(analysis_results, args)
    if len(filtered_results) != len(analysis_results):
        print(f"Filtered from {len(analysis_results)} to {len(filtered_results)} documents")
    
    # Rank the documents
    ranked_results = rank_documents(filtered_results)
    
    # Generate exports based on format
    if args.format in ["txt", "all"]:
        summarize_findings(ranked_results, output_dir, args)
    
    if args.format in ["json", "all"]:
        export_json_findings(ranked_results, output_dir)
    
    if args.format in ["csv", "all"]:
        export_findings_csv(ranked_results, output_dir)
    
    # Generate knowledge graph
    generate_knowledge_graph(ranked_results, output_dir)
    
    print(f"\nAnalysis complete!")
    
    # Print top 5 most interesting documents
    print("\nTOP 5 MOST SIGNIFICANT DOCUMENTS:")
    for i, result in enumerate(ranked_results[:5], 1):
        print(f"{i}. {result['document']} (Score: {result['relevance_score']})")
        print(f"   Categories: {', '.join(result['categories'])}")
        
        # Show top entities if available
        top_entities = sorted(result["entity_mentions"].items(), key=lambda x: x[1], reverse=True)[:3]
        if top_entities:
            entity_str = ", ".join([f"{e[0]} ({e[1]})" for e in top_entities])
            print(f"   Key entities: {entity_str}")
        
        # Show relationship count if any
        if result["relationships"]:
            print(f"   Entity connections: {len(result['relationships'])}")
        
        print()

if __name__ == "__main__":
    main()
