# Cyber Prospect Radar

Notebook that listens to public posts on X to detect commercial signals for an
endpoint security sales team (EDR / MDR / XDR / ransomware protection / security
operations), classifies and prioritizes them, and exports a CSV for human review.

Pipeline:

1. Query public X posts using a focused taxonomy.
2. Normalize and clean the data.
3. Classify each post into one of six categories with auditable rules.
4. Assign `opportunity_score` and priority (`High` / `Medium` / `Low` / `Ignore`).
5. Add `why_now`, sales angle, and a **safe** outreach suggestion.
6. Optionally run a second pass with OpenAI (`temperature=0`).
7. Export `x_endpoint_sales_signals.csv` for human review.

**This is a signal generator for humans, not an automated outreach tool.**

## Repo

```
CyberSignal/
├── cyber_prospect_radar_x_signal_listener.ipynb   # notebook
├── build_notebook.py                              # regenerates the notebook
├── documentation/main.md                          # original spec
└── README.md
```

## How to run it

1. X developer account with **Recent Search** access.
2. Bearer token. Provide it via one of:
   - environment variable: `export X_BEARER_TOKEN=...`
   - `.env` in the repo root: `X_BEARER_TOKEN=...`
   - `getpass` prompt when the cell runs (input hidden, never printed).
3. Open the notebook:
   ```bash
   jupyter notebook cyber_prospect_radar_x_signal_listener.ipynb
   ```
4. *Run all*.

The notebook respects `SLEEP_BETWEEN_REQUESTS` (1.0s default) between calls and
handles non-200 responses without breaking the pipeline — prints a short
diagnostic and keeps going.

## Optional LLM second pass

1. `pip install openai` (already in the install cell).
2. Provide `OPENAI_API_KEY` via env var, `.env`, or `getpass`.
3. In the notebook: `USE_LLM_CLASSIFIER = True`.
4. The notebook samples the first `LLM_SAMPLE_SIZE` (20 default) posts and shows
   where the rule-based and LLM classifiers disagree.

## Environment variables

| Name              | Required for                       | Notes                                          |
|-------------------|------------------------------------|------------------------------------------------|
| `X_BEARER_TOKEN`  | always                             | `os.getenv` first, falls back to `getpass`.    |
| `OPENAI_API_KEY`  | optional LLM second pass           | Only read when `USE_LLM_CLASSIFIER = True`.    |

Tokens are never printed. Do not commit `.env`.

## Limitations

- **Rule-based classification is intentionally shallow** — substring matching
  against a curated dictionary. Misses paraphrase and sarcasm. Use the LLM
  second pass when precision matters.
- **X Recent Search returns a 7-day window** and is rate-limited. The notebook
  does not paginate; widen the queries instead of chasing volume.
- **No company enrichment.** Does not resolve handle → company / domain / person.
  Intentional for the MVP.
- **No persistence.** Each run produces a fresh CSV; there is no dedup across
  runs. Add a database (see Productization Notes in the notebook) before
  scheduling this on cron.
- **English-only** queries and term lists.

## Ethical guardrails

- Public content only. No DMs, no protected accounts.
- No aggressive scraping. Official API, respect rate limits.
- No automated outreach. The output is a CSV; a human acts on it.
- No claims of vulnerability or compromise unless the post explicitly says so.
- Minimum-necessary data: post text, public metrics, source URL.
- Human in the loop. Every suggestion in the CSV is a hint, not a message.

## Next steps

- Validate quality on 100 hand-labeled rows; compute precision per signal.
- Tune the keyword lists from the false-positive list.
- Persist signals in PostgreSQL with `post_id UNIQUE` for dedup across runs.
- Wrap in Streamlit, then FastAPI.
- Firmographic enrichment (industry, headcount), not personal data.
- Broaden sources: job posts, public news, vendor pages, technographics.

---

# Research Signal Listener

