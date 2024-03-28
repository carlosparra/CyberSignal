"""Generates research_signal_listener.ipynb from cell definitions.

Threat-intelligence variant of the sales prospect radar: surfaces public
ransomware victims, breach disclosures, database leaks, malware campaigns,
exploits, ransomware operator chatter, and dark-web mentions on X.

Run once:  python build_research_notebook.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
NB_PATH = HERE / "research_signal_listener.ipynb"


def md(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


CELLS = []

# -----------------------------------------------------------------------------
# Title
# -----------------------------------------------------------------------------
CELLS.append(md("""# Research Signal Listener

**Objective:** detect public threat-intelligence chatter on X — ransomware victims, breach disclosures, leaked databases, malware campaigns, exploits, operator activity, dark-web mentions — and export a prioritized CSV for an internal CTI / sales analyst.
"""))



# -----------------------------------------------------------------------------
# 1. Install Dependencies
# -----------------------------------------------------------------------------
CELLS.append(md("""## 1. Install Dependencies

Run once. Comment out after the first execution to speed up reruns.
"""))

CELLS.append(code("""# Install required libraries. Safe to re-run.
!pip install -q requests pandas numpy python-dotenv openai matplotlib scikit-learn umap-learn
"""))

# -----------------------------------------------------------------------------
# 2. Imports and Configuration
# -----------------------------------------------------------------------------
CELLS.append(md("""## 2. Imports and Configuration

Loads dependencies and sets the pipeline knobs. The X bearer token is read at
data-collection time, never stored.
"""))

CELLS.append(code('''%matplotlib inline
import os
import re
import json
import time
import getpass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- Run mode ----------------------------------------------------------------
USE_LLM_CLASSIFIER = True         # False -> skip the OpenAI second-pass classifier

# --- Pipeline knobs ----------------------------------------------------------
MAX_RESULTS_PER_QUERY = 10
SLEEP_BETWEEN_REQUESTS = 1.0
LLM_SAMPLE_SIZE = 20
OUTPUT_CSV = "x_research_signals.csv"

# X API endpoint (Recent Search v2).
X_RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"

print(f"USE_LLM_CLASSIFIER = {USE_LLM_CLASSIFIER}")
'''))

# -----------------------------------------------------------------------------
# 3. Search Taxonomy
# -----------------------------------------------------------------------------
CELLS.append(md("""## 3. Search Taxonomy

`SEARCH_QUERIES` is the heart of the listener. Each key is a signal category;
each value is a list of X-API-ready query strings, plus simpler quoted keywords
for quick tests.
"""))

CELLS.append(code('''SEARCH_QUERIES = {
    "RANSOMWARE_VICTIM": [
        '"ransomware victim"',
        '"added to leak site"',
        '"ransomware attack on"',
        '("LockBit" OR "Qilin" OR "Akira" OR "BlackCat" OR "ALPHV") "victim"',
        '"claims responsibility for"',
    ],
    "BREACH_DISCLOSURE": [
        '"data breach"',
        '"security breach"',
        '"breach disclosed"',
        '"breach notification"',
        '"notifying customers"',
    ],
    "DATABASE_LEAK": [
        '"database for sale"',
        '"selling database"',
        '"leaked credentials"',
        '"stealer logs"',
        '"credential dump"',
    ],
    "MALWARE_CAMPAIGN": [
        '"infostealer"',
        '"RedLine stealer"',
        '"Lumma stealer"',
        '"malware campaign"',
        '"phishing campaign"',
        '"loader malware"',
    ],
    "EXPLOIT_OR_VULN": [
        '"zero-day"',
        '"0-day"',
        '"exploit for sale"',
        '"PoC released"',
        '"CVE-2026"',
    ],
    "RANSOMWARE_OPERATOR": [
        '"ransomware group"',
        '"ransomware gang"',
        '"data leak site"',
        '"double extortion"',
    ],
    "DARK_WEB_CHATTER": [
        '"dark web"',
        '"underground forum"',
        '"breachforums"',
        '"onion site"',
    ],
}

for k, v in SEARCH_QUERIES.items():
    print(f"{k}: {len(v)} queries")
'''))


# -----------------------------------------------------------------------------
# 4. X API Connection
# -----------------------------------------------------------------------------
CELLS.append(md("""## 4. X API Connection

Three helpers:

- `get_x_bearer_token()` resolves the token from `X_BEARER_TOKEN` env var first,
  then prompts via `getpass` (input is hidden, never printed).
- `search_recent_x_posts(query, bearer_token, max_results)` calls X Recent Search
  and returns a list of **normalized** posts. Any non-200 status prints a short
  diagnostic and returns `[]` — the notebook keeps moving.
- `collect_x_posts(...)` iterates the taxonomy, tagging each post with its
  `initial_signal_type` and respecting `SLEEP_BETWEEN_REQUESTS`.
