import os
import requests
from concurrent.futures import ThreadPoolExecutor

# Import the list of PDF filenames from file_list.py
from file_list import pdf_files

# Base URL for downloading PDFs
base_url = "https://www.archives.gov/files/research/jfk/releases/2025/0318/"

# Folder to save PDFs
download_folder = "jfk_pdfs"
os.makedirs(download_folder, exist_ok=True)

def download_pdf(filename):
    url = base_url + filename.replace(" ", "%20")  # Encode spaces for URLs
    print(f"Attempting to download: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Ensure the request succeeded

        # Save PDF to file
        pdf_path = os.path.join(download_folder, filename)
        with open(pdf_path, "wb") as file:
            file.write(response.content)

        print(f"Successfully downloaded {filename}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {filename}: {e}")
        return False

# Number of concurrent downloads
max_workers = 10

# Use ThreadPoolExecutor for parallel downloads
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    results = list(executor.map(download_pdf, pdf_files))

# Print summary
success_count = results.count(True)
print(f"\nDownload summary: {success_count}/{len(pdf_files)} files downloaded successfully")
