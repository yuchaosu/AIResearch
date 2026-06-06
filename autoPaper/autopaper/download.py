"""Resolve a paper's DOI to a publisher PDF and download it politely.

Designed to run on a machine that is ON the NCSU network (campus Wi-Fi, wired,
or NCSU VPN), so ACM/IEEE authenticate by IP automatically -- no proxy, no login.

IMPORTANT: ACM and IEEE prohibit systematic/bulk downloading. This module
enforces a per-run cap and a polite delay between downloads. Do not raise these
to crawl whole proceedings -- that can get NCSU's institutional access revoked.
"""

from __future__ import annotations

import random
import re
import time
from pathlib import Path

import requests

from .dblp import Paper

ARXIV_RE = re.compile(r"arxiv\.org/abs/([^\s/?#]+)", re.IGNORECASE)


def _safe_name(paper: Paper) -> str:
    base = paper.doi or paper.title
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)[:120].strip("_") + ".pdf"


def _candidate_pdf_urls(paper: Paper) -> list[str]:
    """Best-effort list of direct-PDF URLs to try, publisher by publisher."""
    urls: list[str] = []
    doi = (paper.doi or "").strip()
    ee = (paper.ee or "")

    # arXiv (open access)
    m = ARXIV_RE.search(ee)
    if m:
        urls.append(f"https://arxiv.org/pdf/{m.group(1)}.pdf")

    if doi:
        # ACM Digital Library: stable direct-PDF pattern
        if doi.startswith("10.1145"):
            urls.append(f"https://dl.acm.org/doi/pdf/{doi}")
        # IEEE: needs the article (arnumber); handled separately below via page scrape
        # Generic: let doi.org redirect to the publisher landing page (we then scrape)
        urls.append(f"https://doi.org/{doi}")

    if ee and ee not in urls:
        urls.append(ee)
    return urls


def _find_pdf_link(html: str, base_url: str) -> str | None:
    """Scrape a landing page for an obvious PDF link (covers IEEE & misc)."""
    # IEEE stamp URL
    m = re.search(r'"pdfUrl":"([^"]+)"', html)
    if m:
        link = m.group(1).replace("\\/", "/")
        if link.startswith("/"):
            return "https://ieeexplore.ieee.org" + link
        return link
    # citation_pdf_url meta tag (common across publishers)
    m = re.search(r'<meta[^>]+name="citation_pdf_url"[^>]+content="([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def _looks_like_pdf(resp: requests.Response) -> bool:
    ctype = resp.headers.get("Content-Type", "").lower()
    return "application/pdf" in ctype or resp.content[:5] == b"%PDF-"


def download_pdf(paper: Paper, dest_dir: Path, cfg: dict) -> Path | None:
    """Try to download the paper's PDF. Returns the path, or None on failure."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / _safe_name(paper)
    if out.exists() and out.stat().st_size > 1024:
        paper.pdf_path = str(out)
        return out

    headers = {"User-Agent": cfg["user_agent"], "Accept": "application/pdf,*/*"}
    timeout = cfg["timeout"]
    session = requests.Session()
    session.headers.update(headers)

    for url in _candidate_pdf_urls(paper):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        if _looks_like_pdf(resp):
            out.write_bytes(resp.content)
            paper.pdf_path = str(out)
            return out
        # landing page -> look for an embedded PDF link, then fetch it
        link = _find_pdf_link(resp.text, resp.url)
        if link:
            try:
                resp2 = session.get(link, timeout=timeout, allow_redirects=True)
                if resp2.status_code == 200 and _looks_like_pdf(resp2):
                    out.write_bytes(resp2.content)
                    paper.pdf_path = str(out)
                    return out
            except requests.RequestException:
                pass
    return None


def download_many(papers: list[Paper], dest_dir: Path, cfg: dict) -> list[Paper]:
    """Politely download PDFs for a list of papers, honoring caps and delays."""
    if not cfg.get("enabled", True):
        return []
    cap = cfg["max_per_run"]
    delay = cfg["delay_seconds"]
    jitter = cfg["jitter_seconds"]

    done: list[Paper] = []
    attempted = 0
    for p in papers:
        if attempted >= cap:
            print(f"[download] hit per-run cap ({cap}); stopping. "
                  f"Re-run to fetch more.")
            break
        attempted += 1
        path = download_pdf(p, dest_dir, cfg)
        if path:
            done.append(p)
            print(f"[download] ok   {p.title[:70]}")
        else:
            print(f"[download] miss {p.title[:70]}  (no accessible PDF found)")
        # polite pause between requests, even on miss
        time.sleep(delay + random.uniform(0, jitter))
    return done
