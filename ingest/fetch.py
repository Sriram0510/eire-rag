"""Download official immigration pages listed in the site's sitemap.

Polite crawler: obeys robots.txt, waits between requests, identifies itself,
and skips pages it already has (so you can stop and re-run safely).
"""

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

import httpx

BASE = "https://www.irishimmigration.ie"
SITEMAP = f"{BASE}/page-sitemap.xml"
USER_AGENT = "eire-rag-learning-project/0.1 (+https://github.com/Sriram0510/eire-rag)"
SECTIONS = (
    "/coming-to-study-in-ireland/",
    "/coming-to-work-in-ireland/",
    "/registering-your-immigration-permission/",
    "/my-situation-has-changed-since-i-arrived-in-ireland/",
)
RAW_DIR = Path("data/raw")
MANIFEST = RAW_DIR / "manifest.jsonl"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def load_robots(client: httpx.Client) -> RobotFileParser:
    # Fetch robots.txt with OUR client (our User-Agent), not urllib's default.
    resp = client.get(f"{BASE}/robots.txt")
    print(f"robots.txt status: {resp.status_code}")
    resp.raise_for_status()
    rp = RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp


def sitemap_urls(client: httpx.Client) -> list[tuple[str, str]]:
    resp = client.get(SITEMAP)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    pages = []
    for url in root.findall("sm:url", NS):
        loc = url.findtext("sm:loc", namespaces=NS)
        lastmod = url.findtext("sm:lastmod", default="", namespaces=NS)
        if loc and loc.removeprefix(BASE).startswith(SECTIONS):
            pages.append((loc, lastmod))
    return pages


def slug(url: str) -> str:
    path = url.removeprefix(BASE).strip("/")
    return path.replace("/", "__")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
    ) as client:
        robots = load_robots(client)
        # This site's robots.txt puts Crawl-delay above the User-agent line,
        # so Python's parser misses it. Fall back to the 10 seconds it asks for.
        delay = robots.crawl_delay(USER_AGENT) or 10

        pages = sitemap_urls(client)
        print(f"Found {len(pages)} pages in scope. Delay: {delay}s between requests.")

        for i, (url, lastmod) in enumerate(pages, start=1):
            out = RAW_DIR / f"{slug(url)}.html"
            if out.exists():
                print(f"[{i}/{len(pages)}] skip (already have it) {url}")
                continue
            if not robots.can_fetch(USER_AGENT, url):
                print(f"[{i}/{len(pages)}] blocked by robots.txt {url}")
                continue

            time.sleep(delay)
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"[{i}/{len(pages)}] FAILED {url}: {exc}")
                continue

            out.write_text(resp.text, encoding="utf-8")
            record = {
                "url": url,
                "file": out.name,
                "lastmod": lastmod,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            with MANIFEST.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            print(f"[{i}/{len(pages)}] saved {out.name}")


if __name__ == "__main__":
    main()