"""The scout's tools: fetch new papers from arXiv, and read a paper's full text."""
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ATOM = "{http://www.w3.org/2005/Atom}"
API = "https://export.arxiv.org/api/query"
HEADERS = {"User-Agent": "paper-scout (Agentic AI course, vectorspace.blog)"}


def _get(url, timeout=60, attempts=1):
    """Download a page. arXiv is sometimes slow, so the API call gets a few tries."""
    request = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
            time.sleep(3)      # arXiv asks for at most one request every 3 seconds
            return text
        except Exception as error:
            if attempt == attempts:
                raise
            wait = 20 * attempt
            print(f"   arXiv request failed ({type(error).__name__}), retrying in {wait}s")
            time.sleep(wait)


def parse_feed(xml_text):
    """Turn arXiv's Atom feed into a list of paper dictionaries."""
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        url = entry.findtext(f"{ATOM}id", "").strip()
        arxiv_id = url.rsplit("/abs/", 1)[-1]
        papers.append({
            "id": arxiv_id,                                   # e.g. 2609.01234v2
            "base_id": re.sub(r"v\d+$", "", arxiv_id),        # the same paper, any version
            "title": " ".join(entry.findtext(f"{ATOM}title", "").split()),
            "abstract": " ".join(entry.findtext(f"{ATOM}summary", "").split()),
            "published": entry.findtext(f"{ATOM}published", "")[:10],
            "url": url,
        })
    return papers


def fetch_new_papers(categories, max_results):
    """The newest papers in the given categories, newest first."""
    query = " OR ".join(f"cat:{c}" for c in categories)
    params = urllib.parse.urlencode({
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    })
    return parse_feed(_get(f"{API}?{params}", timeout=90, attempts=4))


class _TextOnly(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer"}

    def __init__(self):
        super().__init__()
        self.parts, self.skipping = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(html):
    parser = _TextOnly()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def fetch_full_text(arxiv_id, max_chars):
    """The start of the paper's HTML version, or None if arXiv has no HTML for it."""
    try:
        html = _get(f"https://arxiv.org/html/{arxiv_id}", timeout=30)
    except Exception:
        return None
    text = html_to_text(html)
    return text[:max_chars] or None
