# Implementation Pseudocode

Class/function-level pseudocode. Intentionally not runnable — this is the implementation spec.

---

## Domain enums

```python
class WalletType(Enum):
    SCOUT
    WHALE
    SMART_MONEY
    KOL_PRECALL
    DEV_ADJACENT
    UNKNOWN

class WalletLifecycle(Enum):
    DISCOVERED
    ACTIVE
    DEGRADED
    RETIRED

class ClusterType(Enum):
    SMART_MONEY
    CABAL_SUSPECT
    DEV_SUSPECT
    BOT_FARM
    KOL_SUSPECT
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

---

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
    def estimate_sellability(token_mint: str, test_amounts_lamports: list[int]) -> SellabilityReport: ...

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

---

## Repository layer

```python
class WalletRepository:
    def upsert_tracked_wallet(wallet: TrackedWallet) -> None: ...
    def list_active_wallets() -> list[TrackedWallet]: ...
    def save_wallet_event(event: WalletEvent) -> None: ...
    def get_wallet_events_for_token(token_mint: str, window: TimeWindow) -> list[WalletEvent]: ...
    def get_recent_wallet_events(wallet_address: str, window: TimeWindow) -> list[WalletEvent]: ...
    def save_wallet_score(score: WalletScoreSnapshot) -> None: ...
    def get_wallet_score(wallet_address: str) -> WalletScoreSnapshot | None: ...
    def save_wallet_beta_posterior(wallet_address: str, alpha: float, beta: float) -> None: ...
    def get_wallet_beta_posterior(wallet_address: str) -> tuple[float, float]: ...  # (alpha, beta)

class TokenRepository:
    def upsert_candidate_token(token: CandidateToken) -> None: ...
    def save_market_snapshot(snapshot: TokenMarketSnapshot) -> None: ...
    def save_risk_snapshot(snapshot: TokenRiskSnapshot) -> None: ...
    def save_social_snapshot(snapshot: SocialSnapshot) -> None: ...
    def save_token_score(score: TokenScoreSnapshot) -> None: ...
    def get_latest_token_context(token_mint: str) -> TokenContext: ...

class GraphRepository:
    def add_wallet_token_edge(wallet: str, token_mint: str, event_type: WalletEventType, event_time: datetime) -> None: ...
    def add_wallet_wallet_edge(source: str, target: str, edge_type: str, confidence: float) -> None: ...
    def add_token_social_edge(token_mint: str, source: str, mention_time: datetime) -> None: ...
    def get_wallet_cluster(wallet_address: str) -> WalletCluster | None: ...
    def get_cluster_members(cluster_id: UUID) -> list[str]: ...
    def save_cluster(cluster: WalletCluster) -> None: ...
    def get_wallets_that_bought_token(token_mint: str) -> list[WalletBuyRecord]: ...

class AlertRepository:
    def save_alert(alert: Alert) -> None: ...
    def list_unlabeled_alerts() -> list[Alert]: ...
    def list_recent_labeled_alerts(days: int = 7) -> list[Alert]: ...
    def save_outcome(outcome: TokenOutcome) -> None: ...
```

---

## Wallet discovery and ranking

```python
class WalletUniverseBuilder:
    def discover_from_historical_winners(tokens: list[str]) -> list[str]:
        # Find wallets in the first 50 holders of TRADEABLE_RUNNER / HEAVY_HITTER tokens.
        ...

    def discover_pre_whale_wallets(known_whales: list[str]) -> list[str]:
        # Find wallets that repeatedly buy the same token 5–60 min before known whales.
        ...

    def discover_kol_precall_wallets(kol_channels: list[str]) -> list[str]:
        # Find wallets that buy 5–120 min before a public KOL posts about the token.
        ...

    def build_seed_wallet_set() -> list[TrackedWallet]:
        historical = discover_from_historical_winners(...)
        pre_whale = discover_pre_whale_wallets(...)
        precall = discover_kol_precall_wallets(...)
        return deduplicate_and_rank(historical + pre_whale + precall)