Threat-intelligence variant of the Cyber Prospect Radar. Instead of looking for
buying intent, it surfaces **public defensive events** on X — ransomware
victims, breach disclosures, leaked databases, active malware campaigns,
exploits, operator chatter, and dark-web mentions — for an internal CTI
analyst or the sales team of a ransomware-protection vendor (Halcyon).

It shares the same pipeline architecture as the Cyber Prospect Radar; only the
taxonomy, base scores, LLM prompt, and output filename differ.

Pipeline:

1. Query public X posts using a threat-intel taxonomy.
2. Normalize and clean the data (same cleaner as sales).
3. Classify into one of seven categories with auditable rules + anti-terms tuned
   against kinetic false positives (ISIS, TTP, BRG, BLA, Al-Shabaab, Balochistan).
4. Assign `opportunity_score` and priority. `RANSOMWARE_VICTIM` starts at base
   45 (the most urgent category for sales follow-up).
5. Add `why_now`, `sales_angle`, and `safe_outreach_suggestion`. For named
   victims, the outreach explicitly forbids contacting them directly — only
   peer-segment briefings to neighbors in the same vertical.
6. Detect tracker accounts (authors with ≥3 `RANSOMWARE_VICTIM` posts in a
   single run — ransomware.live, ransomwarewatch, automated feeds) and cap
   them to Low priority.
7. Optionally run a second pass with OpenAI re-prompted to the role of "threat
   intelligence analyst".
8. Same EDA + semantic clustering as the other notebook.
9. Export `x_research_signals.csv` for human review.

## Categories

| Category | Base score | What it captures |
|---|---|---|
| `RANSOMWARE_VICTIM` | 45 | Named victim on a leak site / operator claim |
| `BREACH_DISCLOSURE` | 40 | Officially disclosed breach |
| `DATABASE_LEAK` | 35 | Databases / credentials for sale or leaked |
| `MALWARE_CAMPAIGN` | 30 | Active campaigns (RedLine, Lumma, Qakbot, IcedID) |
| `EXPLOIT_OR_VULN` | 25 | 0-days, published PoCs, active CVEs |
| `RANSOMWARE_OPERATOR` | 20 | Operator chatter (LockBit, Qilin, ALPHV) |
| `DARK_WEB_CHATTER` | 15 | References to underground forums / onion sites |

## How to run it

Identical to the Cyber Prospect Radar — same `X_BEARER_TOKEN` and same `.env`.
Open:

```bash
jupyter notebook research_signal_listener.ipynb
```

*Kernel → Restart Kernel and Run All Cells*.

Typical volume: **~250 rows per run** (vs ~93 from the sales notebook), because
cyber-threat news is densely posted by automated tracker accounts.

## Output

`x_research_signals.csv` with the same 23 columns as the sales CSV. The
`is_tracker=True` flag marks automated feeds; the `safe_outreach_suggestion`
field for named victims explicitly says *"do NOT contact the named victim"*.

## Additional ethical guardrails (threat-intel)

The Cyber Prospect Radar guardrails apply in full, plus these domain-specific
ones:

- **Never contact named victims** directly. The sales angle is *peer-segment
  briefing*, not *opportunistic pitch*.
- **Do not engage with operator content.** `RANSOMWARE_OPERATOR` and
  `DARK_WEB_CHATTER` are *internal tracking only*.
- **Do not visit dark-web URLs** from corporate infrastructure.
- **Do not weaponize public PoCs** in outreach. Share detection and mitigation,
  never the exploit.

## Next steps specific to the research notebook

- Consider a new category `BREACH_LEGAL_AFTERMATH` (court rulings, GDPR fines)
  — the semantic clustering suggested it as a cluster with a populated NONE
  bucket.
- Add complementary sources: Mastodon `infosec.exchange`, RSS from
  BleepingComputer / The Record / KrebsOnSecurity, GitHub security advisories,
  ransomware.live for cross-validation of victims.
- Temporal filter `created_at >= last_30_days` to drop historical references
  that leak in via mentions like *"In 2021, a ransomware attack on..."*.