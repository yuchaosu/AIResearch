"""Summarize paper text by shelling out to Claude Code headless mode.

Uses your logged-in Claude Code subscription -- NO API key required. We invoke
`claude -p` (print mode), feed the paper text on stdin, and read JSON back.

We deliberately do NOT use --bare: bare mode skips OAuth and requires an
ANTHROPIC_API_KEY. Plain `claude -p` uses your interactive login instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .dblp import Paper

PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "summarize.txt"


class SummarizerError(RuntimeError):
    pass


def _resolve_claude(command: str) -> str:
    found = shutil.which(command)
    if not found:
        raise SummarizerError(
            f"Could not find '{command}' on PATH. Install Claude Code and run "
            f"`claude` once to log in."
        )
    return found


def _build_prompt(paper: Paper, keywords: list[str], body: str) -> str:
    instructions = PROMPT_FILE.read_text(encoding="utf-8")
    kw = ", ".join(keywords) if keywords else "(none specified)"
    header = (
        f"User keywords: {kw}\n"
        f"Paper title: {paper.title}\n"
        f"Venue/year: {paper.venue} {paper.year or ''}\n"
        f"Authors: {', '.join(paper.authors)}\n"
        f"DOI: {paper.doi or 'n/a'}\n"
        f"--- BEGIN PAPER TEXT ---\n{body}\n--- END PAPER TEXT ---\n"
    )
    return f"{instructions}\n\n{header}"


def summarize_text(
    paper: Paper,
    body: str,
    keywords: list[str],
    cfg: dict,
) -> str:
    """Return a Markdown digest of `body` for `paper`. Raises on hard failure."""
    claude = _resolve_claude(cfg["command"])
    prompt = _build_prompt(paper, keywords, body)

    cmd = [
        claude,
        "-p", prompt,
        "--model", cfg["model"],
        "--max-turns", "1",
        "--output-format", "json",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cfg["timeout"],
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired as e:
        raise SummarizerError(f"claude timed out after {cfg['timeout']}s") from e

    if proc.returncode != 0:
        raise SummarizerError(
            f"claude exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )

    out = proc.stdout.strip()
    # --output-format json -> {"result": "...", "total_cost_usd": ..., ...}
    try:
        data = json.loads(out)
        result = data.get("result", "")
        if not result:
            raise SummarizerError(f"empty result in JSON: {out[:300]}")
        return result.strip()
    except json.JSONDecodeError:
        # tolerate a plain-text response just in case
        return out
