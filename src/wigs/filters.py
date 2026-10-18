"""WIGS filter rules — single source of truth for all inclusion/exclusion gates.

ARCHITECTURAL RULE
==================
Every threshold, constant, or predicate that determines whether a token or wallet
is included, excluded, counted, promoted, or gated in any part of the pipeline
MUST live in this file. Nowhere else.

This includes:
  - Hard veto thresholds and penalty point values (safety)
  - Cluster type classification thresholds and the excluded-type set
  - Convergence independence and time-compression rules
  - Social source quality gates (account age, follower floors)
  - Evidence fusion component weights
  - Score decision levels and alert trigger decisions
  - Outcome classification thresholds and Beta posterior credits
  - Wallet quality component weights and sub-score gates
  - Wallet lifecycle gates (copurchase, universe discovery)

Values that ARE in config.py (user-configurable via .env) stay there. This file
covers all hardcoded policy values that are not environment-overridable.

See docs/filter-rules.md for the full rationale and contribution rules.
"""

from __future__ import annotations

# ── Cluster type constants ────────────────────────────────────────────────────

# Cluster types that are completely excluded from convergence voting (weight = 0.0)
EXCLUDED_CLUSTER_TYPES: frozenset[str] = frozenset({"CABAL_SUSPECT", "BOT_FARM", "DEV_SUSPECT"})

# Cluster classification decision boundaries
BOT_FARM_SUSPICION_THRESHOLD: float = 0.80    # normalized suspicion > this AND timing > BOT_FARM_TIMING → BOT_FARM
BOT_FARM_TIMING_THRESHOLD: float = 0.90       # timing tightness required for BOT_FARM classification
DEV_SUSPECT_SHARED_FUNDING_THRESHOLD: float = 0.80   # shared_funding > this → DEV_SUSPECT
CABAL_SUSPECT_SUSPICION_THRESHOLD: float = 0.70      # normalized suspicion > this → CABAL_SUSPECT
SMART_MONEY_SUSPICION_THRESHOLD: float = 0.30        # normalized suspicion < this → SMART_MONEY

# ── Convergence gates ────────────────────────────────────────────────────────

# Number of confirmed independent wallets needed before confidence reaches 1.0
CONVERGENCE_CONFIDENCE_FULL_AT_N_WALLETS: int = 3

# Threshold adjustment: points subtracted per additional independent wallet above 1
CONVERGENCE_THRESHOLD_ADJUSTMENT_PER_WALLET: int = 5
CONVERGENCE_THRESHOLD_ADJUSTMENT_MAX: int = 20   # cap

# Time compression breakpoints (seconds)
TIME_COMPRESSION_TIGHT_SECONDS: float = 300.0    # spread ≤ this → maximum multiplier
TIME_COMPRESSION_NONE_SECONDS: float = 1800.0    # spread > this → no bonus (1.0x)
TIME_COMPRESSION_MAX_FACTOR: float = 2.0

# ── Safety veto — DS thresholds ──────────────────────────────────────────────

DS_HARD_VETO_THRESHOLD: float = 0.85    # DS risky belief above this → DS_COMBINED_RISK hard veto
DS_SOFT_PENALTY_THRESHOLD: float = 0.60 # DS risky belief above this → DS_PARTIAL_RISK soft penalty

# BPA belief weights used by Dempster-Shafer source functions
DS_CONCENTRATION_GINI_WEIGHT: float = 0.50    # gini > max_gini_coefficient → add this to risky
DS_CONCENTRATION_HHI_WEIGHT: float = 0.30     # hhi > max_hhi → add this to risky
DS_CONCENTRATION_TOP10_WEIGHT: float = 0.20   # top_10_pct > max_top_10_holder_pct → add this
DS_LIQUIDITY_RISKY_HIGH: float = 0.80         # liquidity < min → RISKY belief this high
DS_LIQUIDITY_RISKY_MARGINAL: float = 0.30     # liquidity < min*3 → RISKY belief this high
DS_AUTHORITY_MINT_WEIGHT: float = 0.60        # active mint authority → risk contribution
DS_AUTHORITY_FREEZE_WEIGHT: float = 0.40      # active freeze authority → risk contribution

# ── Safety veto — soft penalty point values ───────────────────────────────────

