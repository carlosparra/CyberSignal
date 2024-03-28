# Cyber Prospect Radar — 17 notebook steps

Step-by-step documentation for `cyber_prospect_radar_signal_listener.ipynb`.
Notebook objective: detect public signals on X that indicate buying intent,
vendor friction, operational pain, compliance triggers, hiring activity, or
industry risk for an endpoint-security sales team (EDR / MDR / XDR). Final
output: a CSV reviewable by a human.

---

## 1. Install Dependencies

Installs the required libraries with `!pip install`. List: `requests`,
`pandas`, `numpy`, `python-dotenv`, `openai`, `matplotlib`, `scikit-learn`,
`umap-learn`. Only needs to run the first time; after that the cell can be
commented out to speed up reruns.

---

## 2. Imports and Configuration

Standard imports plus `%matplotlib inline` so figures render embedded in
Jupyter. Loads `.env` with `load_dotenv()` to read the bearer token and the
OpenAI API key without ever printing them. Defines the pipeline flags:

- `USE_LLM_CLASSIFIER = True` enables the OpenAI second pass.
- `MAX_RESULTS_PER_QUERY = 10` — how many tweets per query.
- `SLEEP_BETWEEN_REQUESTS = 1.0` — pause between calls to respect rate limits.
- `LLM_SAMPLE_SIZE = 20` — how many posts go through the LLM.
- `OUTPUT_CSV = "x_endpoint_sales_signals.csv"` — name of the final CSV.
- `X_RECENT_SEARCH_URL` — X API v2 Recent Search endpoint.

---

## 3. Search Taxonomy

Defines `SEARCH_QUERIES`: a dictionary with 6 commercial categories, each with
several X-API-ready queries:

- `BUYING_INTENT` — *"looking for EDR"*, *"best EDR"*, *"need MDR"*.
- `COMPETITOR_PAIN` — *"alternatives to CrowdStrike"*, *"switching from Defender"*.
- `OPERATIONAL_PAIN` — *"alert fatigue"*, *"small security team"*, *"no SOC team"*.
- `COMPLIANCE_TRIGGER` — *"SOC 2 audit"*, *"ISO 27001"*, *"cyber insurance requirements"*.
- `HIRING_SIGNAL` — *"hiring SOC analyst"*, *"new CISO"*, *"hiring security engineer"*.
- `INDUSTRY_RISK` — *"hospital ransomware"*, *"manufacturing ransomware"*, etc.

Queries combine `OR` operators, quoted exact phrases, and the names of the main
vendors.

---

## 4. X API Connection

Defines three helper functions:

- `get_x_bearer_token()` — resolves the bearer token from the `X_BEARER_TOKEN`
  environment variable and, if missing, asks for it via `getpass` (hidden input).
- `search_recent_x_posts(query, bearer_token, max_results)` — GETs
  `https://api.x.com/2/tweets/search/recent`, requests the `created_at`,
  `author_id`, `public_metrics`, `lang` fields, handles non-200 errors by
  printing a short diagnostic and returning an empty list.
- `collect_x_posts(search_queries, bearer_token, max_results_per_query)` —
  iterates the taxonomy, applies `time.sleep` between requests, and marks each
  post with its `initial_signal_type` (the category of the query that brought
  it in).

The normalized schema for each post includes: `platform`, `post_id`,
`created_at`, `author_id`, `post_text`, `matched_query`, `initial_signal_type`,
`like_count`, `reply_count`, `retweet_count`, `quote_count`, `source_url`.

---

## 5. Data Collection

Calls `collect_x_posts` with all queries and builds `raw_df`. If no bearer
token is available, raises `RuntimeError`. Prints the DataFrame shape and
shows `head()`. Typical volume: 90-100 rows with the current taxonomy.

---

## 6. Data Cleaning

`clean_posts_df(df)` applies:

1. Drops rows with empty `post_text`.
2. Drops duplicates by `post_id` (the same tweet seen by multiple queries).
3. Normalizes `created_at` to UTC `datetime`.
4. Creates a `post_text_clean` column collapsing repeated whitespace via regex.
5. Resets the index.

Preserves the original `post_text` unchanged. Produces `clean_df`.

---

## 7. Rule-Based Classification

Core of the classifier. Three pieces:

- `SIGNAL_TERMS` — dictionary of substrings per category (lowercase). Includes
  punctuation variants observed in real X data (*"hiring: SOC analyst"*,
  *"hiring! security engineer"*) and hashtag combos for INDUSTRY_RISK.
- `PRIORITY_ORDER` — defines which category wins when a post matches several:
  `BUYING_INTENT > COMPETITOR_PAIN > OPERATIONAL_PAIN > COMPLIANCE_TRIGGER > HIRING_SIGNAL > INDUSTRY_RISK > NONE`.
- `ANTI_TERMS` — negative terms that demote a match back to `NONE`. Captured
  from real false positives: book promos for *"First 100 Days of the New CISO"*,
  @MessariCrypto posts, educational content, positive Defender reviews.

`classify_signal_rule_based(text)` returns `{signal_type, confidence,
matched_terms}`. `confidence` starts at 60 with 1 matching term and grows
by +20 per additional term, capped at 100. If an anti-term hits the text, it
returns NONE with `matched_terms = [demoted_from_X, ...]` for auditability.

---

## 8. Opportunity Scoring

Two functions:

- `score_signal(signal_type, confidence)` — computes `opportunity_score` as
  `min(100, int(BASE_SCORES[type] * confidence / 100))`. Base scores:
  BUYING_INTENT=40, COMPETITOR_PAIN=35, OPERATIONAL_PAIN=30, COMPLIANCE=25,
  HIRING=20, INDUSTRY_RISK=15, NONE=0.