"""))

CELLS.append(code('''def get_x_bearer_token() -> Optional[str]:
    """Resolve the X bearer token from env first, then prompt via getpass.

    Never prints the token. Returns None if the user provides nothing.
    """
    token = os.getenv("X_BEARER_TOKEN")
    if token:
        return token
    try:
        token = getpass.getpass("Paste your X_BEARER_TOKEN (input hidden): ").strip()
        return token or None
    except Exception:
        return None


def _normalize_x_post(raw: dict, matched_query: str, initial_signal_type: str) -> dict:
    """Map a raw X API tweet object to the project's normalized schema."""
    metrics = raw.get("public_metrics", {}) or {}
    post_id = raw.get("id", "")
    return {
        "platform": "x",
        "post_id": post_id,
        "created_at": raw.get("created_at", ""),
        "author_id": raw.get("author_id", ""),
        "post_text": raw.get("text", "") or "",
        "matched_query": matched_query,
        "initial_signal_type": initial_signal_type,
        "like_count": int(metrics.get("like_count", 0) or 0),
        "reply_count": int(metrics.get("reply_count", 0) or 0),
        "retweet_count": int(metrics.get("retweet_count", 0) or 0),
        "quote_count": int(metrics.get("quote_count", 0) or 0),
        "source_url": f"https://x.com/i/web/status/{post_id}",
    }


def search_recent_x_posts(query: str, bearer_token: str, max_results: int = 10) -> list:
    """Call X API Recent Search and return a list of normalized post dicts.

    On any non-200 response or transport error, prints a short diagnostic
    and returns an empty list instead of raising.
    """
    if not bearer_token:
        print("[search_recent_x_posts] missing bearer_token, skipping.")
        return []

    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "query": query,
        # X API requires max_results in [10, 100].
        "max_results": max(10, min(int(max_results), 100)),
        "tweet.fields": "created_at,author_id,public_metrics,lang",
    }

    try:
        resp = requests.get(X_RECENT_SEARCH_URL, headers=headers, params=params, timeout=30)
    except requests.RequestException as exc:
        print(f"[search_recent_x_posts] transport error for query={query!r}: {exc}")
        return []

    if resp.status_code != 200:
        # Never echo the token back; only the response body excerpt.
        print(f"[search_recent_x_posts] HTTP {resp.status_code} for query={query!r}: {resp.text[:200]}")
        return []

    data = resp.json().get("data", []) or []
    return [_normalize_x_post(r, matched_query=query, initial_signal_type="") for r in data]


def collect_x_posts(search_queries: dict, bearer_token: str, max_results_per_query: int = 10) -> list:
    """Iterate the taxonomy, calling ``search_recent_x_posts`` for every query.

    The ``initial_signal_type`` is filled from the taxonomy key (e.g. BUYING_INTENT)
    so it can later be compared against the rule-based classifier output.
    """
    collected = []
    for signal_type, queries in search_queries.items():
        for q in queries:
            posts = search_recent_x_posts(q, bearer_token, max_results=max_results_per_query)
            for p in posts:
                p["initial_signal_type"] = signal_type
            collected.extend(posts)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
    return collected
'''))

# -----------------------------------------------------------------------------
# 5. Data Collection
# -----------------------------------------------------------------------------
CELLS.append(md("""## 5. Data Collection

Walks the taxonomy against the X API and builds `raw_df`. Requires `X_BEARER_TOKEN`.
"""))

CELLS.append(code('''bearer = get_x_bearer_token()
if not bearer:
    raise RuntimeError("X_BEARER_TOKEN is required to run this notebook.")

raw_posts = collect_x_posts(SEARCH_QUERIES, bearer, max_results_per_query=MAX_RESULTS_PER_QUERY)
print(f"Collected {len(raw_posts)} posts from X API.")

raw_df = pd.DataFrame(raw_posts)
print("raw_df.shape =", raw_df.shape)
raw_df.head()
'''))

# -----------------------------------------------------------------------------
# 6. Data Cleaning
# -----------------------------------------------------------------------------
CELLS.append(md("""## 6. Data Cleaning

`clean_posts_df()` drops empty rows, de-duplicates by `post_id`, normalizes
timestamps, and adds a whitespace-collapsed `post_text_clean` while preserving
the original `post_text`.
"""))

CELLS.append(code('''def clean_posts_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop empty / duplicate posts, normalize timestamps, add ``post_text_clean``.

    Preserves the original ``post_text`` column untouched.
    """
    if df.empty:
        return df.copy()

    out = df.copy()
    out = out[out["post_text"].astype(str).str.strip() != ""]
    out = out.drop_duplicates(subset=["post_id"], keep="first")

    out["created_at"] = pd.to_datetime(out["created_at"], errors="coerce", utc=True)

    def _clean(text: str) -> str:
        t = str(text)
        t = re.sub(r"\\s+", " ", t)  # collapse newlines + repeated whitespace
        return t.strip()

    out["post_text_clean"] = out["post_text"].map(_clean)
    return out.reset_index(drop=True)


clean_df = clean_posts_df(raw_df)
print("clean_df.shape =", clean_df.shape)
clean_df.head()
'''))

# -----------------------------------------------------------------------------
# 7. Rule-Based Classification
# -----------------------------------------------------------------------------
CELLS.append(md("""## 7. Rule-Based Classification

