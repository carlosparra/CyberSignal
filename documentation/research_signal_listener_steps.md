# Research Signal Listener — 17 notebook steps

Step-by-step documentation for `research_signal_listener.ipynb`.
Threat-intelligence variant of the Cyber Prospect Radar: instead of looking for
buying intent, it surfaces **public defensive events** on X — ransomware
victims, breach disclosures, database sales, active malware campaigns,
exploits, operator chatter, and dark-web mentions. Final output: a prioritized
CSV for an internal CTI analyst or the sales team of a ransomware-protection
vendor.

---

## 1. Install Dependencies

Same cell as the sales notebook. Installs `requests`, `pandas`, `numpy`,
`python-dotenv`, `openai`, `matplotlib`, `scikit-learn`, `umap-learn`.

---

## 2. Imports and Configuration

Standard imports + `%matplotlib inline` + `.env` load for `X_BEARER_TOKEN`,
`OPENAI_API_KEY`, `OPENAI_MODEL`. Pipeline flags:

- `USE_LLM_CLASSIFIER = True` — enables the OpenAI second pass.
- `MAX_RESULTS_PER_QUERY = 10`, `SLEEP_BETWEEN_REQUESTS = 1.0`,
  `LLM_SAMPLE_SIZE = 20`.
- `OUTPUT_CSV = "x_research_signals.csv"` — separate from the sales CSV.
- `X_RECENT_SEARCH_URL` points to the same Recent Search v2 endpoint.

---

## 3. Search Taxonomy

`SEARCH_QUERIES` retargeted to threat-intel. 7 categories:

- `RANSOMWARE_VICTIM` — *"ransomware victim"*, *"added to leak site"*,
  *"ransomware attack on"*, group combos (LockBit, Qilin, Akira, BlackCat,
  ALPHV) with the word *"victim"*.
- `BREACH_DISCLOSURE` — *"data breach"*, *"security breach"*, *"breach
  disclosed"*, *"breach notification"*, *"notifying customers"*.
- `DATABASE_LEAK` — *"database for sale"*, *"selling database"*, *"leaked
  credentials"*, *"stealer logs"*, *"credential dump"*.
- `MALWARE_CAMPAIGN` — *"infostealer"*, *"RedLine stealer"*, *"Lumma stealer"*,
  *"malware campaign"*, *"phishing campaign"*, *"loader malware"*.
- `EXPLOIT_OR_VULN` — *"zero-day"*, *"0-day"*, *"exploit for sale"*, *"PoC
  released"*, *"CVE-2026"*.
- `RANSOMWARE_OPERATOR` — *"ransomware group"*, *"ransomware gang"*, *"data
  leak site"*, *"double extortion"*.
- `DARK_WEB_CHATTER` — *"dark web"*, *"underground forum"*, *"breachforums"*,
  *"onion site"*.

---

## 4. X API Connection

Functions identical to the sales notebook (conceptually shared):
`get_x_bearer_token`, `_normalize_x_post`, `search_recent_x_posts`,
`collect_x_posts`. Same normalized per-tweet schema.

---

## 5. Data Collection

Builds `raw_df` by calling `collect_x_posts` with the threat-intel taxonomy.
**Typical volume is much higher than sales (~250 rows vs ~93)** because
cyber-threat news has tracker accounts auto-posting dense feeds of victims
and CVEs.

---

## 6. Data Cleaning

Identical to the sales notebook: drop empties + dedup by `post_id` + date
normalization + `post_text_clean` with whitespace collapsed.

---

## 7. Rule-Based Classification

Adapted to the threat-intel domain:

- `SIGNAL_TERMS` covers 7 categories. For `RANSOMWARE_VICTIM` it avoids the
  generic *"claims responsibility for"* term (which was catching kinetic
  terrorism claims) and instead uses *"claims a ransomware attack"* and
  *"claims the ransomware attack"*, both cyber-specific.
- `PRIORITY_ORDER`:
  `RANSOMWARE_VICTIM > BREACH_DISCLOSURE > DATABASE_LEAK > MALWARE_CAMPAIGN > EXPLOIT_OR_VULN > RANSOMWARE_OPERATOR > DARK_WEB_CHATTER > NONE`.
- `ANTI_TERMS` for `RANSOMWARE_VICTIM` includes kinetic-violence markers
  captured from real runs: `ttp claims`, `isis claims`, `iskp`, `al-naba`,
  `khorasan province`, `tehreek-e-taliban`, `drone strike`, `attackers
  killed`, `security forces were killed`, `brg claims`, `bla claims`,
  `balochistan`, `tower sabotage`, `#sibbi`, `#zrumbesh`. The other categories
  start with empty anti-terms, ready to be tuned from real data.

`classify_signal_rule_based(text)` operates the same way: substring matching +
priority cascade + anti-term demotion.

---

## 8. Opportunity Scoring

Same functions as sales, base scores re-weighted for the defensive domain:

- `RANSOMWARE_VICTIM`: 45 (highest commercial urgency — confirmed victim).
- `BREACH_DISCLOSURE`: 40.
- `DATABASE_LEAK`: 35.
- `MALWARE_CAMPAIGN`: 30.
- `EXPLOIT_OR_VULN`: 25.
- `RANSOMWARE_OPERATOR`: 20.
- `DARK_WEB_CHATTER`: 15.
- `NONE`: 0.