class WalletQualityModel:
    DECAY_LAMBDA = 0.1  # freshness score decay rate

    def calculate_realized_pnl_score(wallet_address: str) -> int:
        trades = get_closed_trades(wallet_address)
        weighted_return = Σ(tradable_return[t] * recency_weight(t) for t in trades)
        return normalize_0_100(weighted_return)

    def calculate_early_entry_score(wallet_address: str) -> int:
        entry_percentiles = [
            rank_in_first_N_buyers(token, wallet_address) / N
            for token in get_wallet_traded_tokens(wallet_address)
        ]
        base = normalize_0_100(1 - mean(entry_percentiles))
        return base * liquidity_event_lead_bonus * social_event_lead_bonus

    def calculate_lead_lag_score(wallet_address: str) -> int:
        # See LeadLagModel below for full formula.
        ...

    def calculate_exit_quality_score(wallet_address: str) -> int:
        avoided = Σ(drawdown_avoided_pct[t] * position_size_weight[t] for t in closed_trades)
        return normalize_0_100(avoided)

    def calculate_rug_avoidance_score(wallet_address: str) -> int:
        rug_rate = rug_trades / total_trades
        return normalize_0_100((1 - rug_rate) * (1 - avg_rug_exposure))

    def calculate_repeatability_score(wallet_address: str) -> int:
        returns = [tradable_return(t) for t in closed_trades]
        H = shannon_entropy(bucket(returns))  # Shannon entropy over return buckets
        return normalize_0_100(H)

    def calculate_independence_score(wallet_address: str) -> int:
        cluster = GraphRepository.get_wallet_cluster(wallet_address)
        if cluster is None:
            return 100
        sim = avg_cosine_similarity(wallet_buy_vector, cluster_member_buy_vectors)
        return normalize_0_100(1 - sim)

    def calculate_freshness_score(wallet_address: str) -> int:
        weekly_pnl = [get_weekly_pnl(wallet_address, w) for w in range(12)]
        weighted = Σ(weekly_pnl[w] * exp(-DECAY_LAMBDA * w) for w in range(12))
        return normalize_0_100(weighted)

    def score_wallet(wallet_address: str) -> WalletScoreSnapshot:
        scores = {
            realized_pnl_score: calculate_realized_pnl_score(wallet_address),
            early_entry_score: calculate_early_entry_score(wallet_address),
            lead_lag_score: calculate_lead_lag_score(wallet_address),
            exit_quality_score: calculate_exit_quality_score(wallet_address),
            rug_avoidance_score: calculate_rug_avoidance_score(wallet_address),
            repeatability_score: calculate_repeatability_score(wallet_address),
            independence_score: calculate_independence_score(wallet_address),
            freshness_score: calculate_freshness_score(wallet_address),
        }
        wallet_quality = weighted_sum(scores, WALLET_QUALITY_WEIGHTS)
        return WalletScoreSnapshot(wallet_address=wallet_address, **scores, wallet_quality=wallet_quality)
```

---

## Lead-lag model

```python
class LeadLagModel:
    def compute_cross_correlation(wallet_a: str, wallet_b: str, window: timedelta) -> CrossCorrResult:
        buys_a = get_buy_time_series(wallet_a, window)
        buys_b = get_buy_time_series(wallet_b, window)
        ccf = rolling_cross_correlation(buys_a, buys_b, max_lag=60)  # 60-minute max lag
        tau_star = argmax(ccf)
        llc = max(ccf)
        llr = ccf[tau_star < 0].mean() / ccf[tau_star > 0].mean()   # A leads if LLR > 1
        return CrossCorrResult(llt=tau_star, llc=llc, llr=llr)

    def granger_causality_test(wallet_a: str, wallet_b: str, p_lags: int = 4) -> float:
        # Returns p-value. Low p-value (< 0.05) = A Granger-causes B.
        buys_a = get_buy_time_series(wallet_a)
        buys_b = get_buy_time_series(wallet_b)
        restricted = VAR(p_lags).fit([buys_b])        # B only
        unrestricted = VAR(p_lags).fit([buys_a, buys_b])  # A + B
        return f_test_p_value(restricted, unrestricted)

    def score_pre_whale_edge(wallet_a: str, whale_b: str) -> LeadLagScore:
        ccf_result = compute_cross_correlation(wallet_a, whale_b, window=timedelta(days=90))
        p_value = granger_causality_test(wallet_a, whale_b)

        if ccf_result.llr < 1.2 or p_value > 0.05:
            return LeadLagScore(value=0, confidence=LOW)

        raw_score = (
            P_event_b_after_a(wallet_a, whale_b, T=timedelta(minutes=30))
          * median_tradable_return_after_entry(wallet_a)
          * exit_liquidity_success_rate(followers_of_wallet_a)
          * independence_multiplier(wallet_a)
          * freshness_multiplier(wallet_a)
          * confidence_factor(sample_size_n(wallet_a))
          - rug_follow_penalty(wallet_a)
          - crowding_penalty(wallet_a)
        )
        return LeadLagScore(value=normalize_0_100(raw_score), confidence=HIGH)