`classify_signal_rule_based(text)` runs simple substring matching against a
dictionary of signal terms. A post may match multiple categories; the function
picks the **primary** category using the priority order
`RANSOMWARE_VICTIM > BREACH_DISCLOSURE > DATABASE_LEAK > MALWARE_CAMPAIGN > EXPLOIT_OR_VULN > RANSOMWARE_OPERATOR > DARK_WEB_CHATTER > NONE`.
Confidence grows with the number of matched terms (capped at 100).
"""))

CELLS.append(code('''SIGNAL_TERMS = {
    "RANSOMWARE_VICTIM": [
        "ransomware victim", "added to leak site", "ransomware attack on",
        "hit by ransomware", "victim of ransomware",
        "publicly listed", "added to the leak site", "claimed by lockbit",
        "claimed by qilin", "claimed by akira",
        # Cyber-specific attribution patterns (NOT generic "claims responsibility for"
        # which captured ISIS / TTP / BRG / BLA / Al-Shabaab kinetic claims).
        "claims the ransomware attack",
        "claims a ransomware attack",
    ],
    "BREACH_DISCLOSURE": [
        "data breach", "security breach", "breach disclosed", "breach notification",
        "breach notice", "notifying customers", "breach affecting",
        "breach impacting",
    ],
    "DATABASE_LEAK": [
        "database for sale", "selling database", "leaked credentials",
        "stealer logs", "credential dump", "leaked database",
        "data dump", "leaked records", "combolist",
    ],
    "MALWARE_CAMPAIGN": [
        "infostealer", "redline stealer", "lumma stealer", "raccoon stealer",
        "vidar stealer", "stealc", "amadey loader",
        "malware campaign", "phishing campaign", "icedid", "qakbot",
        "loader malware", "trojan campaign",
    ],
    "EXPLOIT_OR_VULN": [
        "zero-day", "zero day", "0-day", "0day exploit",
        "exploit for sale", "poc released", "proof of concept",
        "cve-2026", "cve-2025",
    ],
    "RANSOMWARE_OPERATOR": [
        "ransomware group", "ransomware gang", "ransomware operator",
        "data leak site", "double extortion", "triple extortion",
        "lockbit affiliate", "alphv affiliate",
        "play ransomware", "clop ransomware", "rhysida",
    ],
    "DARK_WEB_CHATTER": [
        "dark web", "darkweb", "underground forum", "breached forum",
        "breachforums", "onion site", "leak forum", "tor forum",
    ],
}

PRIORITY_ORDER = [
    "RANSOMWARE_VICTIM",
    "BREACH_DISCLOSURE",
    "DATABASE_LEAK",
    "MALWARE_CAMPAIGN",
    "EXPLOIT_OR_VULN",
    "RANSOMWARE_OPERATOR",
    "DARK_WEB_CHATTER",
]


# Anti-terms tuned from the first live run. Drop a post to NONE if it matches
# any of these patterns even though the category-positive terms also hit.
ANTI_TERMS = {
    "RANSOMWARE_VICTIM": [
        # Kinetic / terrorism content that hits "claims responsibility for".
        "ttp claims",
        "isis claims",
        "iskp",
        "isis-k",
        "al-naba",
        "khorasan province",
        "tehreek-e-taliban",
        "drone strike",
        "attackers killed",
        "security forces were killed",
        # Balochistan separatist sabotage (BRG, BLA, etc.).
        "brg claims",
        "bla claims",
        "balochistan",
        "tower sabotage",
        "#sibbi",
        "#zrumbesh",
    ],
    "BREACH_DISCLOSURE": [],
    "DATABASE_LEAK": [],
    "MALWARE_CAMPAIGN": [],
    "EXPLOIT_OR_VULN": [],
    "RANSOMWARE_OPERATOR": [],
    "DARK_WEB_CHATTER": [],
}


def classify_signal_rule_based(text: str) -> dict:
    """Classify a post into one signal_type using substring matching.

    Returns ``{"signal_type": ..., "confidence": 0-100, "matched_terms": [...]}``.
    Primary category is chosen via ``PRIORITY_ORDER`` when multiple match.

    If the primary category has any anti-term hit in the same text (book promo,
    positive review, off-topic context, etc.) the post is demoted to NONE with
    a ``demoted_from_<CATEGORY>`` marker in ``matched_terms`` for transparency.
    """
    if not isinstance(text, str) or not text.strip():
        return {"signal_type": "NONE", "confidence": 0, "matched_terms": []}

    lower = text.lower()
    hits = {sig: [] for sig in PRIORITY_ORDER}
    for sig, terms in SIGNAL_TERMS.items():
        for term in terms:
            if term in lower:
                hits[sig].append(term)

    for sig in PRIORITY_ORDER:
        if hits[sig]:
            anti_hits = [t for t in ANTI_TERMS.get(sig, []) if t in lower]
            if anti_hits:
                return {
                    "signal_type": "NONE",
                    "confidence": 0,
                    "matched_terms": [f"demoted_from_{sig}"] + anti_hits,
                }
            confidence = min(100, 60 + 20 * (len(hits[sig]) - 1))
            return {"signal_type": sig, "confidence": confidence, "matched_terms": hits[sig]}

    return {"signal_type": "NONE", "confidence": 0, "matched_terms": []}


# Quick sanity check.
for sample in [
    "Any MDR recommendations for a small healthcare clinic?",
    "Alert fatigue is real.",
    "Just had the best ramen of my life.",
]:
    print(sample, "->", classify_signal_rule_based(sample))
'''))

# -----------------------------------------------------------------------------
# 8. Opportunity Scoring
# -----------------------------------------------------------------------------
CELLS.append(md("""## 8. Opportunity Scoring

