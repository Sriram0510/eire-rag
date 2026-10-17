"""Turn raw HTML pages into clean Markdown documents with their source URL.

Version 2: a site-specific extractor. trafilatura's general-purpose rules
dropped collapsed accordion panels (FAQs) and some lists on this site, so we
read the page's own content container (.post-content) directly instead.
"""

import hashlib
import json
import re
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
DOCS_FILE = OUT_DIR / "docs.jsonl"
MIN_WORDS = 80
TITLE_SUFFIX = " - Immigration Service Delivery"


def load_manifest() -> dict[str, dict]:
    records = {}
    with (RAW_DIR / "manifest.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            records[rec["file"]] = rec
    return records


def extract_main(html: str) -> tuple[str | None, str | None]:
    """Return (title, markdown) from the site's main content container."""
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True).removesuffix(TITLE_SUFFIX) if title_tag else None

    main = soup.select_one(".post-content")
    if main is None:
        return title, None

    # Things that are never content
    for node in main.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    for tag in main.select("script, style, noscript, iframe, form, button, svg, img"):
        tag.decompose()
    # Decorative icons
    for tag in main.select(".fusion-toggle-icon-wrapper, i.fb-icon-element, i.fontawesome-icon"):
        tag.decompose()
    # The "In This Section" box only holds jump-links to headings on the same page
    for tag in main.select("[class*=inthissection]"):
        tag.decompose()
    for heading in main.find_all(["h2", "h3", "h4"]):
        if heading.get_text(strip=True).lower() == "in this section":
            heading.decompose()
    # Accordion titles become real headings, so each FAQ keeps its question
    for panel_title in main.select(".panel-title"):
        panel_title.name = "h4"

    markdown = markdownify(
        str(main), heading_style="ATX", bullets="-", strip=["a", "span", "div"]
    )
    return title, markdown


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")      # non-breaking spaces -> normal spaces
    text = re.sub(r'(<\?)?xml encoding="[^"]*"\s*\?>?\s*', "", text)  # stray <?xml ?> tag
    text = re.sub(r"[ \t]+\n", "\n", text)   # remove spaces at line ends
    text = re.sub(r"\n{3,}", "\n\n", text)   # at most one blank line in a row
    return text.strip()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    seen_hashes: dict[str, str] = {}
    kept, short, dupes, fallback = 0, [], [], []

    with DOCS_FILE.open("w", encoding="utf-8") as out:
        for file_name, rec in sorted(manifest.items()):
            html = (RAW_DIR / file_name).read_text(encoding="utf-8")
            title, text = extract_main(html)
            if not text:
                # Page doesn't use the usual template: fall back to trafilatura
                fallback.append(file_name)
                text = trafilatura.extract(
                    html, output_format="markdown", include_formatting=True,
                    include_tables=True, include_links=False,
                    include_images=False, include_comments=False,
                )
            if not text:
                short.append((file_name, 0))
                continue

            text = clean_text(text)
            n_words = len(text.split())
            if n_words < MIN_WORDS:
                short.append((file_name, n_words))
                continue

            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest in seen_hashes:
                dupes.append((file_name, seen_hashes[digest]))
                continue
            seen_hashes[digest] = file_name

            title = title or file_name
            doc_id = file_name.removesuffix(".html")
            doc = {
                "doc_id": doc_id,
                "url": rec["url"],
                "title": title,
                "lastmod": rec["lastmod"],
                "fetched_at": rec["fetched_at"],
                "n_words": n_words,
                "text": text,
            }
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            (OUT_DIR / f"{doc_id}.md").write_text(
                f"# {title}\n\nSource: {rec['url']}\n\n{text}\n", encoding="utf-8"
            )
            kept += 1

    print(f"Kept {kept} of {len(manifest)} pages -> {DOCS_FILE}")
    print(f"Used trafilatura fallback: {len(fallback)}")
    for name in fallback:
        print(f"   {name}")
    print(f"Too short (< {MIN_WORDS} words): {len(short)}")
    for name, n in short:
        print(f"   {n:>4} words  {name}")
    print(f"Exact duplicates skipped: {len(dupes)}")
    for name, original in dupes:
        print(f"   {name}  (same as {original})")


if __name__ == "__main__":
    main()