```

---

## Wallet cluster detection

```python
class WalletClusterer:
    def build_copurchase_graph(wallets: list[str]) -> Graph:
        # Bipartite wallet-token graph, projected to wallet-wallet.
        # Edge weight = co-purchase count * recency_weight.
        ...

    def run_louvain(graph: Graph, modularity_threshold: float = 0.4) -> list[Community]:
        # Phase 1: local modularity optimization per node.
        # Phase 2: collapse communities to super-nodes. Repeat.
        # Returns communities when Q converges.
        ...

    def score_cluster_suspicion(community: Community) -> float:
        timing_tightness = measure_inter_wallet_buy_delta(community)
        shared_funding = detect_shared_funding_source(community)
        co_purchase_rate = community.edge_density
        sync_exits = measure_synchronized_sells(community)
        social_diversity = measure_associated_social_diversity(community)

        return (
            0.30 * timing_tightness
          + 0.25 * shared_funding
          + 0.20 * co_purchase_rate
          + 0.15 * sync_exits
          + 0.10 * social_diversity
        )

    def classify_cluster(community: Community, suspicion: float) -> ClusterType:
        if suspicion > 0.70:
            if has_shared_dev_ancestry(community): return ClusterType.DEV_SUSPECT
            if has_high_frequency_bot_pattern(community): return ClusterType.BOT_FARM
            return ClusterType.CABAL_SUSPECT
        if has_consistent_early_alpha(community): return ClusterType.SMART_MONEY
        return ClusterType.UNKNOWN

    def build_clusters(wallets: list[str]) -> list[WalletCluster]:
        graph = build_copurchase_graph(wallets)
        communities = run_louvain(graph)
        clusters = []
        for c in communities:
            suspicion = score_cluster_suspicion(c)
            cluster_type = classify_cluster(c, suspicion)
            clusters.append(WalletCluster(members=c.nodes, type=cluster_type, confidence=suspicion))
        return clusters
```

---

## Wallet convergence scoring

```python
class WalletConvergenceScorer:
    RECENCY_LAMBDA = 0.05   # half-life ~14 minutes
    MIN_INDEPENDENT_BUYERS_FOR_UPGRADE = 3
    MAX_TIME_SPREAD_FOR_COMPRESSION = 1800  # 30 minutes in seconds

    def compute_convergence_score(token_mint: str) -> ConvergenceResult:
        buyers = GraphRepository.get_wallets_that_bought_token(token_mint)
        now = utcnow()

        weighted_sum = 0.0
        independent_count = 0
        entry_times = []

        for buyer in buyers:
            wallet_quality = WalletRepository.get_wallet_score(buyer.wallet_address).wallet_quality
            minutes_ago = (now - buyer.event_time).total_seconds() / 60
            recency_weight = exp(-RECENCY_LAMBDA * minutes_ago)

            cluster = GraphRepository.get_wallet_cluster(buyer.wallet_address)
            if cluster and cluster.type in [CABAL_SUSPECT, BOT_FARM]:
                independence_weight = 0.0   # excluded
            elif cluster and cluster.type == SMART_MONEY:
                independence_weight = 1.0 / len(GraphRepository.get_cluster_members(cluster.id))
            else:
                independence_weight = 1.0
                independent_count += 1

            weighted_sum += wallet_quality * recency_weight * independence_weight
            entry_times.append(buyer.event_time)

        time_spread_seconds = std_dev(entry_times).total_seconds()
        time_compression_factor = compute_time_compression(time_spread_seconds)
        independence_confidence = min(1.0, independent_count / 3)

        convergence_score = weighted_sum * time_compression_factor * independence_confidence

        return ConvergenceResult(
            convergence_score=normalize_0_100(convergence_score),
            independent_buyer_count=independent_count,
            time_spread_seconds=time_spread_seconds,
            qualifies_for_threshold_reduction=independent_count >= 2,
            qualifies_for_forced_strong_watch=(
                independent_count >= 3
                and time_spread_seconds <= 600   # 10 minutes
            ),
        )

    def compute_time_compression(time_spread_seconds: float) -> float:
        if time_spread_seconds > 1800: return 1.0
        if time_spread_seconds <= 300: return 2.0   # ≤5 min: max boost
        return 1.0 + (1 - time_spread_seconds / 1800)

    def get_threshold_adjustment(independent_count: int) -> int:
        # Returns how many points to subtract from decision thresholds.
        return min(20, max(0, (independent_count - 1) * 5))