PENALTY_POOL_TOO_NEW: int = 15          # pool younger than POOL_AGE_SOFT_PENALTY_MINUTES
PENALTY_VOLUME_TOO_BOTLIKE: int = 20    # volume authenticity ratio below VOLUME_AUTHENTICITY_MIN_RATIO
PENALTY_SOCIAL_TOO_THIN: int = 10       # no social data present
PENALTY_SINGLE_WALLET_SIGNAL: int = 10  # only one independent buyer
PENALTY_CLUSTER_NOT_INDEPENDENT: int = 20  # no independent buyer at all
PENALTY_KOL_ALREADY_CALLED: int = 15    # KOL already called this token before signal
PENALTY_DS_PARTIAL_RISK: int = 20       # DS risky belief above DS_SOFT_PENALTY_THRESHOLD

# ── Safety veto — market condition thresholds ────────────────────────────────

POOL_AGE_SOFT_PENALTY_MINUTES: float = 10.0  # pools younger than this trigger POOL_TOO_NEW
VOLUME_AUTHENTICITY_MIN_RATIO: float = 0.20  # ratio below this triggers VOLUME_TOO_BOTLIKE

# ── Social source quality gates ───────────────────────────────────────────────

SOCIAL_QUALITY_ACCOUNT_MIN_AGE_DAYS: int = 30  # accounts must be older than this to be "quality"
SOCIAL_QUALITY_ACCOUNTS_FOR_MAX_SCORE: int = 20  # 20 quality accounts → unique_sources score 1.0
SOCIAL_GDELT_ARTICLES_FOR_MAX_RELEVANCE: int = 5  # 5 articles → gdelt_relevance 1.0
SOCIAL_PLATFORMS_FOR_MAX_SCORE: int = 3           # 3 platforms → cross_platform score 1.0
SOCIAL_REDDIT_MENTIONS_FOR_MAX_SCORE: int = 20    # 20 mentions → reddit mention score 1.0
SOCIAL_YOUTUBE_MENTIONS_FOR_MAX_SCORE: int = 5    # 5 videos → youtube score 1.0
SOCIAL_GDELT_NARRATIVE_MIN_RELEVANCE: float = 0.30  # above this → REAL_WORLD_EVENT narrative

# ── Evidence fusion component weights ─────────────────────────────────────────

FUSION_WEIGHT_WALLET: float = 0.35
FUSION_WEIGHT_MARKET: float = 0.20
FUSION_WEIGHT_RISK: float = 0.20
FUSION_WEIGHT_SOCIAL: float = 0.15
FUSION_WEIGHT_HISTORY: float = 0.07
FUSION_WEIGHT_EXECUTION: float = 0.03

# ── Risk level classification ─────────────────────────────────────────────────

RISK_LEVEL_HIGH_BELOW: int = 40     # risk_score < this → HIGH risk label
RISK_LEVEL_MEDIUM_BELOW: int = 70   # risk_score < this → MEDIUM risk label

# ── Alert trigger decisions ───────────────────────────────────────────────────

# Only these decision levels publish an alert to Telegram / Discord
ALERT_TRIGGER_DECISIONS: frozenset[str] = frozenset({"STRONG_WATCH", "STRONG_CANDIDATE"})

# ── Wallet score composition ──────────────────────────────────────────────────

WALLET_SCORE_CONVERGENCE_WEIGHT: float = 0.70   # convergence score share in wallet_score
WALLET_SCORE_QUALITY_WEIGHT: float = 0.30       # wallet quality share in wallet_score
WALLET_SCORE_DEFAULT_QUALITY: int = 50          # fallback when no quality score exists

# ── Outcome measurement and labeling ─────────────────────────────────────────

OUTCOME_MEASUREMENT_WINDOW_DAYS: int = 7   # wait this long after alert before labeling

# Outcome labels that qualify wallets for the refresh/discovery cycle
OUTCOME_LABELS_FOR_WALLET_REFRESH: frozenset[str] = frozenset({"HEAVY_HITTER", "TRADEABLE_RUNNER"})

# Outcome labels considered "wins" for backtest hit-rate reporting
OUTCOME_LABELS_POSITIVE: frozenset[str] = frozenset({"HEAVY_HITTER", "TRADEABLE_RUNNER", "SURVIVOR"})

# ── Outcome classification thresholds ────────────────────────────────────────

