"""Discover papers for a venue + year(s) using the DBLP API.

DBLP is the canonical, free index of CS publications. We use the `toc:` query
trick to fetch the *complete* table of contents of a specific proceedings, which
is far more precise than fuzzy keyword search.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Iterable

import requests

DBLP_PUBL_API = "https://dblp.org/search/publ/api"
DBLP_VENUE_API = "https://dblp.org/search/venue/api"


@dataclass
class Paper:
    title: str
    authors: list[str]
    venue: str
    year: int | None
    doi: str | None = None
    ee: str | None = None          # electronic edition URL (publisher link)
    dblp_url: str | None = None
    dblp_key: str | None = None
    abstract: str | None = None
    # filled in later stages:
    pdf_path: str | None = None
    summary_path: str | None = None
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.dblp_key or self.doi or self.title


def _session(user_agent: str = "autoPaper/0.1") -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    return s


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve_stream_key(acronym: str, session: requests.Session) -> str | None:
    """Resolve a venue acronym (e.g. 'isca') to a DBLP stream key (e.g. 'conf/isca')
    via the venue search API. Returns None if not confidently found."""
    r = session.get(
        DBLP_VENUE_API,
        params={"q": acronym, "format": "json", "h": 20},
        timeout=30,
    )
    r.raise_for_status()
    hits = r.json().get("result", {}).get("hits", {}).get("hit", [])
    target = _norm(acronym)
    for hit in hits:
        info = hit.get("info", {})
        url = info.get("url", "")  # e.g. https://dblp.org/db/conf/isca/
        m = re.search(r"/db/((?:conf|journals)/[^/]+)/?$", url)
        if not m:
            continue
        key = m.group(1)
        # prefer an exact-ish acronym match on the last path segment
        if _norm(key.split("/")[-1]) == target or target in _norm(info.get("acronym", "")):
            return key
    # fall back to the first usable hit
    for hit in hits:
        url = hit.get("info", {}).get("url", "")
        m = re.search(r"/db/((?:conf|journals)/[^/]+)/?$", url)
        if m:
            return m.group(1)
    return None


def _parse_hit(info: dict) -> Paper:
    authors_field = info.get("authors", {}).get("author", [])
    if isinstance(authors_field, dict):
        authors_field = [authors_field]
    authors = [a.get("text", "") if isinstance(a, dict) else str(a) for a in authors_field]
    year = info.get("year")
    try:
        year = int(year) if year is not None else None
    except (ValueError, TypeError):
        year = None
    return Paper(
        title=info.get("title", "").rstrip("."),
        authors=authors,
        venue=info.get("venue", ""),
        year=year,
        doi=info.get("doi"),
        ee=info.get("ee"),
        dblp_url=info.get("url"),
        dblp_key=info.get("key"),
    )


def _toc_query(stream_key: str, year: int, session: requests.Session) -> list[Paper]:
    """Fetch a full proceedings TOC via the DBLP `toc:` filter.

    The bibliographic-history (.bht) file for a conference proceedings is named
    like `db/conf/isca/isca2023.bht`. Querying `toc:<that path>:` returns exactly
    the entries in that proceedings.
    """
    short = stream_key.split("/")[-1]
    bht = f"{stream_key}/{short}{year}.bht"
    r = session.get(
        DBLP_PUBL_API,
        params={"q": f"toc:db/{bht}:", "format": "json", "h": 1000},
        timeout=45,
    )
    r.raise_for_status()
    hits = r.json().get("result", {}).get("hits", {}).get("hit", [])
    papers = [_parse_hit(h.get("info", {})) for h in hits]
    # keep only real papers (drop the proceedings/editorship entry)
    return [p for p in papers if p.title and len(p.authors) > 0]


def _fuzzy_query(acronym: str, year: int, session: requests.Session) -> list[Paper]:
    """Fallback: keyword search filtered to the venue acronym + year."""
    r = session.get(
        DBLP_PUBL_API,
        params={"q": f"{acronym} {year}", "format": "json", "h": 1000},
        timeout=45,
    )
    r.raise_for_status()
    hits = r.json().get("result", {}).get("hits", {}).get("hit", [])
    target = _norm(acronym)
    out = []
    for h in hits:
        p = _parse_hit(h.get("info", {}))
        if p.year == year and target in _norm(p.venue):
            out.append(p)
    return out


def fetch_venue(
    acronym: str,
    years: Iterable[int],
    venue_keys: dict[str, str] | None = None,
    user_agent: str = "autoPaper/0.1",
    polite_delay: float = 1.0,
) -> list[Paper]:
    """Return all papers for a venue across the given years."""
    session = _session(user_agent)
    venue_keys = venue_keys or {}
    key = venue_keys.get(acronym.lower())
    if not key:
        key = resolve_stream_key(acronym, session)

    results: list[Paper] = []
    for year in years:
        papers: list[Paper] = []
        if key:
            try:
                papers = _toc_query(key, year, session)
            except requests.RequestException:
                papers = []
        if not papers:
            papers = _fuzzy_query(acronym, year, session)
        results.extend(papers)
        time.sleep(polite_delay)
    return results