```

---

## Live event pipeline

```python
class WalletEventIngestor:
    def handle_helius_webhook(payload: dict) -> list[WalletEvent]:
        parsed = HeliusClient.parse_transaction(payload["signature"])
        return extract_wallet_events(parsed)

    def is_candidate_buy(event: WalletEvent) -> bool:
        return event.event_type == BUY and event.token_mint is not None


class CandidateMintExtractor:
    def extract_candidate(event: WalletEvent) -> CandidateToken:
        return CandidateToken(
            token_mint=event.token_mint,
            first_seen_at=utcnow(),
            status=PENDING,
        )


class EvidenceGraphBuilder:
    def update_graph_from_event(event: WalletEvent) -> None:
        GraphRepository.add_wallet_token_edge(
            wallet=event.wallet_address,
            token_mint=event.token_mint,
            event_type=event.event_type,
            event_time=event.event_time,
        )
        update_candidate_relationships(event)
```

---

## Enrichment pipeline

```python
class MarketVerifier:
    def fetch_market_context(token_mint: str) -> MarketContext:
        dex_pairs = DexScreenerClient.get_token_pairs(token_mint)
        gecko_pools = GeckoTerminalClient.get_token_pools("solana", token_mint)
        birdeye_price = BirdeyeClient.get_price(token_mint)
        return reconcile_market_sources(dex_pairs, gecko_pools, birdeye_price)

    def check_volume_authenticity(context: MarketContext) -> float:
        ratio = context.unique_buyers_5m / (context.volume_5m / context.avg_trade_size)
        return min(1.0, ratio / 0.2)   # normalized; <0.2 = botlike

    def score_market_context(context: MarketContext) -> int:
        liquidity_realism = (
            normalize(context.liquidity_usd) * 0.30
          + context.sell_quote_success_score * 0.25
          + context.sol_side_depth_score * 0.20
          + context.route_count_score * 0.15
          - context.price_impact_penalty * 0.10
        )
        volume_auth = check_volume_authenticity(context)
        pool_maturity = normalize(context.pool_age_hours)
        price_stability = 1 - normalize(context.price_volatility_1h)

        return normalize_0_100(
            0.35 * liquidity_realism
          + 0.25 * volume_auth
          + 0.20 * price_stability
          + 0.20 * pool_maturity
        )


class ExecutionVerifier:
    def check_sellability(token_mint: str) -> SellabilityReport:
        quotes = [
            JupiterClient.quote(token_mint, SOL_MINT, amount, slippage_bps=500)
            for amount in [025_SOL_LAMPORTS, 1_SOL_LAMPORTS, 5_SOL_LAMPORTS]
        ]
        return build_sellability_report(quotes)


