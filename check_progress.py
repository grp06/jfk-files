import os
import glob
import argparse  # For command line arguments

# Config - use same paths as in the main script
PDF_DIR = "jfk_pdfs"
DEFAULT_OUTPUT_DIR = "output"  # Default to original directory

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
    parser = argparse.ArgumentParser(description="Check progress of JFK document analysis")
    parser.add_argument("--output", "-o", 
                       help="Output directory to check (default: most recent)")
    args = parser.parse_args()
    
    # If no output directory specified, use most recent
    if not args.output:
        args.output = get_latest_output_dir()
        print(f"No output directory specified, using: {args.output}")
    
    return args

def check_progress(output_dir):
    # Get list of all PDFs
    pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    total_pdfs = len(pdf_files)
    
    if total_pdfs == 0:
        print(f"No PDF files found in {PDF_DIR}")
        return
    
    # Check which PDFs have been fully processed
    completed = []
    in_progress = []
    
    for pdf_path in pdf_files:
        pdf_name = os.path.basename(pdf_path).replace('.pdf', '')
        output_folder = os.path.join(output_dir, pdf_name)
        analysis_file = os.path.join(output_folder, f"{pdf_name}-analysis.json")
        checkpoint_file = os.path.join(output_folder, ".checkpoint.json")
        
        if os.path.exists(analysis_file):
            completed.append(pdf_name)
        elif os.path.exists(checkpoint_file):
            in_progress.append(pdf_name)
    
    # Print summary
    print(f"Using output directory: {output_dir}")
    print(f"Total PDFs: {total_pdfs}")
    print(f"Completed: {len(completed)} ({', '.join(completed[:5]) + '...' if len(completed) > 5 else ', '.join(completed) if completed else 'None'})")
    print(f"In progress: {len(in_progress)} ({', '.join(in_progress[:5]) + '...' if len(in_progress) > 5 else ', '.join(in_progress) if in_progress else 'None'})")
    print(f"Not started: {total_pdfs - len(completed) - len(in_progress)}")
    
    return completed, in_progress

if __name__ == "__main__":
    args = parse_args()
    check_progress(args.output) 