`score_signal(signal_type, confidence)` multiplies a per-category base score by
the confidence (0-100) and caps the result at 100. `priority_from_score(score)`
buckets the score into `High` / `Medium` / `Low` / `Ignore`.
"""))

CELLS.append(code('''BASE_SCORES = {
    "RANSOMWARE_VICTIM": 45,
    "BREACH_DISCLOSURE": 40,
    "DATABASE_LEAK": 35,
    "MALWARE_CAMPAIGN": 30,
    "EXPLOIT_OR_VULN": 25,
    "RANSOMWARE_OPERATOR": 20,
    "DARK_WEB_CHATTER": 15,
    "NONE": 0,
}


def score_signal(signal_type: str, confidence: int) -> int:
    """Compute the opportunity_score from base score * confidence / 100."""
    base = BASE_SCORES.get(signal_type, 0)
    return min(100, int(base * confidence / 100))


def priority_from_score(score: int) -> str:
    """Map a numeric opportunity_score to a priority bucket."""
    if score >= 30:
        return "High"
    if score >= 18:
        return "Medium"
    if score > 0:
        return "Low"
    return "Ignore"


# Quick check.
print(score_signal("RANSOMWARE_VICTIM", 80), priority_from_score(score_signal("RANSOMWARE_VICTIM", 80)))
print(score_signal("DARK_WEB_CHATTER", 60), priority_from_score(score_signal("DARK_WEB_CHATTER", 60)))
print(score_signal("NONE", 0), priority_from_score(0))
'''))

# -----------------------------------------------------------------------------
# 9. Sales Intelligence Fields
# -----------------------------------------------------------------------------
CELLS.append(md("""## 9. Sales Intelligence Fields

Three generators turn a `signal_type` into:

- `why_now` — a short, evidence-bounded reason this matters now.
- `sales_angle` — what an SDR could lead with internally.
- `safe_outreach_suggestion` — a non-invasive, professional outreach hint. **Never**
  references vulnerability, compromise, or surveillance.

These are internal hints for a human, not pre-written DMs.
"""))

CELLS.append(code('''WHY_NOW = {
    "RANSOMWARE_VICTIM": "Post names a confirmed ransomware victim -- peers in the same segment face an immediate buying trigger.",
    "BREACH_DISCLOSURE": "Post references an officially disclosed breach -- regulatory pressure typically opens budget for endpoint / detection upgrades.",
    "DATABASE_LEAK": "Post references credentials or a database being sold or leaked -- companies in the same vertical face elevated takeover risk.",
    "MALWARE_CAMPAIGN": "Post references an active malware campaign -- exposure is high in the targeted segments.",
    "EXPLOIT_OR_VULN": "Post references a zero-day or public PoC -- patching pressure and EDR detection tuning are urgent.",
    "RANSOMWARE_OPERATOR": "Post references an active ransomware operator -- track for early indicators on their next victim segment.",
    "DARK_WEB_CHATTER": "Post references dark-web or underground forum activity -- monitor for downstream consequences.",
    "NONE": "No clear threat-intel signal detected.",
}

SALES_ANGLE = {
    "RANSOMWARE_VICTIM": "Lead with a peer-segment briefing on how comparable companies hardened after a similar incident.",
    "BREACH_DISCLOSURE": "Lead with a compliance-aligned post-incident playbook (notification, scope, blast radius) -- not a product pitch.",
    "DATABASE_LEAK": "Lead with credential hygiene plus endpoint detection on stealer-malware artifacts.",
    "MALWARE_CAMPAIGN": "Share detection-engineering notes specific to the named family; offer a tuned rule pack.",
    "EXPLOIT_OR_VULN": "Lead with detection plus virtual-patching options while the vendor patch is rolled out.",
    "RANSOMWARE_OPERATOR": "Internal tracking only -- not an outreach target.",
    "DARK_WEB_CHATTER": "Internal tracking only -- not an outreach target.",
    "NONE": "No sales angle.",
}

SAFE_OUTREACH = {
    "RANSOMWARE_VICTIM": "Internal suggestion: do NOT contact the named victim. Share a generic peer-segment briefing with neighbors in the same vertical, framed as helpful, not opportunistic.",
    "BREACH_DISCLOSURE": "Internal suggestion: share a post-incident lessons-learned brief; never claim insight you do not have.",
    "DATABASE_LEAK": "Internal suggestion: share a credential-hygiene plus endpoint detection brief for the vertical; do not reference specific leaked datasets.",
    "MALWARE_CAMPAIGN": "Internal suggestion: share IoC / detection notes framed as community contribution, not pitch.",
    "EXPLOIT_OR_VULN": "Internal suggestion: share detection and mitigation steps; do NOT weaponize public PoCs in outreach.",
    "RANSOMWARE_OPERATOR": "Internal tracking only. Do NOT engage with or amplify operator content.",
    "DARK_WEB_CHATTER": "Internal tracking only. Do NOT visit linked dark-web resources from corporate infrastructure.",
    "NONE": "No outreach suggested.",
}


def generate_why_now(signal_type: str) -> str:
    """Return a short, evidence-bounded reason this signal matters now."""
    return WHY_NOW.get(signal_type, WHY_NOW["NONE"])


def generate_sales_angle(signal_type: str) -> str:
    """Return a suggested internal sales angle for this signal type."""
    return SALES_ANGLE.get(signal_type, SALES_ANGLE["NONE"])


def generate_safe_outreach(signal_type: str) -> str:
    """Return a safe, non-invasive internal outreach suggestion."""
    return SAFE_OUTREACH.get(signal_type, SAFE_OUTREACH["NONE"])
'''))

# -----------------------------------------------------------------------------
# 10. Apply Pipeline
# -----------------------------------------------------------------------------
CELLS.append(md("""## 10. Apply Pipeline