- `priority_from_score(score)` — buckets: `≥30 High`, `≥18 Medium`, `>0 Low`,
  `0 Ignore`.

This is what the SDR consumes: the `priority` column decides what they review
first.

---

## 9. Sales Intelligence Fields

Three functions that map `signal_type` to pre-written text for the human
reviewer:

- `generate_why_now(signal_type)` — explains why this signal matters now.
- `generate_sales_angle(signal_type)` — the suggested commercial angle.
- `generate_safe_outreach(signal_type)` — safe, non-invasive outreach
  suggestion, never asserting vulnerability or compromise.

The texts are internal hints for the human, not ready-to-send messages.

---

## 10. Apply Pipeline

Builds `signals_df` applying, in order:

1. Rule-based classification.
2. Scoring + priority.
3. Generation of the 3 sales-intelligence fields.
4. **Tracker detection**: authors with ≥3 INDUSTRY_RISK posts in the same run
   are flagged `is_tracker=True` and their priority is capped at Low (they are
   automated leak-site monitoring feeds, not leads).
5. Sort by `priority_rank ASC, opportunity_score DESC, created_at DESC`.

`FINAL_COLUMNS` defines the 21 columns of the final CSV.

---

## 11. Review Top Signals

Prints four quick views for eyeball audit:

- Top 20 signals (`signal_type`, `priority`, `opportunity_score`, `post_text`).
- Only the `High` priority rows.
- Counts by `signal_type`.
- Counts by `priority`.

This is the fast check before export.

---

## 12. Visualizations

Three matplotlib figures, each in its own figure (no seaborn):

1. Bar chart of posts by `signal_type`.
2. Bar chart of posts by `priority` (ordered High → Medium → Low → Ignore).
3. Histogram of `opportunity_score` (10 bins).

---

## 13. Optional LLM Classification

Second pass with OpenAI controlled by `USE_LLM_CLASSIFIER`. Reads
`OPENAI_API_KEY` and `OPENAI_MODEL` (default `gpt-4o-mini`) from `.env`.

`classify_with_llm(post_text, client, model)` sends the post to the LLM with
`temperature=0` and a prompt that:

- Restricts `signal_type` to the exact 7 categories (no `WEAK_*` prefixes).
- Defines `confidence` as an integer 0-100.
- Asks for pure JSON, no fences, no prose.
- Explicitly tells the model that content marketing, vendor promo, listicles,
  and conference recaps should go to NONE.

Defensive post-response validation: if the LLM invents a label outside the
valid list, snap to `NONE`. Coerces `confidence` to int or 0.

Processes only the top `LLM_SAMPLE_SIZE` (20) posts to control cost
(~$0.001 USD per run with `gpt-4o-mini`). `time.sleep(0.5)` between calls.

---

## 14. Compare Rule-Based vs LLM

Shows rows where rule-based and LLM disagreed (`signal_type !=
llm_signal_type`). Useful to detect rules with false positives: when the LLM
says NONE but rule-based said something, it is usually content marketing or
off-topic content that wants a new anti-term.

---

## 15. Exploratory Analysis

Four lightweight analyses over `signals_df`:

1. **Confusion matrix rule-based vs LLM** — matplotlib heatmap with cell
   counts. Shows where the two classifiers disagree across the 20 LLM samples.
2. **Hashtag co-occurrence** — top 10 hashtags + co-occurrence matrix.
   Captures industry patterns automatically (#cybersecurity + #healthcare).
3. **Engagement vs priority** — boxplot of `like_count + reply_count +
   retweet_count + quote_count` per priority bucket (symlog Y-axis).
4. **Top recurring authors per signal_type** — who posts a lot of each
   category. Useful to identify tracker accounts or recurring vendors.

---

## 16. Semantic Clustering with Embeddings

The richest step: embed every post with `text-embedding-3-small` from OpenAI
(~$0.001), reduce to 2D with UMAP (PCA fallback if UMAP is missing), k-means
clustering with `k = min(6, len(emb)//10)`. Passes `n_jobs=1` to UMAP to
silence the parallelism warning that fires with `random_state`.

Produces three outputs:

- 2D scatter plot colored by `signal_type` (rule-based).
- 2D scatter plot colored by `cluster` (k-means).
- `cluster vs signal_type` crosstab to validate the taxonomy.
- Shows a representative post per cluster.

Four patterns to read in the crosstab:

| Pattern | Reading |
|---|---|
| Pure cluster (90%+ one category) | ✅ Taxonomy is correct for that category |
| Junk cluster (many categories mixed) | ⚠️ Rules are forcing labels onto generic content |
| Large NONE cluster | 🚨 An entire category is missing |
| Category split across many clusters | ❌ Category is incoherent; split or rename it |

---

## 17. Export Results

`signals_df.to_csv(OUTPUT_CSV, index=False)` writes the final CSV and prints
the absolute path. The `x_endpoint_sales_signals.csv` file contains 21 base
columns in order: `platform`, `post_id`, `created_at`, `author_id`,
`post_text`, `source_url`, `matched_query`, `initial_signal_type`,
`signal_type`, `confidence`, `matched_terms`, `opportunity_score`, `priority`,
`is_tracker`, `why_now`, `sales_angle`, `safe_outreach_suggestion`,
`like_count`, `reply_count`, `retweet_count`, `quote_count`.

Plus the columns dynamically added by the EDA and Clustering sections
(`engagement`, `cluster`) — total 23 columns in the exported CSV.