class SafetyVetoEngine:
    def compute_holder_concentration(token_mint: str) -> ConcentrationReport:
        holders = SolanaRpcClient.get_token_largest_accounts(token_mint)
        supply = SolanaRpcClient.get_token_supply(token_mint)
        balances = [h.amount / supply.amount for h in holders]

        # Gini coefficient
        N = len(balances)
        sorted_b = sorted(balances)
        gini = (2 * Σ((i+1) * sorted_b[i] for i in range(N))) / (N * Σ(sorted_b)) - (N+1)/N

        # Herfindahl-Hirschman Index
        hhi = Σ(b**2 for b in balances)

        return ConcentrationReport(gini=gini, hhi=hhi, top_10_pct=sum(balances[:10]))

    def detect_dev_dump(token_mint: str, creator_wallet: str) -> bool:
        creator_sells = get_recent_sells(creator_wallet, token_mint, window=timedelta(hours=4))
        creator_buys = get_recent_buys(creator_wallet, token_mint, window=timedelta(days=1))
        time_since_launch = get_pool_age(token_mint)
        return (
            sum(creator_sells) > sum(creator_buys) * 0.5
            and time_since_launch < timedelta(hours=4)
        )

    def evaluate(token_mint: str, context: TokenContext) -> RiskReport:
        vetoes = []
        penalties = []

        # Hard vetoes
        if not context.sellability.route_exists: vetoes.append("NO_SELL_ROUTE")
        if context.market.liquidity_usd < config.MIN_LIQUIDITY: vetoes.append("LIQUIDITY_TOO_LOW")
        if context.sellability.price_impact_1_sol > 0.15: vetoes.append("PRICE_IMPACT_TOO_HIGH")
        if context.risk.mint_authority_active: vetoes.append("ACTIVE_MINT_AUTHORITY")
        if context.risk.freeze_authority_active: vetoes.append("ACTIVE_FREEZE_AUTHORITY")

        concentration = compute_holder_concentration(token_mint)
        if concentration.gini > 0.90 or concentration.hhi > 0.25:
            vetoes.append("TOP_HOLDER_TOO_CONCENTRATED")

        if context.candidate.creator_wallet:
            if detect_dev_dump(token_mint, context.candidate.creator_wallet):
                vetoes.append("DEV_DUMP_DETECTED")

        if is_copycat_mint(token_mint, context): vetoes.append("COPYCAT_MINT")

        # Soft penalties — applied as score reductions, not vetoes
        if context.market.pool_age_minutes < 10: penalties.append(("POOL_TOO_NEW", 15))
        if check_volume_authenticity(context.market) < 0.2: penalties.append(("VOLUME_TOO_BOTLIKE", 20))

        # Dempster-Shafer combination for partial risk signals
        ds_belief = dempster_shafer_combine(
            partial_signals=[
                bpa_from_concentration(concentration),
                bpa_from_liquidity(context.market),
                bpa_from_authority_checks(context.risk),
            ]
        )
        if ds_belief["RISKY"] > 0.85: vetoes.append("DS_COMBINED_RISK")
        elif ds_belief["RISKY"] > 0.60: penalties.append(("DS_PARTIAL_RISK", 20))

        risk_score = max(0, 100 - Σ(p[1] for p in penalties))
        if vetoes: risk_score = 0

        return RiskReport(vetoes=vetoes, penalties=penalties, risk_score=risk_score,
                          gini=concentration.gini, hhi=concentration.hhi)