Glues the previous steps into a single DataFrame, `signals_df`, sorted by
priority then by `opportunity_score` then by recency.
"""))

CELLS.append(code('''PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2, "Ignore": 3}

classified = clean_df["post_text_clean"].map(classify_signal_rule_based)
signals_df = clean_df.copy()
signals_df["signal_type"] = classified.map(lambda r: r["signal_type"])
signals_df["confidence"] = classified.map(lambda r: r["confidence"])
signals_df["matched_terms"] = classified.map(lambda r: r["matched_terms"])
signals_df["opportunity_score"] = signals_df.apply(
    lambda r: score_signal(r["signal_type"], r["confidence"]), axis=1
)
signals_df["priority"] = signals_df["opportunity_score"].map(priority_from_score)
signals_df["why_now"] = signals_df["signal_type"].map(generate_why_now)
signals_df["sales_angle"] = signals_df["signal_type"].map(generate_sales_angle)
signals_df["safe_outreach_suggestion"] = signals_df["signal_type"].map(generate_safe_outreach)

# Tracker / bot detection: authors who post >= 3 RANSOMWARE_VICTIM signals in
# this run are almost always automated leak-site / breach trackers. Useful as a
# feed, not as leads -- so we flag them and cap their priority at "Low".
TRACKER_VICTIM_MIN = 3
ir = signals_df[signals_df["signal_type"] == "RANSOMWARE_VICTIM"].groupby("author_id").size()
tracker_authors = set(ir[ir >= TRACKER_VICTIM_MIN].index)
signals_df["is_tracker"] = signals_df["author_id"].isin(tracker_authors)
demote_mask = signals_df["is_tracker"] & signals_df["priority"].isin(["High", "Medium"])
signals_df.loc[demote_mask, "priority"] = "Low"

signals_df["priority_rank"] = signals_df["priority"].map(PRIORITY_RANK)
signals_df = signals_df.sort_values(
    by=["priority_rank", "opportunity_score", "created_at"],
    ascending=[True, False, False],
).reset_index(drop=True)

FINAL_COLUMNS = [
    "platform", "post_id", "created_at", "author_id", "post_text", "source_url",
    "matched_query", "initial_signal_type", "signal_type", "confidence",
    "matched_terms", "opportunity_score", "priority", "is_tracker",
    "why_now", "sales_angle", "safe_outreach_suggestion",
    "like_count", "reply_count", "retweet_count", "quote_count",
]
signals_df = signals_df[FINAL_COLUMNS]
print("signals_df.shape =", signals_df.shape)
signals_df.head()
'''))

# -----------------------------------------------------------------------------
# 11. Review Top Signals
# -----------------------------------------------------------------------------
CELLS.append(md("""## 11. Review Top Signals

A quick eyeball pass before exporting.
"""))

CELLS.append(code('''pd.set_option("display.max_colwidth", 120)

print("--- Top 20 signals ---")
print(signals_df.head(20)[["signal_type", "priority", "opportunity_score", "post_text"]])

print("\\n--- High priority only ---")
high = signals_df[signals_df["priority"] == "High"]
print(high[["signal_type", "opportunity_score", "post_text"]])

print("\\n--- Counts by signal_type ---")
print(signals_df["signal_type"].value_counts())

print("\\n--- Counts by priority ---")
print(signals_df["priority"].value_counts())
'''))

# -----------------------------------------------------------------------------
# 12. Visualizations
# -----------------------------------------------------------------------------
CELLS.append(md("""## 12. Visualizations

Three matplotlib charts, each in its own figure. No seaborn. No hard-coded colors.
"""))

CELLS.append(code('''fig1, ax1 = plt.subplots(figsize=(8, 4))
signals_df["signal_type"].value_counts().plot(kind="bar", ax=ax1)
ax1.set_title("Posts by signal_type")
ax1.set_xlabel("signal_type")
ax1.set_ylabel("count")
plt.tight_layout()
plt.show()

fig2, ax2 = plt.subplots(figsize=(6, 4))
signals_df["priority"].value_counts().reindex(["High", "Medium", "Low", "Ignore"]).fillna(0).plot(kind="bar", ax=ax2)
ax2.set_title("Posts by priority")
ax2.set_xlabel("priority")
ax2.set_ylabel("count")
plt.tight_layout()
plt.show()

fig3, ax3 = plt.subplots(figsize=(6, 4))
ax3.hist(signals_df["opportunity_score"], bins=10)
ax3.set_title("Distribution of opportunity_score")
ax3.set_xlabel("opportunity_score")
ax3.set_ylabel("count")
plt.tight_layout()
plt.show()
'''))

# -----------------------------------------------------------------------------
# 13. Optional LLM Classification
# -----------------------------------------------------------------------------
CELLS.append(md("""## 13. Optional LLM Classification

