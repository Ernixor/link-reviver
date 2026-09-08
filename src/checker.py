import httpx
import re
import asyncio
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Regex to find markdown links: [text](url) or [text](url "title")
# We capture the full link definition part to make replacement easier.
LINK_PATTERN = re.compile(r'\[(?P<text>.*?)\]\((?P<url>https?://.*?)(?:\s+(?P<title>".*?")\s*)?\)')

async def check_link(client, url):
    try:
        # Use a more descriptive User-Agent
        headers = {'User-Agent': 'Link-Reviver-Bot/1.0'}
        # Try HEAD first
        response = await client.head(url, follow_redirects=True, timeout=10.0, headers=headers)
        if response.status_code == 200:
            return url, 200, None
        return await check_wayback(client, url)
    except httpx.HTTPError as e:
        logging.debug(f"HTTP error for {url}: {e}")
        return await check_wayback(client, url)
    except Exception as e:
        logging.warning(f"Unexpected error for {url}: {e}")
        return await check_wayback(client, url)

async def check_wayback(client, url):
    try:
        wb_url = f"http://archive.org/wayback/available?url={url}"
        response = await client.get(wb_url, timeout=10.0)
        if response.status_code != 200:
            return url, f"Wayback API Error: {response.status_code}", None
        
        data = response.json()
        snapshots = data.get("archived_snapshots", {})
        if "closest" in snapshots and snapshots["closest"].get("available"):
            return url, "Archived", snapshots["closest"]["url"]
        return url, "Not Found", None
    except Exception as e:
        return url, f"Wayback Error: {e}", None

def replace_link(match, new_url):
    text = match.group('text')
    title = match.group('title')
    if title:
        return f"[{text}]({new_url} {title})"
    return f"[{text}]({new_url})"

async def scan_and_fix(file_path, client, fix=False):
    try:
        text = file_path.read_text(encoding='utf-8')
        
        # We need to perform replacements iteratively or using a replacement function
        # to ensure we only replace the broken links.
        
        links = list(LINK_PATTERN.finditer(text))
        
        # Unique URLs to check first to avoid redundant checks
        unique_urls = {match.group('url') for match in links}
        
        url_status_map = {}
        for url in unique_urls:
            _, status, arch_url = await check_link(client, url)
            url_status_map[url] = (status, arch_url)
        
        changed = False
        
        # Helper to replace in the text
        def replacer(match):
            nonlocal changed
            url = match.group('url')
            status, arch_url = url_status_map.get(url, (None, None))
            
            if status != 200 and fix and arch_url:
                logging.info(f"Fixing: {url} -> {arch_url}")
                changed = True
                return replace_link(match, arch_url)
            
            if status != 200:
                logging.info(f"Broken: {url} -> {status} {'(' + arch_url + ')' if arch_url else ''}")
            
            return match.group(0) # No change

        new_text = LINK_PATTERN.sub(replacer, text)
        
        if changed:
            file_path.write_text(new_text, encoding='utf-8')
            logging.info(f"Fixed links in {file_path}")
            
    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Find and fix broken links in Markdown files.")
    parser.add_argument("path", help="Path to file or directory to scan")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix broken links")
    args = parser.parse_args()

    async with httpx.AsyncClient() as client:
        path = Path(args.path)
        if not path.exists():
            logging.error(f"Path {path} does not exist.")
            return

        files = [path] if path.is_file() else path.rglob('*.md')
        
        for p in files:
            logging.info(f"Scanning {p}...")
            await scan_and_fix(p, client, fix=args.fix)

if __name__ == "__main__":
    asyncio.run(main())