Bucketing identical (`≥30 High`, `≥18 Medium`, `>0 Low`, `0 Ignore`).

---

## 9. Sales Intelligence Fields

Same three generators (`why_now`, `sales_angle`, `safe_outreach`) but the
texts are adapted to the threat-intel context. Notes:

- For `RANSOMWARE_VICTIM` and `BREACH_DISCLOSURE`, `safe_outreach` explicitly
  forbids contacting the named victim — it suggests a peer-segment briefing
  with neighbors in the same vertical.
- For `RANSOMWARE_OPERATOR` and `DARK_WEB_CHATTER`, the sales angle says
  *"internal tracking only — not an outreach target"*. No commercial outreach
  is performed on operators or on underground-forum references.

---

## 10. Apply Pipeline

Same flow as sales:

1. Rule-based classification.
2. Scoring + priority.
3. Sales-intelligence generators.
4. **Tracker detection**: authors with ≥3 `RANSOMWARE_VICTIM` posts in the run
   are flagged `is_tracker=True` and capped at Low (ransomware.live,
   ransomwarewatch, automated feeds).
5. Sort by `priority_rank, opportunity_score, created_at`.

`FINAL_COLUMNS` orders the 21 final columns of the DataFrame.

---

## 11. Review Top Signals

Prints: top 20, only `High`, counts by `signal_type`, counts by `priority`.
With the current taxonomy, the Medium bucket usually includes notable
incidents (Foxconn / Nitrogen, Qilin / hospitals, Pakistani DB sale).

---

## 12. Visualizations

Three matplotlib figures, structurally identical to the sales notebook:

1. Bar chart of posts by `signal_type` (7 categories).
2. Bar chart of posts by `priority`.
3. Histogram of `opportunity_score`.

---

## 13. Optional LLM Classification

Same `classify_with_llm` but with the prompt rewritten for the role of a
**threat intelligence analyst** rather than a sales analyst. The prompt:

- Lists the 7 exact categories (`RANSOMWARE_VICTIM`, `BREACH_DISCLOSURE`,
  `DATABASE_LEAK`, `MALWARE_CAMPAIGN`, `EXPLOIT_OR_VULN`,
  `RANSOMWARE_OPERATOR`, `DARK_WEB_CHATTER`, `NONE`).
- Forbids inventing prefixes/suffixes (`WEAK_*`).
- Asks the model to classify as `NONE` when the post is vendor self-promotion,
  recap, listicle, or educational with no live incident.
- `temperature=0`, pure JSON.

Defensive validation: if the model returns a label outside the valid list,
snap to `NONE`. Sample size 20 → ~$0.001 USD per run.

---

## 14. Compare Rule-Based vs LLM

Disagreement table. Typical pattern observed: the LLM correctly filters
posts where trigger words appear in kinetic / off-topic contexts. Useful for
discovering new anti-terms.

---

## 15. Exploratory Analysis

Four lightweight analyses:

1. **Confusion matrix rule-based vs LLM** — matplotlib heatmap with the 8
   categories (7 + NONE) on both axes.
2. **Hashtag co-occurrence** — top 10 hashtags + matrix. Captures combos like
   `#ransomware #cti #cybersecurity` that dominate tracker accounts.
3. **Engagement vs priority** — symlog boxplot of engagement per bucket.
4. **Top recurring authors per signal_type** — key in threat-intel:
   identifies automated feeds (e.g., an author with 8+ `RANSOMWARE_VICTIM`
   posts = tracker bot).

---

## 16. Semantic Clustering with Embeddings

Embeddings with `text-embedding-3-small` → UMAP to 2D (PCA fallback) →
k-means with `k = min(6, len(emb)//10)`. UMAP receives `n_jobs=1` to silence
the parallelism warning that fires when `random_state` is fixed.

Common readings of the `cluster vs signal_type` crosstab for this notebook:

- **Tracker-feed cluster** (RANSOMWARE_VICTIM + RANSOMWARE_OPERATOR ~50/50)
  — auto-published leak-site monitoring posts; each names both victim AND
  group.
- **Event-driven cluster** (mostly RANSOMWARE_VICTIM on a single incident —
  Foxconn/Nitrogen) — multiple authors amplifying the same event. Useful: it
  tells you which incident is dominating the news cycle.
- **Pure dark-web cluster** (~63% DARK_WEB_CHATTER) — semantically
  well-defined category.
- **Breach + legal aftermath cluster** (BREACH_DISCLOSURE + NONE) — suggests a
  missing category: `BREACH_LEGAL_AFTERMATH` with queries for *"court ruling"*,
  *"data protection fine"*, *"GDPR fine"*.
- **Middle noise cluster** — the junk drawer; where the LLM second pass has
  the highest ROI.

---

## 17. Export Results

`signals_df.to_csv(OUTPUT_CSV, index=False)` writes `x_research_signals.csv`
with 21 base columns plus `engagement` and `cluster` (added in the EDA and
Clustering sections). Total 23 columns. Prints the absolute path.

The CSV is the handoff to a CTI analyst / sales analyst at CyberSignal or another
ransomware-protection vendor. Each row carries a `source_url` clickable to
the original tweet on X, `why_now` for context, `sales_angle` for the
approach, and `safe_outreach_suggestion` that explicitly forbids contacting
named victims.
