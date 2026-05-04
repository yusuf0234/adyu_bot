import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

DOMAIN = "www.adiyaman.edu.tr"
BASE_URL = f"https://{DOMAIN}"
# Limit pages to avoid infinite scraping locally during demo
MAX_PAGES = 50 

def chunk_text(text: str, max_words: int = 400) -> list:
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        if len(chunk.strip()) > 50: # Only keep meaningful chunks
            chunks.append(chunk)
    return chunks

def extract_text_from_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script, style, nav, footer, header
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()
        
    text = soup.get_text(separator=' ', strip=True)
    # Remove extra whitespaces
    text = ' '.join(text.split())
    return text

def scrape_site():
    print(f"Starting crawl for {BASE_URL}")
    visited = set()
    to_visit = [BASE_URL]
    all_chunks = []
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'AdyuBot/1.0 (Research Purpose)'
    })

    while to_visit and len(visited) < MAX_PAGES:
        url = to_visit.pop(0)
        
        if url in visited:
            continue
            
        try:
            val = urlparse(url)
            if val.netloc != DOMAIN:
                continue
                
            response = session.get(url, timeout=10)
            visited.add(url)
            
            if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                continue
                
            text = extract_text_from_html(response.text)
            chunks = chunk_text(text)
            
            for c in chunks:
                all_chunks.append({
                    "text": c,
                    "url": url
                })
                
            # Find more links
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                # Normalize url by removing fragments
                full_url = full_url.split('#')[0]
                
                if full_url not in visited and urlparse(full_url).netloc == DOMAIN:
                    if full_url not in to_visit:
                        to_visit.append(full_url)
                        
            print(f"Scraped {url} - Total visited: {len(visited)} - Chunks so far: {len(all_chunks)}")
            time.sleep(0.5) # Polite scraping
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            visited.add(url)
            
    return all_chunks

if __name__ == "__main__":
    chunks = scrape_site()
    print(f"Finished scraping. Total chunks: {len(chunks)}")