```

---

## Social and narrative verification

```python
class SocialTrendVerifier:
    def build_search_terms(token: CandidateToken) -> list[str]:
        return [
            token.token_mint,
            token.symbol,
            token.name,
            normalize(token.symbol),
            normalize(token.name),
        ]

    def compute_velocity_acceleration(mentions: list[MentionRecord]) -> float:
        v_5m = count_in_window(mentions, last_5_min)
        v_prev = count_in_window(mentions, min_5_to_10)
        return v_5m - v_prev   # positive = accelerating

    def compute_novelty_score(posts: list[str], embedder: SentenceTransformer) -> float:
        # Low score = near-identical posts = coordinated / bots.
        # High score = diverse organic discussion.
        embeddings = [embedder.encode(p) for p in posts]
        pairwise_sims = [cosine_similarity(embeddings[i], embeddings[i+1]) for i in range(len(embeddings)-1)]
        return 1 - mean(pairwise_sims)

    def score_unique_sources(mentions: list[MentionRecord]) -> float:
        quality_accounts = [
            m for m in mentions
            if m.account_age_days > 30
        ]
        return normalize(len(set(m.account_id for m in quality_accounts)))

    def classify_narrative(token: CandidateToken, evidence: SocialEvidence) -> NarrativeType:
        # Classifier over token.name + token.symbol + top social posts.
        # Returns: REAL_WORLD_EVENT, ANIMAL, AI_TECH, CELEBRITY, DERIVATIVE, UNKNOWN.
        ...

    def fetch_and_score(token: CandidateToken) -> SocialScore:
        terms = build_search_terms(token)
        reddit = RedditClient.search_mentions(terms, TARGET_SUBREDDITS, window=timedelta(hours=24))
        telegram = TelegramClient.scan_authorized_channels(terms, window=timedelta(hours=6))
        discord = DiscordClient.scan_authorized_servers(terms, window=timedelta(hours=6))
        gdelt = GdeltClient.search_news_events(terms, window=timedelta(days=7))
        youtube = YouTubeClient.search_video_mentions(terms, window=timedelta(days=7))

        all_mentions = merge_social_evidence(reddit, telegram, discord, gdelt, youtube)
        all_posts = [m.text for m in all_mentions]

        velocity_accel = compute_velocity_acceleration(all_mentions)
        novelty = compute_novelty_score(all_posts, embedder=CRYPTO_BERT)
        unique_src = score_unique_sources(all_mentions)
        gdelt_match = score_gdelt_match(gdelt, token)
        mint_mentions = count_mint_address_mentions(all_mentions, token.token_mint)
        cross_platform = count_platforms_represented(all_mentions)

        social_score = normalize_0_100(
            0.25 * normalize(velocity_accel)
          + 0.20 * unique_src
          + 0.15 * novelty
          + 0.15 * gdelt_match
          + 0.10 * normalize(mint_mentions)
          + 0.10 * normalize(cross_platform)
          + 0.05 * content_quality_score(all_mentions)
        )
        return SocialScore(value=social_score, novelty=novelty, unique_sources=len(set(...)))
```

---

## Evidence fusion scoring

```python
class EvidenceFusionScorer:
    BASE_THRESHOLDS = {"AVOID": 45, "WATCH": 45, "STRONG_WATCH": 60, "STRONG_CANDIDATE": 75}

    def calculate_wallet_score(token_mint: str, convergence: ConvergenceResult) -> int:
        # Primary component is the convergence score (weighted multi-wallet signal).
        # Augmented by lead-lag strength of triggering wallets.
        lead_lag_bonus = mean([
            WalletRepository.get_wallet_score(w).lead_lag_score
            for w in get_triggering_wallets(token_mint)
        ])
        return normalize_0_100(0.70 * convergence.convergence_score + 0.30 * lead_lag_bonus)

    def calculate_history_score(token_mint: str, context: TokenContext) -> int:
        creator_rep = score_creator_reputation(context.candidate.creator_wallet)
        early_holder_quality = mean([
            get_wallet_quality(w) for w in get_first_N_holders(token_mint, N=50)
        ])
        launch_context = score_launch_source(context.candidate.launch_source)
        pool_context = score_pool_creation_context(token_mint)

        return normalize_0_100(
            0.40 * creator_rep
          + 0.30 * early_holder_quality
          + 0.20 * launch_context
          + 0.10 * pool_context
        )

    def final_score(context: TokenContext, convergence: ConvergenceResult) -> TokenScoreSnapshot:
        if context.risk.has_hard_veto():
            return TokenScoreSnapshot(
                decision=AVOID,
                total_score=0,
                score_reasons=context.risk.vetoes,
            )

        wallet_score = calculate_wallet_score(context.candidate.token_mint, convergence)
        market_score = MarketVerifier.score_market_context(context.market)
        risk_score = context.risk.risk_score
        social_score = context.social.value
        history_score = calculate_history_score(context.candidate.token_mint, context)
        execution_score = score_execution(context.sellability)

        total = (
            0.35 * wallet_score
          + 0.20 * market_score
          + 0.20 * risk_score
          + 0.15 * social_score
          + 0.07 * history_score
          + 0.03 * execution_score
        )

        # Apply convergence threshold reduction
        threshold_adj = WalletConvergenceScorer.get_threshold_adjustment(
            convergence.independent_buyer_count
        )
        adjusted_thresholds = {k: v - threshold_adj for k, v in BASE_THRESHOLDS.items()}

        # Convergence upgrade override
        if convergence.qualifies_for_forced_strong_watch:
            decision = max_decision(classify_decision(total, adjusted_thresholds), STRONG_WATCH)
        else:
            decision = classify_decision(total, adjusted_thresholds)

        return TokenScoreSnapshot(
            total_score=int(total),
            decision=decision,
            wallet_score=wallet_score,
            market_score=market_score,
            risk_score=risk_score,
            social_score=social_score,
            history_score=history_score,
            execution_score=execution_score,
            convergence_independent_count=convergence.independent_buyer_count,
            convergence_time_spread_s=convergence.time_spread_seconds,
        )
