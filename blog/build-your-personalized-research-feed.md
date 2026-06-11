---
title: "Build Your Personalized Research Feed in 10 minutes for Free"
date: 2026-05-09
authors:
  - name: Krishnagopal Halder
    email: Krishnagopal.Halder@zalf.de
    orcid: 0009-0005-9815-3017
    url: https://geonextgis.github.io/krishnagopal-halder-cv/
description: A step-by-step guide to building a free, automated, and personalized academic research feed using Web of Science, arXiv, and GitHub Actions.
thumbnail: ./images/build-your-personalized-research-feed.jpg
tags:
  - Research Feed
  - Web of Science
  - arXiv
  - GitHub Actions
  - GitHub Pages
keywords:
  - Literature Review
  - Web of Science
  - arXiv
  - GitHub Actions
  - GitHub Pages
  - Academic Writing
  - Automation
---

# Build Your Personalized Research Feed in 10 minutes for Free

This site is a personal [**research-interest feed**](https://geonextgis.github.io/paperatlas/): every Monday morning a GitHub Actions workflow asks Web of Science and arXiv for the freshest
papers matching my topics and journals, deduplicates them, writes a JSON
file, and redeploys this static site. There is no server, no database,
no build step, and no manual editing of paper lists.

If you are a researcher who wants the same thing for *your* topics, you
can fork this repo and have a working feed in roughly in 10 minutes. This
post walks through the parts that actually matter — what to edit, what
to leave alone, and how to write queries that pull useful results
instead of noise.

![Thumbnail](./images/build-your-personalized-research-feed.jpg)

## Why it is needed

Staying updated with the latest developments in your field is a constant, 
time-consuming struggle. Like many researchers, I tried relying on the 
standard platforms, but they all fall short in frustrating ways:

- **Google Scholar Alerts are too noisy:** The signal-to-noise ratio is terrible. 
  Set an alert for a specific term, and your inbox gets flooded with 
  unreviewed university theses, patents, and tangentially related papers from 
  obscure or predatory journals. There is no easy way to restrict the firehose 
  to just the high-impact journals you actually care about.
- **ResearchGate is a social network, not a feed:** It has become heavily 
  optimized for engagement rather than strict relevance. Your feed is constantly 
  cluttered with notifications like "Someone recommended your co-author's paper" 
  or "Congratulate X on 100 citations," burying the actual new literature you 
  need to see. 
- **Publisher Email Alerts are fragmented:** Signing up for Table of Contents (TOC) 
  alerts means managing a fragmented nightmare. You end up with 15 different, 
  unstandardized emails a week from Elsevier, Springer, Nature, and Wiley, forcing 
  you to manually scan through dozens of irrelevant papers just to find the one 
  article that fits your niche.

I built this because I wanted a system that is deterministic, quiet, and 
entirely under my control. No black-box recommendation algorithms, no 
"suggested for you" social feeds, and no inbox clutter. Just the exact 
search terms I care about, scoped exclusively to the journals I trust.

---

## What you get

- A weekly-updated grid of papers matching **your** topic terms, your
  keywords, your journals of interest, and any arXiv preprint queries
  you write.
- Filtering by journal, publisher, year, and free-text search.
- A dark/light theme that respects `prefers-color-scheme`.
- A complete audit trail: every executed query (and how many hits it
  returned) is recorded in `data/publications.json` under `queries`.
- Zero maintenance once configured. The workflow runs on a cron and
  commits the new JSON back to `main` for you.

---

## Five minutes of setup

1. [**Fork the repo**](https://github.com/geonextgis/paperatlas) on GitHub.
2. **Get a Web of Science API key** from
   [developer.clarivate.com](https://developer.clarivate.com/).
3. **Add the key as a repository secret**:
   *Settings → Secrets and variables → Actions → New repository secret*.
   Name it exactly `WOS_API_KEY`.
4. **Enable Pages**: *Settings → Pages → Build and deployment →
   Source → GitHub Actions*. Do not pick "Deploy from branch" — the
   workflow uploads its own artifact.
5. **Run the workflow once** from the Actions tab. After it finishes
   you'll have a live site at `https://<you>.github.io/<repo>/`.

That's the whole infrastructure side. From here on you are only editing
two YAML files.

---

## The one file that does most of the work: `query_config.yml`

Everything the script searches for lives in `query_config.yml`. The
Python script never hardcodes a query — change the YAML, push, and the
next run picks it up. Five sections matter.

### `site` — page title and tagline

```yaml
site:
  title: "Your Name — Research Feed"
  subtitle: "What you want the header to say"
```

### `topic_query.terms` — broad themes

Each line becomes its own query, scoped to your journals of interest
via `AND SO=(...)`. Use Web of Science wildcard syntax — a trailing `*`
matches any suffix.

```yaml
topic_query:
  terms:
    - "crop model*"           # matches model, models, modeling, modelling
    - "nitrogen dynamic*"
    - '"deep learning" AND "agriculture"'   # quotes lock the phrase
    - '"climate change" AND "crop*" AND "SSP"'
  year_from: 2022             # null for no lower bound
  year_to: CURRENT_YEAR       # literal string; resolves to today's year
```

Tips that took me a while to learn:

- **Quote multi-word phrases** or WoS will treat them as `word AND word`.
- **Don't put a wildcard at the start** of a token (`*model`). Suffix
  wildcards only.
- **Use parentheses around `AND/OR` groups** when terms get complex.
  The script auto-wraps if it sees an operator, but explicit is safer.
- **One term per line is the right unit.** Each becomes its own audit
  entry with its own `hits` count, so you can see which terms are
  pulling weight and which are dead.

### `keywords` — narrow tags

Mechanically identical to `topic_query.terms` (same `TS=` query, same
journal scope, same year clause), but tagged separately so the audit
log distinguishes broad themes from specific keywords. Use this for
techniques, sensors, and named entities:

```yaml
keywords:
  - "Sentinel-2"
  - "convolutional neural network*"
  - "GeoAI"
```

### `journals_of_interest` — the strict allow-list

This list is doing **two** jobs:

1. It scopes every topic and keyword query (`AND SO=(...)`).
2. It drives a per-journal query, so the latest paper from each watched
   journal lands in the feed even if no topic query matched it.

A post-fetch guard then drops any WoS record whose source title isn't
on the list. So you genuinely cannot get papers from journals you
didn't list.

```yaml
journals_of_interest:
  - "FIELD CROPS RESEARCH"
  - "NATURE FOOD"
  - "REMOTE SENSING OF ENVIRONMENT"
```

Use the **exact** journal name as it appears in the WoS `SO=` field.
"NATURE FOOD" works; "Nat. Food" does not. If you're unsure, search
the journal once on the WoS web interface and copy the title exactly.

If you leave this list empty while topic terms are set, the script
aborts with a clear error — by design. An unscoped topic search
returns thousands of irrelevant papers.

### `arxiv` — preprints

arXiv is a separate source with its own syntax (`ti:`, `abs:`, `all:`,
`cat:`). Preprints bypass the journal allow-list (they aren't journals)
and dedupe against WoS by DOI when they have one.

```yaml
arxiv:
  enabled: true
  categories: ["cs.LG", "cs.CV", "stat.ML"]   # AND-combined with each query
  results_per_query: 25
  max_age_days: 365
  queries:
    - label: "Crop yield + DL"
      query: 'all:"crop yield" AND all:"deep learning"'
    - label: "Sentinel-2 segmentation"
      query: 'abs:"Sentinel-2" AND abs:segmentation'
```

Each query has a `label` (used in the audit log and on cards) and a
`query` in arXiv search syntax. Quote phrases. Combine fields with
`AND`/`OR`/`ANDNOT`.

---

## Publisher tabs: `publishers_config.yml`

The site groups journals into publisher tabs (Nature, Elsevier, Wiley,
Springer, MDPI, arXiv, …). The mapping lives in `publishers_config.yml`:

```yaml
publishers:
  - label: "Nature"
    patterns:
      - "^nature\\b"
      - "^npj\\b"
  - label: "Elsevier"
    patterns:
      - "^field crops research$"
      - "^remote sensing of environment$"

overrides:
  "Some Specific Journal": "Wiley"
```

`patterns` are case-insensitive regexes matched against the journal
name. The first publisher that matches wins; unmatched journals go
into "Other". `overrides` pin specific exact journal names and
override `patterns`. The Python script validates every regex compiles
before it writes the JSON, so a typo aborts the run instead of
silently miscategorising.

The site only renders tabs for publishers that have at least one
paper in the current data — empty groups are hidden automatically.

---

## Reading the audit log

After a run, open `data/publications.json` and look at the top-level
`queries` key. Each executed query is logged with the **full** string
sent to the API plus `hits` (returned by the API) and `new` (newly
added after dedup).

```jsonc
"queries": {
  "topic":   [{"label": "crop model*",  "query": "TS=(\"crop model*\") AND SO=(...)", "hits": 50, "new": 50}],
  "keyword": [{"label": "Sentinel-2",   "query": "TS=(\"Sentinel-2\") AND SO=(...)",  "hits": 50, "new": 27}],
  "journal": [{"label": "NATURE FOOD",  "query": "SO=(\"NATURE FOOD\")",              "hits": 50, "new": 36}],
  "arxiv":   [{"label": "Crop yield + DL", "query": "(...) AND (cat:cs.LG OR ...)",   "hits": 25, "new": 22}]
}
```

This is the single most useful debugging tool the project has. If a
term is returning zero hits, the query string in the log is exactly
what got sent — paste it into the WoS web interface and you'll see why.

---

## Local development

You don't need to push to GitHub to test changes. Drop a `.env` file
at the repo root:

```
WOS_API_KEY=your-key-here
```

The script auto-loads it (and `.env` is gitignored). Then:

```bash
pip install requests pyyaml
python scripts/fetch_publications.py
python -m http.server 8000
```

Open `http://localhost:8000` and you've got the live site reading the
freshly generated `data/publications.json`.

For pure CSS/HTML/JS tweaks you don't even need to refetch — the
workflow skips the fetch on `push` events for exactly this reason, so
your style changes deploy without burning API quota.

---

## Tuning advice from a few months of use

- **Start small.** Three or four topic terms, six or seven journals.
  You can always grow the lists; you'll quickly notice which queries
  are noise.
- **Watch the `new` column in the audit log.** A query with 50 hits
  and `new: 0` is fully covered by your other queries — consider
  dropping it. A query with 50 hits and `new: 50` is doing real work.
- **Prefer narrow journals over broad terms.** "Field Crops Research"
  as a journal entry gives you everything in that journal. Adding
  "field crops" as a topic term mostly produces duplicates.
- **arXiv preprints decay fast.** Set `max_age_days: 365` (or shorter)
  unless you specifically want historical preprints in the feed.
- **`results_per_query: 50` is the right default.** WoS pages are 50
  records each, so anything lower wastes a fetch and anything higher
  bumps the rate-limit ceiling without much benefit.

---

## When something breaks

- **Workflow fails with "missing WOS_API_KEY":** the secret name must be
  exact. Re-create it as `WOS_API_KEY`.
- **"journals_of_interest is empty" error:** add at least one journal,
  or the script refuses to run an unscoped search.
- **Zero papers returned from a topic term:** copy the `query` from
  `data/publications.json → queries.topic[i].query` into the WoS web
  UI. It's almost always a wildcard at the wrong end of a word, or an
  unquoted multi-word phrase.
- **A journal isn't appearing under the expected publisher tab:** add
  it to `overrides` in `publishers_config.yml` with the exact journal
  name as the key.
- **Site looks stale:** the workflow only fetches on `schedule` and
  `workflow_dispatch`, not on `push`. Trigger a manual run from the
  Actions tab.

---

## What this codebase is not trying to be

It is **not** a literature management tool. There is no Zotero export,
no PDF download, no annotation. The DOI link on each card is the
handoff — click through and use whatever reference manager you
already have.

It is **not** a recommender system. There is no learning, no
personalisation beyond the queries you write. If a query stops
producing useful results, you change the query. That is the whole
loop, and keeping it simple is the point.

---

If you fork this and build a feed for your own field, I would
genuinely like to see it — open an issue on the repo and link yours.

— *Krish*
