# 05 — End-to-End High-Level Python Pseudocode

This is intentionally class/function-level pseudocode, not implementation code.

## Domain enums

```python
class WalletType(Enum):
    SCOUT
    WHALE
    SMART_MONEY
    KOL_PRECALL
    DEV_ADJACENT
    UNKNOWN

class WalletEventType(Enum):
    BUY
    SELL
    TRANSFER_IN
    TRANSFER_OUT
    LP_ADD
    LP_REMOVE

class CandidateStatus(Enum):
    PENDING
    ENRICHING
    REJECTED
    WATCH
    STRONG_WATCH
    STRONG_CANDIDATE

class Decision(Enum):
    AVOID
    WATCH
    STRONG_WATCH
    STRONG_CANDIDATE

class OutcomeLabel(Enum):
    RUG
    DEAD_ON_ARRIVAL
    ONE_CYCLE_PUMP
    TRADEABLE_RUNNER
    SURVIVOR
    HEAVY_HITTER
```

## API client layer

```python
class HeliusClient:
    def create_wallet_webhook(wallet_addresses: list[str]) -> WebhookId: ...
    def parse_transaction(signature: str) -> ParsedTransaction: ...
    def get_transactions_for_address(address: str, before: str | None = None) -> list[ParsedTransaction]: ...

class SolanaRpcClient:
    def get_token_supply(token_mint: str) -> TokenSupply: ...
    def get_token_largest_accounts(token_mint: str) -> list[TokenAccountBalance]: ...
    def get_transaction(signature: str) -> RawTransaction: ...
    def get_signatures_for_address(address: str, limit: int) -> list[str]: ...

class DexScreenerClient:
    def get_token_pairs(token_mint: str) -> list[DexPair]: ...
    def get_token_profile(token_mint: str) -> TokenProfile: ...
    def get_paid_orders(token_mint: str) -> list[PaidOrder]: ...

class GeckoTerminalClient:
    def get_token_pools(network: str, token_mint: str) -> list[Pool]: ...
    def get_ohlcv(pool_address: str, timeframe: str) -> list[Candle]: ...

class BirdeyeClient:
    def get_price(token_mint: str) -> Price: ...
    def get_token_trades(token_mint: str) -> list[Trade]: ...
    def get_token_security(token_mint: str) -> TokenSecurity: ...
    def get_wallet_portfolio(wallet_address: str) -> WalletPortfolio: ...

class JupiterClient:
    def quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Quote: ...
    def estimate_sellability(token_mint: str, test_amounts: list[int]) -> SellabilityReport: ...

class RedditClient:
    def search_mentions(terms: list[str], subreddits: list[str], window: TimeWindow) -> SocialMentionSet: ...

class TelegramClient:
    def scan_authorized_channels(terms: list[str], window: TimeWindow) -> SocialMentionSet: ...

class DiscordClient:
    def scan_authorized_servers(terms: list[str], window: TimeWindow) -> SocialMentionSet: ...

class GdeltClient:
    def search_news_events(terms: list[str], window: TimeWindow) -> NewsMentionSet: ...

class YouTubeClient:
    def search_video_mentions(terms: list[str], window: TimeWindow) -> VideoMentionSet: ...
```

## Repository layer

```python
class WalletRepository:
    def upsert_tracked_wallet(wallet: TrackedWallet) -> None: ...
    def list_active_wallets() -> list[TrackedWallet]: ...
    def save_wallet_event(event: WalletEvent) -> None: ...
    def get_recent_wallet_events(wallet_address: str, window: TimeWindow) -> list[WalletEvent]: ...
    def save_wallet_score(score: WalletScoreSnapshot) -> None: ...

class TokenRepository:
    def upsert_candidate_token(token: CandidateToken) -> None: ...
    def save_market_snapshot(snapshot: TokenMarketSnapshot) -> None: ...
    def save_risk_snapshot(snapshot: TokenRiskSnapshot) -> None: ...
    def save_social_snapshot(snapshot: SocialSnapshot) -> None: ...
    def save_token_score(score: TokenScoreSnapshot) -> None: ...
    def get_latest_token_context(token_mint: str) -> TokenContext: ...

class GraphRepository:
    def add_wallet_token_edge(wallet: str, token_mint: str, event_type: WalletEventType, event_time: datetime) -> None: ...
    def add_wallet_wallet_edge(source_wallet: str, target_wallet: str, edge_type: str, confidence: float) -> None: ...
    def add_token_social_edge(token_mint: str, source: str, mention_time: datetime) -> None: ...
    def get_wallet_cluster(wallet_address: str) -> WalletCluster | None: ...
    def save_cluster(cluster: WalletCluster) -> None: ...

class AlertRepository:
    def save_alert(alert: Alert) -> None: ...
    def list_unlabeled_alerts() -> list[Alert]: ...
    def save_outcome(outcome: TokenOutcome) -> None: ...
```

