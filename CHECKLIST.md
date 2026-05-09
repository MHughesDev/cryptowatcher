# WIGS Implementation Checklist

Ordered by dependency. Each item must be done before items below it that depend on it.
Check off items as they are completed.

---

## Block 1 — Project Scaffold

- [ ] `pyproject.toml` — Python 3.12, all dependencies declared
- [ ] `.env.example` — all required env vars documented
- [ ] `Dockerfile` — Python 3.12 slim, non-root user, proper layering
- [ ] `docker-compose.yml` — app + PostgreSQL + Redis services
- [ ] `src/wigs/__init__.py`
- [ ] `src/wigs/config.py` — Pydantic BaseSettings, typed config, loaded from env

---

## Block 2 — Database Layer

- [ ] `src/wigs/models.py` — all SQLAlchemy ORM tables
  - [ ] `tracked_wallets`
  - [ ] `wallet_events`
  - [ ] `wallet_score_snapshots`
  - [ ] `wallet_beta_posteriors`
  - [ ] `wallet_clusters`
  - [ ] `wallet_cluster_members`
  - [ ] `candidate_tokens`
  - [ ] `token_pools`
  - [ ] `token_market_snapshots`
  - [ ] `token_risk_snapshots`
  - [ ] `social_snapshots`
  - [ ] `token_scores`
  - [ ] `alerts`
  - [ ] `token_outcomes`
- [ ] Alembic initialized (`alembic init`)
- [ ] `alembic/env.py` — async SQLAlchemy wired in
- [ ] Initial migration generated and tested
- [ ] `src/wigs/database.py` — async engine, session factory, get_db dependency

---

## Block 3 — API Clients

- [ ] `src/wigs/clients/helius.py`
  - [ ] `create_wallet_webhook()`
  - [ ] `parse_transaction()`
  - [ ] `get_transactions_for_address()`
- [ ] `src/wigs/clients/solana_rpc.py`
  - [ ] `get_token_supply()`
  - [ ] `get_token_largest_accounts()`
  - [ ] `get_transaction()`
  - [ ] `get_signatures_for_address()`
- [ ] `src/wigs/clients/dexscreener.py`
  - [ ] `get_token_pairs()`
  - [ ] `get_token_profile()`
  - [ ] `get_paid_orders()`
- [ ] `src/wigs/clients/geckoterminal.py`
  - [ ] `get_token_pools()`
  - [ ] `get_ohlcv()`
- [ ] `src/wigs/clients/birdeye.py`
  - [ ] `get_price()`
  - [ ] `get_token_trades()`
  - [ ] `get_token_security()`
- [ ] `src/wigs/clients/jupiter.py`
  - [ ] `quote()`
  - [ ] `estimate_sellability()` — run at 0.25, 1, 5 SOL sizes
- [ ] `src/wigs/clients/reddit.py`
  - [ ] `search_mentions()`
- [ ] `src/wigs/clients/telegram.py`
  - [ ] `scan_authorized_channels()`
- [ ] `src/wigs/clients/discord.py`
  - [ ] `scan_authorized_servers()`
- [ ] `src/wigs/clients/gdelt.py`
  - [ ] `search_news_events()`
- [ ] `src/wigs/clients/youtube.py`
  - [ ] `search_video_mentions()`
- [ ] `src/wigs/clients/__init__.py` — re-exports all clients
- [ ] Rate limit handling in every client (retry with backoff)
- [ ] Client-level error handling (timeouts, 4xx, 5xx, empty responses)

---

## Block 4 — Repository Layer

- [ ] `src/wigs/repositories/wallet_repo.py`
  - [ ] `upsert_tracked_wallet()`
  - [ ] `list_active_wallets()`
  - [ ] `save_wallet_event()`
  - [ ] `get_wallet_events_for_token()`
  - [ ] `get_recent_wallet_events()`
  - [ ] `save_wallet_score()`
  - [ ] `get_wallet_score()`
  - [ ] `save_wallet_beta_posterior()`
  - [ ] `get_wallet_beta_posterior()`
- [ ] `src/wigs/repositories/token_repo.py`
  - [ ] `upsert_candidate_token()`
  - [ ] `save_market_snapshot()`
  - [ ] `save_risk_snapshot()`
  - [ ] `save_social_snapshot()`
  - [ ] `save_token_score()`
  - [ ] `get_latest_token_context()`
