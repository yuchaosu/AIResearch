"""Enrich papers with abstracts via OpenAlex (free, no key, looked up by DOI)."""

from __future__ import annotations

import time

import requests

from .dblp import Paper

OPENALEX_WORK = "https://api.openalex.org/works/https://doi.org/{doi}"


def _reconstruct_abstract(inv_index: dict | None) -> str | None:
    """OpenAlex stores abstracts as an inverted index {word: [positions]}."""
    if not inv_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv_index.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


def enrich_abstracts(
    papers: list[Paper],
    mailto: str = "",
    user_agent: str = "autoPaper/0.1",
    polite_delay: float = 0.2,
) -> None:
    """Fill paper.abstract in place for papers that have a DOI. Best-effort."""
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    params = {"mailto": mailto} if mailto else {}

    for p in papers:
        if p.abstract or not p.doi:
            continue
        try:
            r = session.get(
                OPENALEX_WORK.format(doi=p.doi),
                params=params,
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                p.abstract = _reconstruct_abstract(data.get("abstract_inverted_index"))
        except requests.RequestException:
            pass
        time.sleep(polite_delay)