## Wallet discovery and ranking

```python
class WalletUniverseBuilder:
    def discover_from_historical_winners(tokens: list[str]) -> list[str]:
        # Find early buyers of tokens that later became tradeable runners.
        ...

    def discover_pre_whale_wallets(known_whales: list[str]) -> list[str]:
        # Find wallets that repeatedly buy before known whales.
        ...

    def discover_kol_precall_wallets(kol_channels: list[str]) -> list[str]:
        # Find wallets that buy before social/KOL mentions.
        ...

    def build_seed_wallet_set() -> list[TrackedWallet]:
        historical = discover_from_historical_winners(...)
        pre_whale = discover_pre_whale_wallets(...)
        precall = discover_kol_precall_wallets(...)
        return deduplicate_and_rank(historical + pre_whale + precall)

class WalletQualityModel:
    def calculate_realized_pnl_score(wallet_address: str) -> int: ...
    def calculate_early_entry_score(wallet_address: str) -> int: ...
    def calculate_lead_lag_score(wallet_address: str) -> int: ...
    def calculate_exit_quality_score(wallet_address: str) -> int: ...
    def calculate_rug_avoidance_score(wallet_address: str) -> int: ...
    def calculate_repeatability_score(wallet_address: str) -> int: ...
    def calculate_independence_score(wallet_address: str) -> int: ...
    def calculate_freshness_score(wallet_address: str) -> int: ...

    def score_wallet(wallet_address: str) -> WalletScoreSnapshot:
        return weighted_wallet_quality_score(...)
```

## Graph and cluster analysis

```python
class WalletClusterer:
    def detect_funding_links(wallets: list[str]) -> list[ClusterEdge]: ...
    def detect_co_entry_patterns(wallets: list[str]) -> list[ClusterEdge]: ...
    def detect_co_exit_patterns(wallets: list[str]) -> list[ClusterEdge]: ...
    def detect_timing_similarity(wallets: list[str]) -> list[ClusterEdge]: ...
    def build_clusters(edges: list[ClusterEdge]) -> list[WalletCluster]: ...

class LeadLagModel:
    def measure_wallet_precedes_wallet(wallet_a: str, wallet_b: str, window: timedelta) -> float: ...
    def measure_wallet_precedes_social(wallet: str, token_mint: str, window: timedelta) -> float: ...
    def measure_wallet_precedes_liquidity_expansion(wallet: str, token_mint: str, window: timedelta) -> float: ...
    def score_pre_whale_edge(wallet_a: str, whale_b: str) -> LeadLagScore: ...
```

## Live event pipeline

```python
class WalletEventIngestor:
    def handle_helius_webhook(payload: dict) -> list[WalletEvent]:
        parsed = parse_payload(payload)
        events = extract_wallet_events(parsed)
        return events

    def is_candidate_buy(event: WalletEvent) -> bool:
        return event.event_type == BUY and event.token_mint is not None

class CandidateMintExtractor:
    def extract_candidate(event: WalletEvent) -> CandidateToken:
        return CandidateToken(
            token_mint=event.token_mint,
            first_seen_at=now(),
            status=PENDING,
        )

class EvidenceGraphBuilder:
    def update_graph_from_event(event: WalletEvent) -> None:
        add_wallet_token_edge(...)
        update_wallet_activity_state(...)
        update_candidate_relationships(...)
```

## Enrichment pipeline