- [ ] `src/wigs/repositories/graph_repo.py`
  - [ ] `add_wallet_token_edge()`
  - [ ] `add_wallet_wallet_edge()`
  - [ ] `get_wallet_cluster()`
  - [ ] `get_cluster_members()`
  - [ ] `save_cluster()`
  - [ ] `get_wallets_that_bought_token()`
- [ ] `src/wigs/repositories/alert_repo.py`
  - [ ] `save_alert()`
  - [ ] `list_unlabeled_alerts()`
  - [ ] `list_recent_labeled_alerts()`
  - [ ] `save_outcome()`
- [ ] `src/wigs/repositories/__init__.py`

---

## Block 5 — Wallet Engine (Algorithms)

- [ ] `src/wigs/algorithms/wallet_quality.py`
  - [ ] `calculate_realized_pnl_score()`
  - [ ] `calculate_early_entry_score()` — entry percentile + event lead bonuses
  - [ ] `calculate_exit_quality_score()` — drawdown avoided
  - [ ] `calculate_rug_avoidance_score()`
  - [ ] `calculate_repeatability_score()` — Shannon entropy over return buckets
  - [ ] `calculate_independence_score()` — cosine similarity vs cluster
  - [ ] `calculate_freshness_score()` — exponential decay λ=0.1 over weekly windows
  - [ ] `score_wallet()` — composite weighted formula
- [ ] `src/wigs/algorithms/lead_lag.py`
  - [ ] `compute_cross_correlation()` — rolling CCF, LLT, LLC, LLR
  - [ ] `granger_causality_test()` — VAR(4), F-test p-value
  - [ ] `calculate_lead_lag_score()` — full formula with penalties
- [ ] `src/wigs/algorithms/clustering.py`
  - [ ] `build_copurchase_graph()` — bipartite projection to wallet-wallet graph
  - [ ] `run_louvain()` — modularity optimization
  - [ ] `score_cluster_suspicion()` — 5-factor formula
  - [ ] `classify_cluster()` — SMART_MONEY / CABAL_SUSPECT / BOT_FARM / etc.
  - [ ] `build_clusters()` — full pipeline entry point
- [ ] `src/wigs/algorithms/wallet_universe.py`
  - [ ] `discover_from_historical_winners()`
  - [ ] `discover_pre_whale_wallets()`
  - [ ] `discover_kol_precall_wallets()`
  - [ ] `build_seed_wallet_set()`

---

## Block 6 — Candidate Scoring (Algorithms)

- [ ] `src/wigs/algorithms/convergence.py`
  - [ ] `compute_convergence_score()` — recency decay + independence weight + time compression
  - [ ] `compute_time_compression_factor()`
  - [ ] `get_threshold_adjustment()` — point reduction per independent buyer count
- [ ] `src/wigs/algorithms/market_verifier.py`
  - [ ] `fetch_market_context()` — reconcile DexScreener + Gecko + Birdeye
  - [ ] `check_volume_authenticity()` — unique buyers / wash trade ratio
  - [ ] `score_market_context()`
- [ ] `src/wigs/algorithms/safety_veto.py`
  - [ ] `compute_holder_concentration()` — Gini coefficient + HHI
  - [ ] `detect_dev_dump()`
  - [ ] `is_copycat_mint()`
  - [ ] `dempster_shafer_combine()` — BPA combination, conflict term K
  - [ ] `evaluate()` — hard vetoes + soft penalties + DS combination
- [ ] `src/wigs/algorithms/social_verifier.py`
  - [ ] `build_search_terms()`
  - [ ] `compute_velocity_acceleration()`
  - [ ] `compute_novelty_score()` — CryptoBERT embeddings, cosine similarity
  - [ ] `score_unique_sources()` — account age filter
  - [ ] `classify_narrative()`
  - [ ] `fetch_and_score()` — full pipeline
- [ ] `src/wigs/algorithms/execution_verifier.py`
  - [ ] `check_sellability()` — Jupiter quotes at 3 sizes
  - [ ] `score_execution()`
- [ ] `src/wigs/algorithms/history_analyzer.py`
  - [ ] `score_creator_reputation()`
  - [ ] `score_early_holder_quality()`
  - [ ] `score_launch_context()`
  - [ ] `analyze()`
- [ ] `src/wigs/algorithms/evidence_fusion.py`
  - [ ] `calculate_wallet_score()` — convergence + lead-lag blend
  - [ ] `calculate_history_score()`
  - [ ] `final_score()` — weighted formula, threshold adjustment, convergence override
- [ ] `src/wigs/algorithms/outcome_labeler.py`
  - [ ] `measure_tradable_return()` — Jupiter quote simulation at each window
  - [ ] `classify_outcome()`
