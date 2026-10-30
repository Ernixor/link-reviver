"""GitHub Action entry point: scan Markdown files for dead links and suggest Wayback Machine copies.

Only HTTP 404/410 counts as dead. Timeouts, 403s and 5xx are reported as "unknown" and never fail the job,
because they are usually bot blocking or a temporary outage, not a broken link.
"""
import asyncio
import fnmatch
import logging
import os
import sys
from pathlib import Path

import httpx

from checker import check_wayback, scan_report

logging.getLogger("httpx").setLevel(logging.WARNING)

ALWAYS_SKIP = {".git", "node_modules"}
MAX_ARCHIVE_LOOKUPS = 25


def setting(name, default):
    return os.environ.get(f"LR_{name}", "").strip() or default


def markdown_files(root, exclude):
    if root.is_file():
        return [root]
    files = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if ALWAYS_SKIP & set(p.relative_to(root).parts) or any(fnmatch.fnmatch(rel, g) for g in exclude):
            continue
        files.append(p)
    return files


async def scan_file(path):
    results, offset = [], 0
    while offset is not None:
        report = await scan_report(path, offset)
        results += report["results"]
        offset = report["next_offset"]
    return results


def line_of(text, url):
    i = text.find(url)
    return text.count("\n", 0, i) + 1 if i >= 0 else 1


async def archive_copies(urls):
    found = {}
    async with httpx.AsyncClient(headers={"User-Agent": "Link-Reviver-Bot/1.1"}) as client:
        for url in urls[:MAX_ARCHIVE_LOOKUPS]:
            try:
                _, _, archived = await asyncio.wait_for(check_wayback(client, url), timeout=30)
            except asyncio.TimeoutError:
                print("Wayback Machine is rate limiting; no more archive lookups")
                break
            if archived:
                found[url] = archived.replace("http://", "https://", 1)
    return found


def write_file(name, text):
    target = os.environ.get(name)
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write(text)


async def main():
    root = Path(setting("PATH", "."))
    exclude = [g.strip() for g in setting("EXCLUDE", "").split(",") if g.strip()]
    fail_on = setting("FAIL_ON", "missing")
    suggest = setting("SUGGEST_ARCHIVE", "true").lower() == "true"
    if fail_on not in ("missing", "never"):
        sys.exit(f"fail-on must be 'missing' or 'never', not {fail_on!r}")
    if not root.exists():
        sys.exit(f"path {root} does not exist")

    dead, unknown, checked = [], 0, 0
    for path in markdown_files(root, exclude):
        text = path.read_text(encoding="utf-8", errors="replace")
        for r in await scan_file(path):
            checked += r["state"] != "skipped"
            unknown += r["state"] == "unknown"
            if r["state"] == "missing":
                dead.append((path, line_of(text, r["url"]), r["url"], r["http_status"]))

    archived = await archive_copies(list(dict.fromkeys(d[2] for d in dead))) if suggest and dead else {}
    for path, line, url, status in dead:
        hint = f" Archived copy: {archived[url]}" if url in archived else ""
        print(f"::warning file={path},line={line},title=Dead link ({status})::{url}{hint}")

    summary = [f"## Link Reviver\n\n{checked} links checked, **{len(dead)} dead** (HTTP 404/410), "
               f"{unknown} unknown (timeouts, bot blocking; not counted as dead).\n"]
    if dead:
        summary.append("\n| File | Line | Dead link | Archived copy |\n|---|---|---|---|\n")
        summary += [f"| {p} | {ln} | {u} | {archived.get(u, '')} |\n" for p, ln, u, _ in dead]
    summary.append("\nFound this useful? [Support link-reviver on Ko-fi](https://ko-fi.com/ernixor)\n")
    write_file("GITHUB_STEP_SUMMARY", "".join(summary))
    write_file("GITHUB_OUTPUT", f"dead-links={len(dead)}\n")
    print(f"{checked} links checked, {len(dead)} dead, {unknown} unknown")
    if dead and fail_on == "missing":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
