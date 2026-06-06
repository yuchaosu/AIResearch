# autoPaper

Venue-driven academic paper **fetcher → downloader → digester** for computer
architecture / HPC research. You give it a venue (HPCA, ISCA, SC, ICS, MICRO, …)
plus optional keywords; it discovers the papers, downloads the matching PDFs via
your campus access, and writes a structured Markdown digest of each using
**Claude Code** (your subscription — no API key needed).

## How it works

```
venue + year(s) + keywords
   │
   ▼ [1] DBLP toc: API ........ complete proceedings list (title, authors, DOI)   ← free, no proxy
   ▼ [2] OpenAlex ............. abstracts by DOI                                    ← free, no proxy
   ▼ [3] keyword filter ....... match keywords on title+abstract (BEFORE download)
   ▼ [4] download ............. DOI → ACM/IEEE PDF, rate-limited, campus IP
   ▼ [5] summarize ............ PyMuPDF text → `claude -p` structured digest
   ▼ [6] store ................ SQLite metadata + PDFs + Markdown summaries
```

## Access / proxy

This tool is meant to run on a machine **on the Proxy network** (campus Wi-Fi,
wired, or institution VPN). ACM Digital Library and IEEE Xplore authenticate by **IP
address**.

## ⚠️ Respect publisher terms

ACM and IEEE **prohibit systematic / bulk downloading**. Abuse can get
institutional access revoked for everyone. autoPaper enforces:
- keyword filtering *before* any download (you only fetch what you actually want)
- a polite delay between downloads (default 20s + jitter)
- a hard per-run cap (default 25 PDFs)

Do not raise these to crawl entire proceedings. Use it for targeted reading.

## Setup

```powershell
cd autoPaper
python -m pip install -r requirements.txt
# Make sure Claude Code is logged in (uses your subscription, not an API key):
claude            # run once interactively, then exit
```

Edit `config.yaml` to taste (delays, model, output dirs).

## Usage

```powershell
# Discover + abstract-triage only (safe, no downloads):
python -m autopaper.cli --venue HPCA --years 2023 2024 --keywords "prefetch" "GPU" --no-download

# Full run: download matching PDFs + summarize:
python -m autopaper.cli --venue ISCA --years 2024 --keywords "security"

# A year range, capped to 5 papers, summarize from abstracts only:
python -m autopaper.cli --venue SC --years 2021-2023 --keywords "MPI" --limit 5 --no-download
```

Flags:
- `--venue` venue acronym (required)
- `--years` one or more years / ranges, e.g. `2024` or `2020-2024`
- `--keywords` zero or more; empty = keep all papers
- `--match any|all` — match any keyword (default) or require all
- `--limit N` — process at most N matched papers
- `--no-download` — abstracts-only triage (no PDF fetching)
- `--no-summarize` — skip Claude digests

## Output

- `data/papers.db` — SQLite metadata (every matched paper)
- `data/pdfs/` — downloaded PDFs
- `data/summaries/` — one Markdown digest per paper:
  TL;DR · Problem · Approach · Key Results · Limitations · Relevance score

## Project layout

```
autoPaper/
  config.yaml              # settings (delays, model, venue keys, paths)
  prompts/summarize.txt    # the prewritten digest prompt sent to Claude
  autopaper/
    cli.py                 # command-line entry point
    pipeline.py            # orchestrates the 6 stages
    dblp.py                # [1] venue discovery
    enrich.py              # [2] abstracts via OpenAlex
    keyword_filter.py      # [3] keyword matching
    download.py            # [4] polite PDF downloading
    extract.py             # [5a] PDF -> text (PyMuPDF)
    summarize.py           # [5b] Claude Code headless digest
    store.py               # [6] SQLite + markdown writer
    config.py              # config loader
```

## Notes & limitations

- **IEEE PDFs** are best-effort: IEEE's PDF endpoint needs an article number, so
  the downloader scrapes the landing page for the stamped PDF link. Some IEEE
  items may miss; ACM `10.1145/*` DOIs use a stable direct-PDF pattern.
- **DBLP venue keys** for common venues are in `config.yaml`; unknown venues are
  auto-resolved via DBLP's venue search (verify the discovered count looks right).
- Re-runs are **idempotent**: already-downloaded PDFs and already-written
  summaries are skipped.
```