```

---

## Alerting and audit

```python
class AlertPublisher:
    def should_alert(score: TokenScoreSnapshot) -> bool:
        return score.decision in [STRONG_WATCH, STRONG_CANDIDATE]

    def format_alert(token: CandidateToken, score: TokenScoreSnapshot, context: TokenContext) -> str:
        convergence_line = (
            f"{score.convergence_independent_count} independent wallets "
            f"({score.convergence_time_spread_s:.0f}s spread)"
        )
        return format_evidence_summary(token, score, context, convergence_line)

    def publish(score: TokenScoreSnapshot, context: TokenContext) -> Alert:
        if not should_alert(score):
            return save_skipped_alert(score)
        message = format_alert(context.candidate, score, context)
        send_to_channels(message)
        return save_alert(score, message)


class AuditLedger:
    def record_decision(token_mint: str, full_context: TokenContext, score: TokenScoreSnapshot) -> None:
        # Store the full context snapshot: every sub-score, every reason code,
        # convergence details, risk flags. Required to explain the decision later
        # and to feed the outcome labeling pipeline.
        ...
```

---

## Outcome labeling and Thompson Sampling feedback

```python
class OutcomeLabeler:
    def measure_tradable_return(alert: Alert, t: timedelta) -> float:
        # Simulate a 1 SOL sell using Jupiter quote at time (alert.sent_at + t).
        # Returns estimated_output_sol — not raw price.
        ...

    def classify_outcome(alert: Alert) -> OutcomeLabel:
        returns = {
            "5m": measure_tradable_return(alert, timedelta(minutes=5)),
            "1h": measure_tradable_return(alert, timedelta(hours=1)),
            "24h": measure_tradable_return(alert, timedelta(hours=24)),
            "7d": measure_tradable_return(alert, timedelta(days=7)),
        }
        liquidity_7d = get_liquidity_at(alert.token_mint, alert.sent_at + timedelta(days=7))

        if liquidity_7d > HEAVY_HITTER_LIQUIDITY_THRESHOLD: return HEAVY_HITTER
        if returns["7d"] > 2.0 and liquidity_7d > SURVIVOR_LIQUIDITY_THRESHOLD: return SURVIVOR
        if returns["1h"] > 1.2: return TRADEABLE_RUNNER
        if max(returns.values()) > 1.5 and returns["7d"] < 0.8: return ONE_CYCLE_PUMP
        if get_liquidity_at(alert.token_mint, alert.sent_at + timedelta(hours=24)) < DEAD_THRESHOLD: return DEAD_ON_ARRIVAL
        return RUG   # liquidity vanished


