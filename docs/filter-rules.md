# Filter Rules — Architectural Rule

## The rule

**Every threshold, constant, or predicate that determines whether a token or wallet is included, excluded, counted, promoted, or gated anywhere in the pipeline must live in `src/wigs/filters.py`. Nowhere else.**

This is a hard architectural constraint, not a preference.

---

## What "filter logic" means

A piece of code is filter logic if it answers any of the following questions:

- Should this token be included in the pipeline or rejected?
- Should this wallet's buy count as a vote or be excluded?
- Does this social mention come from a credible source?
- Is this score high enough to trigger an alert?
- Does this outcome qualify this wallet for re-inclusion in tracking?
- What weight does this component get in the final score?

If the answer to any of those is determined by a hardcoded number, set membership, or threshold comparison — that value belongs in `filters.py`.

---

## What belongs in `filters.py`

| Category | Examples |
|---|---|
| Safety veto thresholds | Gini, HHI, top-10 holder %, price impact minimums |
| Soft penalty point values | Points deducted for POOL_TOO_NEW, VOLUME_TOO_BOTLIKE, etc. |
| Dempster-Shafer belief weights | Per-source risk contribution weights |
| Cluster type rules | Which types are excluded from voting; classification thresholds |
| Convergence gates | Wallets needed for full confidence, threshold adjustment formula |
| Time compression breakpoints | Seconds thresholds for the buy-spread multiplier |
| Social quality gates | Account age floor, platform normalization ceilings |
| Evidence fusion weights | Per-component weight in the final score formula |
| Risk level thresholds | Score cutoffs for LOW / MEDIUM / HIGH / CRITICAL labels |
| Alert trigger decisions | Which decision levels fire Telegram / Discord alerts |
| Wallet score blend weights | Convergence vs quality ratio in wallet_score |
| Outcome classification thresholds | Liquidity and return cutoffs for each outcome label |
| Outcome Beta posterior credits | Alpha/beta deltas per outcome label |
| Wallet quality component weights | Default weights dict for score_wallet() |
| Wallet quality sub-score gates | Early entry percentile, exit impact penalty trigger |
| Copurchase graph minimum | Min shared tokens to form a co-purchase edge |
| Wallet universe discovery gates | Min multiple, first window, whale threshold, KOL lookback |

---

## What does NOT belong in `filters.py`

| Category | Where it lives | Why |
|---|---|---|
| User-configurable thresholds | `config.py` (loaded from `.env`) | Users change these without touching code |
| Algorithm implementations | Individual algorithm files | The math is not the rule; the number is |
| DB queries | Repository files | Data retrieval is not filtering |
| API client rate limits / retry logic | Client files | Operational, not policy |

---

## How to add or change a filter

1. **Find the constant or function in `filters.py`.** If it doesn't exist yet, add it there.
2. **Give it a descriptive ALL_CAPS name** for constants, or a clear verb-noun name for predicate functions.
3. **Add a comment** explaining what the value means and what triggers it. Include units (USD, seconds, ratio).
4. **Import it** in the file that needs it — never define the value locally.
5. **Do not duplicate.** If a threshold is already in `config.py` (because it's user-configurable), import from `get_settings()`, not `filters.py`.

---

## Why this rule exists

Before this rule, thresholds were scattered:

- `0.20` appeared in `safety_veto.py`, `social_verifier.py`, and `workers.py` meaning three different things
- `{"HEAVY_HITTER", "TRADEABLE_RUNNER"}` was hardcoded in two separate worker functions
- The cluster exclusion set `("CABAL_SUSPECT", "BOT_FARM", "DEV_SUSPECT")` lived inside a scoring function, invisible to anyone tuning the system

When you needed to ask "what exactly disqualifies a wallet from voting?" you had to read five files. When you needed to change the bot farm timing threshold, you had to find it by grepping for a magic number.

With this rule: one file, one lookup, one change, zero drift.

---

## Enforcement

There is no automated linter for this yet. Until one exists, enforce it in code review:

- Any PR that introduces a numeric threshold, set comparison, or `> / < / ==` check against a hardcoded value in any file **other than** `filters.py` should be flagged and moved.
- The exception is values already in `config.py` — those are fine where they are.
