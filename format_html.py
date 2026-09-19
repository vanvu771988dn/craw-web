from bs4 import BeautifulSoup
import sys
import os

# Add src to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

def format_html_file(file_path):
    """
    Reads an HTML file, formats it using BeautifulSoup, and overwrites the file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print(f"Successfully formatted {file_path}")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    file_to_format = "data/crawl_html_20250825_100437_580595.html"
    format_html_file(file_to_format)