When `USE_LLM_CLASSIFIER = True` the notebook samples the top `LLM_SAMPLE_SIZE`
posts and runs them through an OpenAI model with `temperature=0`. The prompt
forbids inferring private facts and forbids claiming compromise.

If the call fails or the response is not valid JSON, the classifier returns a
`NONE / 0` result and continues.
"""))

CELLS.append(code('''LLM_PROMPT_TEMPLATE = """You are a cybersecurity threat-intelligence analyst.

Analyze the following public X post and classify whether it contains a defender-relevant threat signal -- a named ransomware victim, a breach disclosure, leaked credentials or database, an active malware campaign, an exploit or CVE, ransomware operator activity, or dark-web chatter.

Rules:
- Use only the post text.
- Do not infer private facts.
- Do not claim a company is compromised unless the post explicitly says so.
- ``signal_type`` MUST be exactly one of: RANSOMWARE_VICTIM, BREACH_DISCLOSURE, DATABASE_LEAK, MALWARE_CAMPAIGN, EXPLOIT_OR_VULN, RANSOMWARE_OPERATOR, DARK_WEB_CHATTER, NONE. Do not add prefixes, suffixes, qualifiers, or new categories.
- If the signal is weak, keep the same ``signal_type`` and set ``confidence`` below 30. Do not invent labels like WEAK_*.
- If the post is a vendor self-promotion, product recap, listicle, or pure educational content with no live incident or active threat, classify as NONE.
- ``confidence`` is an integer 0-100.
- Return JSON only, no prose, no code fences.

Post:
{post_text}

Return:
{{
  "is_relevant": true,
  "signal_type": "RANSOMWARE_VICTIM",
  "confidence": 0,
  "why_it_matters": "",
  "recommended_sales_angle": "",
  "safe_outreach_suggestion": ""
}}"""


def _empty_llm_result() -> dict:
    return {
        "is_relevant": False,
        "signal_type": "NONE",
        "confidence": 0,
        "why_it_matters": "",
        "recommended_sales_angle": "",
        "safe_outreach_suggestion": "",
    }


def classify_with_llm(post_text: str, client=None, model: str = "gpt-4o-mini") -> dict:
    """Classify a single post using OpenAI. Returns a NONE result on any failure."""
    if client is None or not post_text:
        return _empty_llm_result()
    prompt = LLM_PROMPT_TEMPLATE.format(post_text=post_text)
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content or ""
        # Strip optional code fences before parsing.
        content = re.sub(r"^```(json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(content)
        out = _empty_llm_result()
        out.update({k: parsed.get(k, out[k]) for k in out.keys()})
        # Defensive: if the model invents a label, snap back to NONE.
        valid = {"RANSOMWARE_VICTIM", "BREACH_DISCLOSURE", "DATABASE_LEAK",
                 "MALWARE_CAMPAIGN", "EXPLOIT_OR_VULN", "RANSOMWARE_OPERATOR",
                 "DARK_WEB_CHATTER", "NONE"}
        if out["signal_type"] not in valid:
            out["signal_type"] = "NONE"
        try:
            out["confidence"] = int(out["confidence"])
        except (TypeError, ValueError):
            out["confidence"] = 0
        return out
    except Exception as exc:
        print(f"[classify_with_llm] error: {exc}")
        return _empty_llm_result()


llm_df = None
if USE_LLM_CLASSIFIER:
    try:
        from openai import OpenAI
    except ImportError:
        print("openai package not installed; skipping LLM classification.")
        OpenAI = None

    if OpenAI is not None:
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not openai_key:
            print("No OPENAI_API_KEY in environment; skipping LLM classification.")
        else:
            client = OpenAI(api_key=openai_key)
            sample = signals_df.head(LLM_SAMPLE_SIZE).copy()
            llm_results = []
            for txt in sample["post_text"]:
                llm_results.append(classify_with_llm(txt, client=client, model=openai_model))
                time.sleep(0.5)  # gentle on rate limits
            llm_df = sample.assign(
                llm_signal_type=[r["signal_type"] for r in llm_results],
                llm_confidence=[r["confidence"] for r in llm_results],
                llm_why_it_matters=[r["why_it_matters"] for r in llm_results],
                llm_recommended_sales_angle=[r["recommended_sales_angle"] for r in llm_results],
                llm_safe_outreach=[r["safe_outreach_suggestion"] for r in llm_results],
            )
            print(f"LLM classified {len(llm_df)} posts using model={openai_model}.")
else:
    print("USE_LLM_CLASSIFIER is False -- skipping LLM step.")
'''))

# -----------------------------------------------------------------------------
# 14. Compare Rule-Based vs LLM
# -----------------------------------------------------------------------------
CELLS.append(md("""## 14. Compare Rule-Based vs LLM

