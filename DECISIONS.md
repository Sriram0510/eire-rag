# Design decisions

## Data collection
- **Source:** irishimmigration.ie (official ISD site), 4 sections: study, work,
  registration, "my situation has changed". 94 pages via the sitemap.
- **Politeness:** follow robots.txt, 10 s crawl delay, identify with a project User-Agent.
- **robots.txt bug:** Python's RobotFileParser fetched robots.txt with its own
  User-Agent and got rejected, so it treated every page as disallowed. Fixed by
  fetching robots.txt with our own httpx client.

## Cleaning
- **Extractor v1 (trafilatura):** dropped collapsed FAQ panels and some lists on this
  site. The Stamp 1G page lost its conditions and the €300 fee.
- **Extractor v2:** read the site's `.post-content` container with BeautifulSoup +
  markdownify; trafilatura kept as fallback (used on 0 of 94 pages).
- **Quality gate:** drop pages under 80 words. v1 dropped 8, v2 drops 2. Six of v1's
  "short" pages were real content hidden in collapsed panels; the 2 left are pointer pages.
- **Stray `<?xml ?>` tag:** leaked into 11 files, in 10 of them glued to the front of an
  important notice banner. Removed with a regex that strips only the tag and keeps the text.
  Verified across all files with a search, not just the first example.
- **Known gap:** some key policy content is only in linked PDFs. TODO: add PDF ingestion.

## Chunking
- **Strategy:** split on Markdown headings; merge sections under 40 words into the
  next one; split sections over 300 words at paragraph breaks with 40 words of overlap.
- **Context header:** every chunk starts with "Page title > Section" so it is
  searchable and citable on its own.
- **Merged labels:** a merged chunk lists all its section names (e.g. "Required
  documents; How to apply") so citations never hide what is inside.
- **Size limit:** 300 words (~400 tokens) keeps chunks under the embedding model's
  512-token limit. Overlap can push a chunk to ~340 words; still under the limit.
- **Footer removal:** "This page was last updated on <date>" is sometimes glued to the
  previous sentence, so the regex matches it anywhere, anchored on the date format.
- **Result:** 92 docs -> N chunks; median M words, max X.