```python
class MarketVerifier:
    def fetch_market_context(token_mint: str) -> MarketContext:
        dex_pairs = DexScreenerClient.get_token_pairs(token_mint)
        gecko_pools = GeckoTerminalClient.get_token_pools("solana", token_mint)
        birdeye_price = BirdeyeClient.get_price(token_mint)
        return reconcile_market_sources(dex_pairs, gecko_pools, birdeye_price)

    def score_market_context(context: MarketContext) -> int:
        return calculate_liquidity_volume_route_score(context)

class ExecutionVerifier:
    def check_sellability(token_mint: str) -> SellabilityReport:
        quote_025 = JupiterClient.quote(token_mint, SOL_MINT, amount_025_sol_equivalent, slippage_bps=500)
        quote_1 = JupiterClient.quote(token_mint, SOL_MINT, amount_1_sol_equivalent, slippage_bps=500)
        quote_5 = JupiterClient.quote(token_mint, SOL_MINT, amount_5_sol_equivalent, slippage_bps=500)
        return build_sellability_report([quote_025, quote_1, quote_5])

class SafetyVetoEngine:
    def check_token_authorities(token_mint: str) -> AuthorityReport: ...
    def check_holder_concentration(token_mint: str) -> HolderConcentrationReport: ...
    def check_dev_wallet_behavior(token_mint: str) -> DevBehaviorReport: ...
    def check_liquidity_risk(token_mint: str) -> LiquidityRiskReport: ...
    def check_copycat_identity(token_mint: str) -> CopycatReport: ...

    def evaluate(token_mint: str, context: TokenContext) -> RiskReport:
        vetoes = []
        penalties = []
        if no_sell_route(context): vetoes.append("NO_SELL_ROUTE")
        if active_mint_authority(context): vetoes.append("ACTIVE_MINT_AUTHORITY")
        if active_freeze_authority(context): vetoes.append("ACTIVE_FREEZE_AUTHORITY")
        if top_holders_too_concentrated(context): vetoes.append("TOP_HOLDER_TOO_CONCENTRATED")
        if liquidity_too_low(context): vetoes.append("LIQUIDITY_TOO_LOW")
        return RiskReport(vetoes=vetoes, penalties=penalties)
```

## Social and narrative confirmation

```python
class SocialTrendVerifier:
    def build_search_terms(token: CandidateToken) -> list[str]:
        return [
            token.token_mint,
            token.symbol,
            token.name,
            normalized_variants(token.symbol),
            normalized_variants(token.name),
        ]

    def fetch_social_mentions(token: CandidateToken) -> SocialEvidence:
        terms = build_search_terms(token)
        reddit = RedditClient.search_mentions(terms, target_subreddits, last_24h)
        telegram = TelegramClient.scan_authorized_channels(terms, last_6h)
        discord = DiscordClient.scan_authorized_servers(terms, last_6h)
        gdelt = GdeltClient.search_news_events(terms, last_7d)
        youtube = YouTubeClient.search_video_mentions(terms, last_7d)
        return merge_social_evidence(reddit, telegram, discord, gdelt, youtube)

    def score_social_evidence(evidence: SocialEvidence) -> int:
        return weighted_social_velocity_score(evidence)

class NarrativeMatcher:
    def classify_narrative(token: CandidateToken, evidence: SocialEvidence) -> NarrativeType:
        # animal, political, AI, celebrity, news event, culture meme, derivative, unknown
        ...

    def detect_fake_social_spam(evidence: SocialEvidence) -> bool: ...
```

## Evidence scoring

