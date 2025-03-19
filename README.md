# JFK Assassination Document Analysis System

This system uses the Anthropic Claude AI to analyze declassified JFK assassination documents, extract key information, identify connections between entities, and surface potentially significant findings.

## Setup

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- JFK assassination documents in PDF format (place in `jfk_pdfs/` directory)
- Anthropic API key

### Installation

1. Clone this repository or download the files

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

### Getting an Anthropic API Key

1. Go to [https://console.anthropic.com/](https://console.anthropic.com/)
2. Sign up for an account or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key and add it to your `.env` file

## Files and Usage

### 1. Initial Document Processing

**File:** `parse_pdfs.py`

This script processes PDF documents to extract meaningful information related to the JFK assassination.

```bash
python parse_pdfs.py
```

- Converts each PDF to images
- Analyzes each page using Claude
- Looks for evidence related to 10 key conspiracy categories
- Generates initial JSON analysis files and summaries
- Creates a global summary of findings

### 2. Enhanced Analysis of Initial Results

**File:** `parse_responses.py`

This script analyzes the initial findings to identify the most significant documents and connections.

```bash
# Basic usage - processes most recent output directory
python parse_responses.py

# Process a specific output directory
python parse_responses.py --output output_20250318_180803

# Filter by category
python parse_responses.py --category "WITNESS_TESTIMONIES"

# Filter by entity
python parse_responses.py --entity "Lee Harvey Oswald"

# Show only documents with connections between entities
python parse_responses.py --connections-only

# Adjust confidence threshold
python parse_responses.py --min-confidence 7
```

Outputs:
- significant_findings.txt: Detailed report of findings
- high_confidence_findings.csv: Tabular data for further analysis
- entity_relationships.csv: Mapping of entity relationships
- structured_findings.json: Complete data in JSON format
- knowledge_graph.json: Network visualization data

### 3. Deep Analysis of High-Confidence Findings

**File:** `final_parse.py`

This script uses Claude 3.7 Sonnet (the most powerful model) to perform deeper analysis on the most promising documents.

```bash
# Analyze top 5 most promising documents (default)
python final_parse.py
```

Outputs detailed JSON analyses and a comprehensive summary in a timestamped directory.

### 4. Targeted Document Analysis

**File:** `analyze_document.py`

This script analyzes a specific document by ID with Claude 3.7 Sonnet.

```bash
# Analyze a specific document, automatically finding the most relevant page
python analyze_document.py 104-10332-10023

# Analyze a specific page
python analyze_document.py 104-10332-10023 --page 5

# Analyze all relevant pages in a document
python analyze_document.py 104-10332-10023 --all-pages
```

Provides a focused analysis of a single document, useful for investigating specific leads.

## Output Directories

- `output_TIMESTAMP/`: Contains results from `parse_pdfs.py`
- `output_final_TIMESTAMP/`: Contains results from `final_parse.py`
- `doc_analysis_TIMESTAMP/`: Contains results from `analyze_document.py`

## Understanding the Analysis

The system evaluates documents based on:

1. **Relevance**: Connection to the JFK assassination
2. **Credibility**: Quality of the evidence
3. **Entity Connections**: Relationships between people and organizations
4. **Contradictions**: Inconsistencies with the official narrative
5. **Significance**: Historical importance of findings

## Example Usage Workflow

1. Process all PDFs with initial analysis:
   ```
   python parse_pdfs.py
   ```

2. Identify significant documents and connections:
   ```
   python parse_responses.py
   ```

3. Run deeper analysis on promising documents:
   ```
   python final_parse.py
   ```

4. Investigate specific documents of interest:
   ```
   python analyze_document.py DOCUMENT_ID
   ```

## Notes

- Processing large numbers of documents can be time and API-cost intensive
- The quality of analysis depends on document legibility
- The system uses a tiered approach, using cheaper models for initial screening and more powerful models for promising documents

## Troubleshooting

- If you encounter JSON parsing errors, the scripts include fallback mechanisms
- For best results, ensure PDFs are high quality and text is legible
- If a script crashes, you can usually resume by running it again - it will skip already processed documents 