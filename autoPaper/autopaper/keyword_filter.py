"""Filter papers by keywords matched against title + abstract."""

from __future__ import annotations

import re

from .dblp import Paper


def _compile(keyword: str) -> re.Pattern:
    # match the keyword as a whole-word-ish phrase, case-insensitive
    escaped = re.escape(keyword.strip()).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def filter_papers(
    papers: list[Paper],
    keywords: list[str],
    mode: str = "any",
) -> list[Paper]:
    """Return papers matching the keywords.

    mode="any" (default): paper kept if it matches at least one keyword.
    mode="all": paper kept only if it matches every keyword.
    Empty keyword list -> all papers kept.
    Sets paper.matched_keywords for each kept paper.
    """
    if not keywords:
        for p in papers:
            p.matched_keywords = []
        return papers

    patterns = [(kw, _compile(kw)) for kw in keywords]
    kept: list[Paper] = []
    for p in papers:
        haystack = f"{p.title}\n{p.abstract or ''}"
        matched = [kw for kw, pat in patterns if pat.search(haystack)]
        ok = (len(matched) == len(keywords)) if mode == "all" else bool(matched)
        if ok:
            p.matched_keywords = matched
            kept.append(p)
    return kept