OUTCOME_HEAVY_HITTER_LIQUIDITY: float = 500_000.0   # liquidity_7d ≥ this → HEAVY_HITTER
OUTCOME_SURVIVOR_LIQUIDITY: float = 50_000.0         # liquidity_7d ≥ this + return > 0 → SURVIVOR
OUTCOME_DEAD_LIQUIDITY: float = 1_000.0              # liquidity_7d < this → DEAD_ON_ARRIVAL or RUG
OUTCOME_TRADEABLE_RUNNER_MIN_RETURN: float = 1.2     # tradable_return_1h > this → TRADEABLE_RUNNER (20% gain)
OUTCOME_SURVIVOR_MIN_RETURN: float = 1.0             # tradable_return_1h > this alongside liquidity → SURVIVOR
OUTCOME_ONE_CYCLE_MIN_RETURN: float = 1.5            # max_return_24h > this → ONE_CYCLE_PUMP candidate (50% peak)
OUTCOME_ONE_CYCLE_LIQUIDITY_DRAIN: float = 0.30      # liquidity_7d < initial * this → pump-and-dump confirmed
OUTCOME_RUG_LIQUIDITY_DRAIN: float = 0.10            # liquidity_7d < initial * this → RUG (90% drained)

# ── Thompson Sampling trust gate ──────────────────────────────────────────────

THOMPSON_TRUST_THRESHOLD: float = 0.60   # Beta sample above this → increase wallet trust

# ── Outcome Beta posterior update credits ────────────────────────────────────
# Maps outcome label → (alpha_delta, beta_delta) for the Beta(α, β) posterior.
# High alpha_delta = signal that this wallet is trustworthy.
# High beta_delta = signal that this wallet is untrustworthy.

OUTCOME_BETA_CREDITS: dict[str, tuple[float, float]] = {
    "HEAVY_HITTER":     (1.0,  0.0),
    "TRADEABLE_RUNNER": (1.0,  0.0),
    "SURVIVOR":         (0.5,  0.0),
    "ONE_CYCLE_PUMP":   (0.25, 0.25),   # pumped but not durable
    "DEAD_ON_ARRIVAL":  (0.0,  1.0),
    "RUG":              (0.0,  1.0),
}

# ── Wallet quality component weights ──────────────────────────────────────────

WALLET_QUALITY_DEFAULT_WEIGHTS: dict[str, float] = {
    "pnl": 0.22,
    "early_entry": 0.18,
    "lead_lag": 0.18,
    "exit_quality": 0.14,
    "rug_avoidance": 0.12,
    "repeatability": 0.08,
    "independence": 0.05,
    "freshness": 0.03,
}

# ── Wallet quality sub-score gates ────────────────────────────────────────────

EARLY_ENTRY_PERCENTILE_THRESHOLD: float = 0.20       # buyer in top 20% of entry order = "early hit"
EXIT_QUALITY_IMPACT_PENALTY_TRIGGER: float = 0.15    # sell price impact > this degrades exit quality
EXIT_QUALITY_IMPACT_PENALTY_FACTOR: float = 0.50     # multiply exit quality by this when penalty triggers
PNL_SCORE_NORMALIZATION_USD: float = 10_000.0        # log1p(this) anchors the 100-point PnL scale

# ── Copurchase graph ──────────────────────────────────────────────────────────

COPURCHASE_MIN_SHARED_TOKENS: int = 2   # wallet pair must co-buy at least this many tokens to form an edge

# ── Wallet universe discovery gates ──────────────────────────────────────────

WALLET_UNIVERSE_HISTORICAL_MIN_MULTIPLE: float = 3.0   # token must reach ≥ 3x for its wallets to qualify
WALLET_UNIVERSE_FIRST_WINDOW_SECONDS: float = 1800.0   # wallets in first 30 min of token life qualify
WALLET_UNIVERSE_WHALE_THRESHOLD_USD: float = 50_000.0  # buy ≥ this USD = "whale" for pre-whale discovery
WALLET_UNIVERSE_KOL_LOOKBACK_HOURS: int = 6            # look this many hours before a KOL buy

# ─────────────────────────────────────────────────────────────────────────────
# Filter predicate functions
# ─────────────────────────────────────────────────────────────────────────────


def independence_weight(
    cluster_type: str | None,
    cluster_id: str | None,
    cluster_size: int,
) -> float:
    """Vote weight for a wallet in convergence scoring.

    Excluded cluster types → 0.0 (no vote).
    Smart-money cluster members → share one vote across the cluster.
    Fully independent wallets → 1.0 full vote.
    """
    if cluster_type in EXCLUDED_CLUSTER_TYPES:
        return 0.0
    if cluster_id is not None and cluster_type == "SMART_MONEY":
        return 1.0 / max(1, cluster_size)
    return 1.0