class WalletReRanker:
    def update_from_outcome(alert: Alert, outcome: OutcomeLabel) -> None:
        wallets = get_triggering_wallets(alert.token_mint)
        for wallet_address in wallets:
            alpha, beta = WalletRepository.get_wallet_beta_posterior(wallet_address)

            if outcome in [TRADEABLE_RUNNER, HEAVY_HITTER]:
                alpha += 1.0
            elif outcome in [SURVIVOR, ONE_CYCLE_PUMP]:
                alpha += 0.5
            elif outcome in [RUG, DEAD_ON_ARRIVAL]:
                beta += 1.0
            else:
                beta += 0.5

            WalletRepository.save_wallet_beta_posterior(wallet_address, alpha, beta)

    def sample_wallet_trust(wallet_address: str) -> float:
        alpha, beta = WalletRepository.get_wallet_beta_posterior(wallet_address)
        return Beta(alpha, beta).sample()   # Thompson Sampling

    def update_all_wallet_scores_from_recent_outcomes() -> None:
        alerts = AlertRepository.list_recent_labeled_alerts(days=7)
        for alert in alerts:
            outcome = get_outcome(alert)
            update_from_outcome(alert, outcome)
        # After updating posteriors, trigger full wallet quality recalculation
        for wallet in WalletRepository.list_active_wallets():
            WalletQualityModel.score_wallet(wallet.wallet_address)
```

---

## Main pipeline orchestration

```python
class WigsPipeline:
    def handle_wallet_event(event: WalletEvent) -> TokenScoreSnapshot | None:
        WalletRepository.save_wallet_event(event)

        if not WalletEventIngestor.is_candidate_buy(event):
            return None

        candidate = CandidateMintExtractor.extract_candidate(event)
        TokenRepository.upsert_candidate_token(candidate)
        EvidenceGraphBuilder.update_graph_from_event(event)

        # Compute convergence first — this determines whether we fast-track enrichment
        convergence = WalletConvergenceScorer.compute_convergence_score(event.token_mint)

        # Always enrich, but prioritize tokens with high convergence
        market = MarketVerifier.fetch_market_context(event.token_mint)
        sellability = ExecutionVerifier.check_sellability(event.token_mint)
        risk = SafetyVetoEngine.evaluate(event.token_mint, TokenContext(market=market, sellability=sellability))
        social = SocialTrendVerifier.fetch_and_score(candidate)
        history = HistoryAnalyzer.analyze(event.token_mint)

        context = TokenContext(
            candidate=candidate,
            market=market,
            sellability=sellability,
            risk=risk,
            social=social,
            history=history,
        )

        score = EvidenceFusionScorer.final_score(context, convergence)
        TokenRepository.save_token_score(score)

        AlertPublisher.publish(score, context)
        AuditLedger.record_decision(event.token_mint, context, score)

        return score
```

---

## Scheduled jobs

```python
class ScheduledJobs:
    def refresh_tracked_wallet_set_every_24h():
        # Re-run WalletUniverseBuilder. Add new candidates. Retire degraded wallets.
        ...

    def update_wallet_scores_every_6h():
        # Recompute all 8 sub-scores for all ACTIVE and DEGRADED wallets.
        # Update lifecycle state (ACTIVE → DEGRADED if quality < 50; DEGRADED → RETIRED if < 25).
        ...

    def refresh_open_candidate_scores_every_5m():
        # Re-score WATCH and STRONG_WATCH tokens that have not yet been labeled.
        # A new wallet buy re-triggers convergence scoring and may upgrade the tier.
        ...

    def label_alert_outcomes_every_15m():
        # For each unlabeled alert, check if any measurement windows have elapsed.
        # Record tradable returns. Assign OutcomeLabel once all windows are complete.
        ...

    def update_wallet_posteriors_every_6h():
        # Run Thompson Sampling updates for all wallets with new labeled outcomes.
        ...

    def rebuild_wallet_clusters_every_24h():
        # Re-run Louvain on the updated co-purchase graph.
        # Re-classify cluster types.
        ...

    def retrain_wallet_quality_weights_monthly():
        # XGBoost regression on labeled outcomes to update sub-score weights.
        # Only run if > 500 labeled outcomes exist.
        ...

    def run_backtest_weekly():
        # Replay historical window. Reconstruct events. Simulate pipeline.
        # Measure recall (how many TRADEABLE_RUNNER tokens were caught) and
        # precision (how many STRONG_CANDIDATEs became TRADEABLE_RUNNER or better).
        ...
```