- [ ] `src/wigs/algorithms/feedback.py`
  - [ ] `update_from_outcome()` — Beta(α, β) posterior update
  - [ ] `sample_wallet_trust()` — Thompson Sampling
  - [ ] `update_all_wallet_scores_from_recent_outcomes()`
  - [ ] `retrain_wallet_quality_weights()` — XGBoost on labeled outcomes (monthly)
- [ ] `src/wigs/algorithms/__init__.py`

---

## Block 7 — Core Pipeline

- [ ] `src/wigs/pipeline.py`
  - [ ] `WalletEventIngestor.handle_helius_webhook()`
  - [ ] `WalletEventIngestor.is_candidate_buy()`
  - [ ] `CandidateMintExtractor.extract_candidate()`
  - [ ] `EvidenceGraphBuilder.update_graph_from_event()`
  - [ ] `WigsPipeline.handle_wallet_event()` — full orchestration
  - [ ] `AuditLedger.record_decision()`

---

## Block 8 — Alert System

- [ ] `src/wigs/alerts.py`
  - [ ] `AlertPublisher.should_alert()`
  - [ ] `AlertPublisher.format_alert()` — includes convergence count + spread in message
  - [ ] `AlertPublisher.publish()`
  - [ ] Telegram channel send
  - [ ] Discord webhook send
  - [ ] Log fallback (always write to structured log)

---

## Block 9 — Background Workers

- [ ] `src/wigs/workers.py`
  - [ ] `refresh_tracked_wallet_set_every_24h()`
  - [ ] `update_wallet_scores_every_6h()`
  - [ ] `refresh_open_candidate_scores_every_5m()`
  - [ ] `label_alert_outcomes_every_15m()`
  - [ ] `update_wallet_posteriors_every_6h()`
  - [ ] `rebuild_wallet_clusters_every_24h()`
  - [ ] `retrain_wallet_quality_weights_monthly()`
  - [ ] `run_backtest_weekly()`
  - [ ] APScheduler or Celery Beat wired in

---

## Block 10 — API Server

- [ ] `src/wigs/app.py`
  - [ ] `POST /webhook/helius` — receive and process Helius events
  - [ ] `GET /health` — liveness check
  - [ ] `GET /candidates` — list recent scored candidates
  - [ ] `GET /candidates/{token_mint}` — full score + context for one token
  - [ ] `GET /wallets` — list tracked wallets with current scores
  - [ ] `GET /wallets/{address}` — single wallet detail + score history
  - [ ] `GET /alerts` — recent alert history
  - [ ] Webhook signature verification (Helius HMAC)

---

## Block 11 — Tests

- [ ] `tests/test_convergence.py` — convergence formula, time compression, threshold adjustment
- [ ] `tests/test_clustering.py` — Louvain on synthetic graphs, suspicion scoring
- [ ] `tests/test_safety_veto.py` — Gini, HHI, hard veto triggers, DS combination
- [ ] `tests/test_social_verifier.py` — novelty score, velocity acceleration, bot detection
- [ ] `tests/test_evidence_fusion.py` — final score formula, convergence override
- [ ] `tests/test_pipeline.py` — end-to-end with mocked API responses
- [ ] `tests/test_feedback.py` — Thompson Sampling, Beta posterior updates
- [ ] `tests/conftest.py` — fixtures, mock clients, test DB

---

## Block 12 — Ops and Config

- [ ] `.env` filled in locally (not committed)
  - [ ] `HELIUS_API_KEY`
  - [ ] `HELIUS_WEBHOOK_SECRET`
  - [ ] `SOLANA_RPC_URL`
  - [ ] `BIRDEYE_API_KEY`
  - [ ] `YOUTUBE_API_KEY`
  - [ ] `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`
  - [ ] `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
  - [ ] `DISCORD_WEBHOOK_URL`
  - [ ] `DATABASE_URL`
  - [ ] `REDIS_URL`
  - [ ] Score thresholds + liquidity minimums
- [ ] Seed wallet list populated (at least 10–20 known quality wallets)
- [ ] Helius webhook registered pointing to deployed endpoint
- [ ] Docker services confirmed running
- [ ] First live wallet event received and processed end-to-end

---

## Block 13 — First Real Run

- [ ] System running, webhook live
- [ ] At least one candidate token detected and scored
- [ ] At least one alert fired to Telegram or Discord
- [ ] Audit log entry confirmed for that alert
- [ ] Outcome labeling job running (will label the alert after time windows elapse)