def time_compression_factor(spread_seconds: float) -> float:
    """Score multiplier based on how tightly clustered wallet buys are in time.

    Tighter convergence = stronger signal = higher multiplier.
    """
    if spread_seconds <= TIME_COMPRESSION_TIGHT_SECONDS:
        return TIME_COMPRESSION_MAX_FACTOR
    if spread_seconds > TIME_COMPRESSION_NONE_SECONDS:
        return 1.0
    return 1.0 + (1.0 - spread_seconds / TIME_COMPRESSION_NONE_SECONDS)


def convergence_confidence(independent_count: int) -> float:
    """Confidence multiplier. Scales 0→1 as independent wallets accumulate.

    Stays below 1.0 until CONVERGENCE_CONFIDENCE_FULL_AT_N_WALLETS are confirmed.
    """
    return min(1.0, independent_count / CONVERGENCE_CONFIDENCE_FULL_AT_N_WALLETS)


def convergence_threshold_adjustment(independent_buyer_count: int) -> int:
    """Points to subtract from decision thresholds.

    More independent wallets = lower bar to reach each decision level.
    """
    return min(
        CONVERGENCE_THRESHOLD_ADJUSTMENT_MAX,
        max(0, (independent_buyer_count - 1) * CONVERGENCE_THRESHOLD_ADJUSTMENT_PER_WALLET),
    )


def classify_cluster_type(
    suspicion_score: float,
    timing_tightness: float,
    shared_funding: float,
) -> str:
    """Classify a wallet cluster into a type based on suspicion metrics.

    suspicion_score is the raw 0–100 output of score_cluster_suspicion().
    """
    normalized = suspicion_score / 100.0
    if normalized > BOT_FARM_SUSPICION_THRESHOLD and timing_tightness > BOT_FARM_TIMING_THRESHOLD:
        return "BOT_FARM"
    if shared_funding > DEV_SUSPECT_SHARED_FUNDING_THRESHOLD:
        return "DEV_SUSPECT"
    if normalized > CABAL_SUSPECT_SUSPICION_THRESHOLD:
        return "CABAL_SUSPECT"
    if normalized < SMART_MONEY_SUSPICION_THRESHOLD:
        return "SMART_MONEY"
    return "UNKNOWN"


def is_quality_social_account(account_age_days: int) -> bool:
    """True if an account is established enough to count as a quality social source."""
    return account_age_days > SOCIAL_QUALITY_ACCOUNT_MIN_AGE_DAYS


def classify_outcome(
    tradable_return_1h: float | None,
    max_return_24h: float | None,
    liquidity_7d: float | None,
    initial_liquidity: float,
) -> str:
    """Classify a token outcome from forward return measurements.

    tradable_return_1h: estimated sell ratio vs entry (1.2 = +20%).
    max_return_24h: peak price return in 24h (unrealized).
    liquidity_7d: liquidity USD 7 days after alert.
    initial_liquidity: liquidity at alert time (for drain ratio).
    """
    if liquidity_7d is None:
        return "RUG"
    if liquidity_7d >= OUTCOME_HEAVY_HITTER_LIQUIDITY:
        return "HEAVY_HITTER"
    if liquidity_7d >= OUTCOME_SURVIVOR_LIQUIDITY and (tradable_return_1h or 0) > OUTCOME_SURVIVOR_MIN_RETURN:
        return "SURVIVOR"
    if (tradable_return_1h or 0) > OUTCOME_TRADEABLE_RUNNER_MIN_RETURN:
        return "TRADEABLE_RUNNER"
    if (max_return_24h or 0) > OUTCOME_ONE_CYCLE_MIN_RETURN and liquidity_7d < initial_liquidity * OUTCOME_ONE_CYCLE_LIQUIDITY_DRAIN:
        return "ONE_CYCLE_PUMP"
    if liquidity_7d < OUTCOME_DEAD_LIQUIDITY:
        if liquidity_7d < initial_liquidity * OUTCOME_RUG_LIQUIDITY_DRAIN:
            return "RUG"
        return "DEAD_ON_ARRIVAL"
    return "DEAD_ON_ARRIVAL"


def should_alert(decision: str) -> bool:
    """True if this decision level should publish an alert to Telegram / Discord."""
    return decision in ALERT_TRIGGER_DECISIONS


def is_positive_outcome(outcome_label: str) -> bool:
    """True if this outcome counts as a win for backtest hit-rate reporting."""
    return outcome_label in OUTCOME_LABELS_POSITIVE


def qualifies_for_wallet_refresh(outcome_label: str) -> bool:
    """True if this outcome qualifies the token's wallets for the refresh/discovery cycle."""
    return outcome_label in OUTCOME_LABELS_FOR_WALLET_REFRESH
