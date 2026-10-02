import httpx
import re
import asyncio
import argparse
import logging
from pathlib import Path
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Regex to find markdown links
LINK_PATTERN = re.compile(r'\[(?P<text>.*?)\]\((?P<url>https?://.*?)(?:\s+(?P<title>".*?")\s*)?\)')

# Simple cache for Wayback API results
wayback_cache = {}
# Semaphore to limit concurrent Wayback API requests
wb_semaphore = asyncio.Semaphore(1)

async def check_link(client, url):
    try:
        # Rate limiting mitigation
        await asyncio.sleep(0.1)
        # Use a more descriptive User-Agent
        headers = {'User-Agent': 'Link-Reviver-Bot/1.1'}
        # Try HEAD first
        response = await client.head(url, follow_redirects=True, timeout=10.0, headers=headers)
        if response.status_code == 200:
            return url, 200, None
        return await check_wayback(client, url)
    except httpx.HTTPError:
        return await check_wayback(client, url)
    except Exception:
        return await check_wayback(client, url)

async def check_wayback(client, url):
    if url in wayback_cache:
        return url, wayback_cache[url][0], wayback_cache[url][1]

    async with wb_semaphore:
        try:
            wb_url = f"http://archive.org/wayback/available?url={url}"
            
            retries = 0
            while retries < 5:
                response = await client.get(wb_url, timeout=15.0)
                
                if response.status_code == 200:
                    data = response.json()
                    snapshots = data.get("archived_snapshots", {})
                    if "closest" in snapshots and snapshots["closest"].get("available"):
                        result = ("Archived", snapshots["closest"]["url"])
                        wayback_cache[url] = result
                        return url, result[0], result[1]
                    
                    result = ("Not Found", None)
                    wayback_cache[url] = result
                    return url, result[0], result[1]
                
                elif response.status_code == 429:
                    wait_time = (10 * (2 ** retries)) + random.uniform(1, 5)
                    logging.info(f"Rate limited by Wayback API for {url}. Retrying in {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                    retries += 1
                else:
                    result = (f"Wayback API Error: {response.status_code}", None)
                    wayback_cache[url] = result
                    return url, result[0], result[1]
            
            result = ("Wayback API Error: Max retries", None)
            wayback_cache[url] = result
            return url, result[0], result[1]
            
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
        links = list(LINK_PATTERN.finditer(text))
        unique_urls = {match.group('url') for match in links}
        
        url_status_map = {}
        for url in unique_urls:
            _, status, arch_url = await check_link(client, url)
            if status != 200:
                logging.warning(f"Broken link found: {url} | Status: {status} | Archived: {arch_url}")
            url_status_map[url] = (status, arch_url)
        
        changed = False
        def replacer(match):
            nonlocal changed
            url = match.group('url')
            status, arch_url = url_status_map.get(url, (None, None))
            
            if status != 200 and fix and arch_url:
                changed = True
                return replace_link(match, arch_url)
            
            return match.group(0)

        new_text = LINK_PATTERN.sub(replacer, text)
        
        if changed:
            file_path.write_text(new_text, encoding='utf-8')
            logging.info(f"Fixed links in {file_path}")
            
    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")

# 2026-10-02: URLs that are not fixable dead links. GitHub serves these
# login-only pages as 404 to anonymous clients, and badge image URLs with a
# shields-style ?style= are decoration, not list entries.
LOGIN_ONLY_GITHUB = re.compile(r'^https?://github\.com/[^/]+/[^/]+/(stargazers|watchers|network/members)/?(?:[?#].*)?$')
BADGE_STYLE = re.compile(r'[?&]style=(flat|flat-square|for-the-badge|plastic|social)(?:&|$)')


def skip_reason(url):
    if LOGIN_ONLY_GITHUB.match(url):
        return 'github_login_only_page'
    if BADGE_STYLE.search(url):
        return 'badge_url'
    return None


async def scan_report(path, offset=0):
    import hashlib
    raw=path.read_bytes()
    urls=list(dict.fromkeys(m.group('url') for m in LINK_PATTERN.finditer(raw.decode('utf-8'))))
    if not 0<=offset<=len(urls):
        raise ValueError('invalid scan offset')
    selected=urls[offset:offset+100]
    semaphore=asyncio.Semaphore(10)
    async with httpx.AsyncClient(headers={'User-Agent':'Link-Reviver-Bot/1.1'}) as client:
        async def inspect(url):
            reason=skip_reason(url)
            if reason:
                return {'url':url,'http_status':None,'state':'skipped','reason':reason}
            async with semaphore:
                async def request():
                    r=await client.head(url,follow_redirects=True,timeout=3)
                    if not 200<=r.status_code<300:
                        async with client.stream('GET',url,follow_redirects=True,timeout=3) as r:
                            status=r.status_code
                    else:
                        status=r.status_code
                    return {'url':url,'http_status':status,'state':'reachable' if 200<=status<300 else 'missing' if status in (404,410) else 'unknown'}
                try:
                    return await asyncio.wait_for(request(),timeout=6)
                except (httpx.HTTPError,asyncio.TimeoutError):
                    return {'url':url,'http_status':None,'state':'unknown','reason':'request_failed_or_timed_out'}
        results=await asyncio.gather(*(inspect(url) for url in selected))
    end=offset+len(results)
    return {'schema':'LinkScan/v1','source_sha256':hashlib.sha256(raw).hexdigest(),'offset':offset,'next_offset':end if end<len(urls) else None,'total_links':len(urls),'checked':len(results),'complete':end==len(urls),'results':results,'note':'HTTP observations only; missing links require confirmation before outreach. Unknown is not broken.'}


async def main():
    parser = argparse.ArgumentParser(description="Find and fix broken links in Markdown files.")
    parser.add_argument("path", help="Path to file or directory to scan")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix broken links")
    parser.add_argument("--report-json", action="store_true")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    if args.report_json:
        if args.fix:
            parser.error("report mode cannot fix files")
        import json
        print(json.dumps(await scan_report(Path(args.path),args.offset)))
        return

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
