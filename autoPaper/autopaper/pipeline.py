"""End-to-end orchestration: discover -> enrich -> filter -> download -> summarize."""

from __future__ import annotations

from .config import Config
from .dblp import Paper, fetch_venue
from .download import download_many
from .enrich import enrich_abstracts
from .extract import extract_text
from .keyword_filter import filter_papers
from .store import Store, write_summary
from .summarize import SummarizerError, summarize_text


def run(
    cfg: Config,
    venue: str,
    years: list[int],
    keywords: list[str],
    match_mode: str = "any",
    do_download: bool = True,
    do_summarize: bool = True,
    limit: int | None = None,
) -> list[Paper]:
    cfg.ensure_dirs()
    store = Store(cfg.path("db_path"))
    ua = cfg["download"]["user_agent"]

    print(f"[discover] {venue} {years} via DBLP ...")
    papers = fetch_venue(venue, years, cfg.get("venue_keys"), user_agent=ua)
    print(f"[discover] found {len(papers)} papers")

    if keywords:
        print(f"[enrich] fetching abstracts for keyword matching ...")
        enrich_abstracts(papers, mailto=cfg.get("openalex_mailto", ""), user_agent=ua)

    matched = filter_papers(papers, keywords, mode=match_mode)
    print(f"[filter] {len(matched)} papers match keywords {keywords or '(all)'}")

    for p in matched:
        store.upsert(p)

    if limit:
        matched = matched[:limit]

    if do_download:
        print(f"[download] attempting up to {cfg['download']['max_per_run']} PDFs "
              f"(polite delay {cfg['download']['delay_seconds']}s) ...")
        downloaded = download_many(matched, cfg.path("pdf_dir"), cfg["download"])
        for p in downloaded:
            store.upsert(p)
    else:
        downloaded = []

    if do_summarize:
        targets = [p for p in matched if p.pdf_path or p.abstract]
        print(f"[summarize] digesting {len(targets)} papers via Claude Code ...")
        for p in targets:
            if store.is_summarized(p.id):
                continue
            if p.pdf_path:
                body = extract_text(p.pdf_path, cfg["summarizer"]["max_chars"])
            else:
                body = p.abstract or ""
            if not body.strip():
                continue
            try:
                digest = summarize_text(p, body, keywords, cfg["summarizer"])
            except SummarizerError as e:
                print(f"[summarize] skip {p.title[:50]}: {e}")
                continue
            path = write_summary(p, digest, cfg.path("summary_dir"))
            store.mark_summarized(p.id, str(path))
            print(f"[summarize] wrote {path.name}")

    store.close()
    return matched