When both classifiers ran, we surface rows where they disagree. The LLM tends to
catch nuance the rule-based pass misses (reducing false positives) but costs
latency, dollars, and adds vendor risk. Use it as a second opinion, not as the
single source of truth.
"""))

CELLS.append(code('''if USE_LLM_CLASSIFIER and llm_df is not None:
    diff = llm_df[llm_df["signal_type"] != llm_df["llm_signal_type"]][
        ["post_id", "post_text", "signal_type", "llm_signal_type", "confidence", "llm_confidence"]
    ]
    print(f"Disagreements: {len(diff)} / {len(llm_df)}")
    print(diff.head(20))
    print("\\nNote: rule-based is cheap and deterministic; the LLM tends to reduce false positives")
    print("at the cost of latency, dollars and provider risk. Always keep a human in the loop.")
else:
    print("LLM comparison skipped.")
'''))

# -----------------------------------------------------------------------------
# 15. Exploratory Analysis
# -----------------------------------------------------------------------------
CELLS.append(md("""## 15. Exploratory Analysis

Four lightweight analyses over `signals_df` to validate the pipeline against the
real X data we just pulled:

1. Confusion matrix between rule-based and LLM signal types.
2. Hashtag co-occurrence among top hashtags.
3. Engagement (likes + replies + retweets) by priority.
4. Top recurring authors per signal_type.
"""))

CELLS.append(code('''import collections

# --- 1) Confusion matrix: rule-based vs LLM -----------------------------------
if USE_LLM_CLASSIFIER and llm_df is not None:
    rb_labels = ["RANSOMWARE_VICTIM", "BREACH_DISCLOSURE", "DATABASE_LEAK",
                 "MALWARE_CAMPAIGN", "EXPLOIT_OR_VULN", "RANSOMWARE_OPERATOR",
                 "DARK_WEB_CHATTER", "NONE"]
    pivot = pd.crosstab(llm_df["signal_type"], llm_df["llm_signal_type"]).reindex(
        index=rb_labels, columns=rb_labels, fill_value=0
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, cmap="Blues")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("LLM signal_type")
    ax.set_ylabel("Rule-based signal_type")
    ax.set_title("Confusion matrix: rule-based vs LLM (top sample)")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = int(pivot.values[i, j])
            if v:
                ax.text(j, i, v, ha="center", va="center", fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.show()
else:
    print("LLM did not run; confusion matrix skipped.")

# --- 2) Hashtag co-occurrence -------------------------------------------------
hashtag_re = re.compile(r"#(\\w+)", re.IGNORECASE)
tags_per_post = signals_df["post_text"].astype(str).map(
    lambda t: list({m.lower() for m in hashtag_re.findall(t)})
)
flat = [t for tags in tags_per_post for t in tags]
top_tags = collections.Counter(flat).most_common(10)
print("Top 10 hashtags:")
for tag, n in top_tags:
    print(f"  #{tag}: {n}")

if len(top_tags) >= 2:
    top_set = [t for t, _ in top_tags]
    cooc = pd.DataFrame(0, index=top_set, columns=top_set)
    for tags in tags_per_post:
        present = [t for t in tags if t in top_set]
        for a in present:
            for b in present:
                if a != b:
                    cooc.loc[a, b] += 1
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cooc.values, cmap="Greens")
    ax.set_xticks(range(len(top_set)))
    ax.set_yticks(range(len(top_set)))
    ax.set_xticklabels([f"#{t}" for t in top_set], rotation=45, ha="right")
    ax.set_yticklabels([f"#{t}" for t in top_set])
    ax.set_title("Hashtag co-occurrence among top 10")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.show()

# --- 3) Engagement by priority ------------------------------------------------
engagement = (
    signals_df["like_count"].fillna(0)
    + signals_df["reply_count"].fillna(0)
    + signals_df["retweet_count"].fillna(0)
    + signals_df["quote_count"].fillna(0)
)
signals_df["engagement"] = engagement.astype(int)
order = ["High", "Medium", "Low", "Ignore"]
data = [signals_df.loc[signals_df["priority"] == p, "engagement"].values for p in order]
fig, ax = plt.subplots(figsize=(7, 4))
ax.boxplot(data, tick_labels=order)
ax.set_yscale("symlog")
ax.set_ylabel("engagement (likes+replies+RTs+quotes)")
ax.set_title("Engagement by priority")
plt.tight_layout()
plt.show()

# --- 4) Top recurring authors per category ------------------------------------
print("Top recurring authors per signal_type (>= 2 posts):")
for cat in ["RANSOMWARE_VICTIM", "BREACH_DISCLOSURE", "DATABASE_LEAK",
            "MALWARE_CAMPAIGN", "EXPLOIT_OR_VULN", "RANSOMWARE_OPERATOR",
            "DARK_WEB_CHATTER"]:
    sub = signals_df[signals_df["signal_type"] == cat]
    if sub.empty:
        continue
    top = sub["author_id"].value_counts()
    top = top[top >= 2].head(5)
    if top.empty:
        continue
    print(f"\\n  {cat}:")
    for author, n in top.items():
        print(f"    author_id={author}  posts={n}")
'''))

# -----------------------------------------------------------------------------
# 16. Semantic Clustering with Embeddings
# -----------------------------------------------------------------------------
CELLS.append(md("""## 16. Semantic Clustering with Embeddings