```python
class EvidenceFusionScorer:
    def calculate_wallet_score(token_mint: str) -> int:
        # Based on triggering wallet quality, number of independent wallets, lead-lag strength, and cluster risk.
        ...

    def calculate_market_score(market_context: MarketContext) -> int:
        ...

    def calculate_risk_score(risk_report: RiskReport) -> int:
        if risk_report.has_hard_veto():
            return 0
        return 100 - penalty_points(risk_report.penalties)

    def calculate_social_score(social_evidence: SocialEvidence) -> int:
        ...

    def calculate_history_score(token_mint: str) -> int:
        # Creator history, early holder quality, pool age, previous rugs, launch behavior.
        ...

    def calculate_execution_score(sellability: SellabilityReport) -> int:
        ...

    def final_score(context: TokenContext) -> TokenScoreSnapshot:
        risk = calculate_risk_score(context.risk_report)

        if context.risk_report.has_hard_veto():
            return TokenScoreSnapshot(decision=AVOID, total_score=0, score_reasons=context.risk_report.vetoes)

        total = (
            0.30 * wallet_score
          + 0.20 * market_score
          + 0.20 * risk
          + 0.15 * social_score
          + 0.10 * history_score
          + 0.05 * execution_score
        )

        decision = classify_decision(total)
        return TokenScoreSnapshot(total_score=total, decision=decision, ...)
```

## Alerting and audit

```python
class AlertPublisher:
    def should_alert(score: TokenScoreSnapshot) -> bool:
        return score.decision in [STRONG_WATCH, STRONG_CANDIDATE]

    def format_alert(token: CandidateToken, score: TokenScoreSnapshot, context: TokenContext) -> str:
        return format_risk_and_evidence_summary(...)

    def publish(score: TokenScoreSnapshot) -> Alert:
        if not should_alert(score):
            return save_skipped_alert(...)
        message = format_alert(...)
        send_to_telegram_or_discord(message)
        return save_alert(...)

class AuditLedger:
    def record_decision(token_mint: str, full_context: TokenContext, score: TokenScoreSnapshot) -> None:
        # Store enough data to later explain exactly why the system alerted.
        ...
```

## Outcome and feedback loop

```python
class OutcomeLabeler:
    def refresh_forward_market_data(alert: Alert) -> ForwardMarketData: ...
    def estimate_tradable_returns(alert: Alert) -> TradableReturnReport: ...
    def classify_outcome(report: TradableReturnReport) -> OutcomeLabel: ...
    def save_outcome(alert: Alert, outcome: TokenOutcome) -> None: ...

class WalletReRanker:
    def update_wallet_scores_from_outcomes() -> None:
        alerts = AlertRepository.list_recent_labeled_alerts()
        for alert in alerts:
            wallets = get_triggering_wallets(alert.token_mint)
            outcome = get_outcome(alert)
            adjust_wallet_scores(wallets, outcome)

class BacktestReplayEngine:
    def replay_historical_window(start: datetime, end: datetime) -> BacktestReport:
        # Reconstruct events, simulate detection delay, run scoring, estimate realistic exits.
        ...

    def compare_strategy_versions(version_a: str, version_b: str) -> StrategyComparison:
        ...
```

## Main orchestration

```python
class WigsPipeline:
    def handle_wallet_event(event: WalletEvent) -> TokenScoreSnapshot | None:
        save_wallet_event(event)

        if not CandidateMintExtractor.is_candidate_buy(event):
            return None

        candidate = CandidateMintExtractor.extract_candidate(event)
        upsert_candidate_token(candidate)

        EvidenceGraphBuilder.update_graph_from_event(event)

        market = MarketVerifier.fetch_market_context(candidate.token_mint)
        sellability = ExecutionVerifier.check_sellability(candidate.token_mint)
        risk = SafetyVetoEngine.evaluate(candidate.token_mint, market, sellability)
        social = SocialTrendVerifier.fetch_social_mentions(candidate)
        history = HistoryAnalyzer.analyze(candidate.token_mint)

        context = TokenContext(
            candidate=candidate,
            market=market,
            sellability=sellability,
            risk=risk,
            social=social,
            history=history,
        )

        score = EvidenceFusionScorer.final_score(context)
        save_token_score(score)

        AlertPublisher.publish(score)
        AuditLedger.record_decision(candidate.token_mint, context, score)

        return score
```

## Scheduled jobs

```python
class ScheduledJobs:
    def refresh_tracked_wallet_set_every_24h(): ...
    def update_wallet_scores_every_6h(): ...
    def refresh_open_candidate_scores_every_5m(): ...
    def label_alert_outcomes_every_15m(): ...
    def prune_low_quality_wallets_every_7d(): ...
    def rebuild_wallet_clusters_every_24h(): ...
    def run_backtest_weekly(): ...
```
