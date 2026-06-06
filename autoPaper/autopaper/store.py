"""SQLite-backed metadata store + markdown summary writer."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .dblp import Paper

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    authors       TEXT,
    venue         TEXT,
    year          INTEGER,
    doi           TEXT,
    ee            TEXT,
    dblp_url      TEXT,
    abstract      TEXT,
    matched       TEXT,
    pdf_path      TEXT,
    summary_path  TEXT,
    summarized    INTEGER DEFAULT 0
);
"""


class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert(self, p: Paper) -> None:
        self.conn.execute(
            """INSERT INTO papers
               (id,title,authors,venue,year,doi,ee,dblp_url,abstract,matched,pdf_path,summary_path)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 abstract=COALESCE(excluded.abstract, papers.abstract),
                 matched=excluded.matched,
                 pdf_path=COALESCE(excluded.pdf_path, papers.pdf_path),
                 summary_path=COALESCE(excluded.summary_path, papers.summary_path)
            """,
            (
                p.id, p.title, json.dumps(p.authors), p.venue, p.year,
                p.doi, p.ee, p.dblp_url, p.abstract,
                json.dumps(p.matched_keywords), p.pdf_path, p.summary_path,
            ),
        )
        self.conn.commit()

    def mark_summarized(self, paper_id: str, summary_path: str) -> None:
        self.conn.execute(
            "UPDATE papers SET summarized=1, summary_path=? WHERE id=?",
            (summary_path, paper_id),
        )
        self.conn.commit()

    def is_summarized(self, paper_id: str) -> bool:
        row = self.conn.execute(
            "SELECT summarized FROM papers WHERE id=?", (paper_id,)
        ).fetchone()
        return bool(row and row["summarized"])

    def close(self) -> None:
        self.conn.close()


def write_summary(paper: Paper, digest: str, summary_dir: Path) -> Path:
    summary_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", (paper.doi or paper.title))[:100].strip("_")
    path = summary_dir / f"{slug}.md"
    header = (
        f"# {paper.title}\n\n"
        f"**Authors:** {', '.join(paper.authors)}  \n"
        f"**Venue:** {paper.venue} {paper.year or ''}  \n"
        f"**DOI:** {paper.doi or 'n/a'}  \n"
        f"**Matched keywords:** {', '.join(paper.matched_keywords) or 'n/a'}  \n\n"
        f"---\n\n"
    )
    path.write_text(header + digest + "\n", encoding="utf-8")
    paper.summary_path = str(path)
    return path