Embed every cleaned post with OpenAI `text-embedding-3-small`, reduce to 2D with
UMAP (PCA fallback if UMAP is missing), cluster with k-means, and plot the
landscape colored by rule-based `signal_type`.

The cross-tab between cluster id and `signal_type` shows whether our taxonomy
matches the actual semantic structure of the data. A cluster dominated by
`NONE` posts hints at a missing category; a single signal_type spread across
many clusters hints at a category that is too broad.

Costs roughly $0.001 per run at 100 posts and `text-embedding-3-small` pricing.
"""))

CELLS.append(code('''openai_key = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

if not openai_key:
    print("No OPENAI_API_KEY in env; skipping semantic clustering.")
else:
    try:
        from openai import OpenAI
    except ImportError:
        print("openai package missing; skipping semantic clustering.")
    else:
        client = OpenAI(api_key=openai_key)
        texts = signals_df["post_text_clean"].fillna("").astype(str).tolist() \\
            if "post_text_clean" in signals_df.columns \\
            else signals_df["post_text"].fillna("").astype(str).tolist()

        # Batch the request; 100 texts per call is well within limits.
        BATCH = 100
        emb_rows = []
        for i in range(0, len(texts), BATCH):
            resp = client.embeddings.create(model=EMBED_MODEL, input=texts[i:i+BATCH])
            emb_rows.extend([d.embedding for d in resp.data])
        emb = np.array(emb_rows)
        print(f"Embeddings: shape={emb.shape}, model={EMBED_MODEL}")

        # 2D projection: prefer UMAP, fall back to PCA.
        try:
            import umap  # type: ignore
            n_neighbors = max(2, min(15, len(emb) - 1))
            reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=n_neighbors, n_jobs=1)
            emb_2d = reducer.fit_transform(emb)
            reducer_name = "UMAP"
        except Exception as exc:
            print(f"UMAP unavailable ({exc}); falling back to PCA.")
            from sklearn.decomposition import PCA
            emb_2d = PCA(n_components=2, random_state=42).fit_transform(emb)
            reducer_name = "PCA"

        # K-means clusters.
        from sklearn.cluster import KMeans
        k = min(6, max(2, len(emb) // 10))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        cluster_labels = km.fit_predict(emb)
        signals_df["cluster"] = cluster_labels
        print(f"K-means with k={k}.")

        # Scatter colored by rule-based signal_type.
        fig, ax = plt.subplots(figsize=(10, 7))
        for st in sorted(signals_df["signal_type"].unique()):
            mask = (signals_df["signal_type"].values == st)
            ax.scatter(emb_2d[mask, 0], emb_2d[mask, 1], label=st, alpha=0.75, s=45)
        ax.set_title(f"Semantic landscape ({reducer_name}, colored by rule-based signal_type)")
        ax.set_xlabel("dim 1")
        ax.set_ylabel("dim 2")
        ax.legend(loc="best", fontsize=8)
        plt.tight_layout()
        plt.show()

        # Scatter colored by k-means cluster.
        fig, ax = plt.subplots(figsize=(10, 7))
        for c in sorted(signals_df["cluster"].unique()):
            mask = (signals_df["cluster"].values == c)
            ax.scatter(emb_2d[mask, 0], emb_2d[mask, 1], label=f"cluster {c}", alpha=0.75, s=45)
        ax.set_title(f"Semantic landscape ({reducer_name}, colored by k-means cluster)")
        ax.set_xlabel("dim 1")
        ax.set_ylabel("dim 2")
        ax.legend(loc="best", fontsize=8)
        plt.tight_layout()
        plt.show()

        print("\\nCross-tab: cluster vs rule-based signal_type")
        print(pd.crosstab(signals_df["cluster"], signals_df["signal_type"]))

        print("\\nSample post per cluster:")
        for c in sorted(signals_df["cluster"].unique()):
            row = signals_df[signals_df["cluster"] == c].iloc[0]
            print(f"  cluster {c} ({row['signal_type']}): {row['post_text'][:140]}")
'''))

# -----------------------------------------------------------------------------
# 17. Export Results
# -----------------------------------------------------------------------------
CELLS.append(md("""## 17. Export Results

Dumps `signals_df` to CSV. The path is printed so it is easy to find in Colab
or in a local Jupyter session.
"""))

CELLS.append(code('''signals_df.to_csv(OUTPUT_CSV, index=False)
print(f"Wrote {len(signals_df)} rows to {os.path.abspath(OUTPUT_CSV)}")
'''))




# -----------------------------------------------------------------------------
# Notebook envelope
# -----------------------------------------------------------------------------
NB = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.10",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main() -> None:
    NB_PATH.write_text(json.dumps(NB, ensure_ascii=False, indent=1))
    print(f"Wrote {NB_PATH} ({NB_PATH.stat().st_size} bytes, {len(CELLS)} cells)")


if __name__ == "__main__":
    main()