"""Background workers — scheduled jobs that run alongside the API server."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete

from wigs.algorithms import clustering, wallet_quality, wallet_universe
from wigs.algorithms.convergence import compute_convergence_score
from wigs.algorithms.evidence_fusion import compute_final_score
from wigs.algorithms.execution_verifier import check_sellability, score_execution
from wigs.algorithms.feedback import retrain_wallet_quality_weights as retrain_weights_algo
from wigs.algorithms.feedback import update_all_wallet_scores_from_recent_outcomes
from wigs.algorithms.history_analyzer import analyze as analyze_history
from wigs.algorithms.market_verifier import fetch_market_context, score_market_context
from wigs.algorithms.outcome_labeler import label_token_outcome
from wigs.algorithms.safety_veto import ConcentrationReport, evaluate
from wigs.algorithms.social_verifier import SocialEvidence, SocialScore, fetch_and_score
from wigs.clients import dexscreener, helius, jupiter, solana_rpc
from wigs.config import get_settings
from wigs.database import AsyncSessionLocal
from wigs.models import WalletCluster, WalletClusterMember
from wigs.observability import metrics
from wigs.pipeline import fetch_risk_data, load_convergence_buyers
from wigs.repositories import alert_repo, graph_repo, token_repo, wallet_repo

log = logging.getLogger(__name__)
settings = get_settings()


def _wallet_events_to_trades(events: list[Any]) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for event in events:
        trades.append(
            {
                "token_mint": event.token_mint,
                "pnl_usd": float(event.amount_usd or 0.0),
                "entry_percentile": 0.5,
                "drawdown_avoided_pct": 0.5,
                "tradable_return_pct": 0.0,
                "lead_lag_score": 50,
                "is_rug": False,
                "rug_exposure": 0.0,
            }
        )
    return trades


async def refresh_open_candidate_scores() -> None:
    """Re-score tokens in WATCH / STRONG_WATCH state with full enrichment."""
    async with AsyncSessionLocal() as db:
        candidates = await token_repo.list_open_candidates(db, ["WATCH", "STRONG_WATCH"])
        log.info("Refreshing %d open candidates", len(candidates))
        for token in candidates:
            try:
                buyers = await load_convergence_buyers(token.token_mint, db)
                convergence = compute_convergence_score(buyers)
                market_ctx = await fetch_market_context(token.token_mint)
                risk_data = await fetch_risk_data(token.token_mint, token.creator_wallet)
                social = await fetch_and_score(token.token_mint, token.symbol, token.name)
                history = await analyze_history(
                    token.token_mint,
                    token.creator_wallet,
                    market_ctx.pool_age_minutes or 0.0,
                    db,
                    solana_rpc,
                    helius,
                )
                concentration, mint_auth, freeze_auth, dev_dump, sell_report = risk_data
                risk_report = evaluate(
                    liquidity_usd=market_ctx.liquidity_usd,
                    mint_authority_active=mint_auth,
                    freeze_authority_active=freeze_auth,
                    concentration=concentration,
                    sell_quote_exists=sell_report.route_exists,
                    price_impact_1_sol=sell_report.price_impact_1_sol,
                    price_impact_5_sol=sell_report.price_impact_5_sol,
                    pool_age_minutes=market_ctx.pool_age_minutes,
                    volume_authenticity_ratio=(
                        market_ctx.buyers_5m / max(1, market_ctx.volume_5m / 100)
                        if market_ctx.volume_5m and market_ctx.buyers_5m
                        else None
                    ),
                    has_social_data=social.value > 0,
                    independent_buyer_count=convergence.independent_buyer_count,
                    cluster_is_independent=convergence.independent_buyer_count > 0,
                    kol_already_called=False,
                    dev_dump_detected=dev_dump,
                    copycat_mint=False,
                    social_drainer_link=False,
                )
                wallet_score = min(
                    100,
                    int(0.70 * convergence.convergence_score + 0.30 * (buyers[0].wallet_quality if buyers else 50)),
                )
                execution_score = score_execution(sell_report, settings.max_price_impact_1_sol)
                result = compute_final_score(
                    wallet_score=wallet_score,
                    market_score=score_market_context(market_ctx),
                    risk_report=risk_report,
                    social_score=social,
                    history_score=history,
                    execution_score=execution_score,
                    convergence=convergence,
                )
                await token_repo.save_market_snapshot(db, token.token_mint, market_ctx)
                await token_repo.save_risk_snapshot(
                    db,
                    token.token_mint,
                    risk_report,
                    concentration,
                    mint_authority_active=mint_auth,
                    freeze_authority_active=freeze_auth,
                    sell_quote_exists=sell_report.route_exists,
                    price_impact_025_sol=sell_report.price_impact_025_sol,
                    price_impact_1_sol=sell_report.price_impact_1_sol,
                    price_impact_5_sol=sell_report.price_impact_5_sol,
                )
                await token_repo.save_social_snapshot(db, token.token_mint, social)
                await token_repo.save_token_score(db, result, token.token_mint)
                token.status = result.decision if result.decision != "AVOID" else "REJECTED"
                await db.commit()
            except Exception as exc:
                await db.rollback()
                log.warning("Failed to refresh %s: %s", token.token_mint, exc)


async def label_alert_outcomes() -> None:
    """Label completed alert outcomes after the measurement window passes."""
    async with AsyncSessionLocal() as db:
        alerts = await alert_repo.list_unlabeled_alerts(db)
        now = datetime.utcnow()
        for alert in alerts:
            if now - alert.sent_at < timedelta(days=7):
                continue
            try:
                pairs = await dexscreener.get_token_pairs(alert.token_mint)
                liq_now = max(
                    (float(pair.get("liquidity", {}).get("usd", 0) or 0) for pair in pairs),
                    default=0.0,
                )
                label = await label_token_outcome(
                    token_mint=alert.token_mint,
                    alert_id=alert.id,
                    alert_time=alert.sent_at,
                    initial_liquidity_usd=liq_now,
                    jupiter_client=jupiter,
                    dexscreener_client=dexscreener,
                    db=db,
                )
                await db.commit()
                log.info("Labeled %s -> %s", alert.token_mint, label)
            except Exception as exc:
                await db.rollback()
                log.warning("Failed to label alert %s: %s", alert.id, exc)


async def update_wallet_posteriors() -> None:
    """Update Thompson Sampling Beta posteriors for wallets with new outcomes."""
    async with AsyncSessionLocal() as db:
        updated = await update_all_wallet_scores_from_recent_outcomes(db)
        await db.commit()
        log.info("Updated posteriors for %d wallet-event rows", updated)


async def discover_new_wallets() -> None:
    """Discover and add wallets (additive only), then score those with available events."""
    async with AsyncSessionLocal() as db:
        outcomes = await alert_repo.list_recent_completed_outcomes(db, limit=200)
        historical_winner_mints = [
            outcome.token_mint
            for outcome in outcomes
            if outcome.label in {"HEAVY_HITTER", "TRADEABLE_RUNNER"}
        ]
        active_wallets = await wallet_repo.list_active_wallets(db)
        kol_wallets = [
            wallet.wallet_address
            for wallet in active_wallets
            if wallet.wallet_type == "KOL_PRECALL"
        ]
        discovered = await wallet_universe.build_seed_wallet_set(
            historical_winner_mints,
            kol_wallets,
            helius,
            solana_rpc,
            db,
        )
        discovered_count = len(discovered)
        added = 0
        existing = 0
        reactivated = 0
        scored = 0
        skipped_no_events = 0
        for wallet_address in discovered:
            existing_wallet = await wallet_repo.get_tracked_wallet(db, wallet_address)
            if existing_wallet is None:
                added += 1
            else:
                existing += 1
                if not existing_wallet.is_active:
                    reactivated += 1
            await wallet_repo.upsert_tracked_wallet(
                db,
                wallet_address,
                source="seed_builder",
                wallet_type=existing_wallet.wallet_type if existing_wallet else "SCOUT",
            )
            events = await wallet_repo.get_recent_wallet_events(db, wallet_address, limit=100)
            if not events:
                skipped_no_events += 1
                continue
            trades = _wallet_events_to_trades(events)
            scores = wallet_quality.score_wallet(wallet_address, trades, [], 0.0)
            await wallet_repo.save_wallet_score(db, wallet_address, scores)
            scored += 1
        await db.commit()
        log.info(
            "Wallet discovery complete | discovered=%d added=%d existing=%d reactivated=%d scored=%d skipped_no_events=%d",
            discovered_count,
            added,
            existing,
            reactivated,
            scored,
            skipped_no_events,
        )


async def refresh_tracked_wallet_set() -> None:
    """Backward-compatible wrapper for legacy job name."""
    await discover_new_wallets()


async def update_wallet_scores() -> None:
    """Recompute wallet quality scores for all active wallets."""
    async with AsyncSessionLocal() as db:
        wallets = await wallet_repo.list_active_wallets(db)
        updated = 0
        active_count = 0
        degraded_count = 0
        retired_count = 0
        now = datetime.utcnow()
        for wallet in wallets:
            events = await wallet_repo.get_recent_wallet_events(db, wallet.wallet_address, limit=100)
            if not events:
                continue
            cluster = await graph_repo.get_wallet_cluster(db, wallet.wallet_address)
            cluster_members = []
            if cluster is not None:
                members = await graph_repo.get_cluster_members(db, cluster.id)
                cluster_members = [{"token_history": []} for _ in members if _ != wallet.wallet_address]
            trades = _wallet_events_to_trades(events)
            last_active_days_ago = max(0.0, (now - events[0].event_time).total_seconds() / 86400.0)
            scores = wallet_quality.score_wallet(
                wallet.wallet_address,
                trades,
                cluster_members,
                last_active_days_ago,
            )
            await wallet_repo.save_wallet_score(db, wallet.wallet_address, scores)
            quality = scores["wallet_quality"]
            if quality < settings.wallet_degraded_quality_threshold:
                wallet.lifecycle = "RETIRED"
                wallet.is_active = False
                retired_count += 1
            elif quality < settings.wallet_active_quality_threshold:
                wallet.lifecycle = "DEGRADED"
                degraded_count += 1
            else:
                wallet.lifecycle = "ACTIVE"
                wallet.is_active = True
                active_count += 1
            updated += 1
        await db.commit()
        metrics.set_gauge("wallet_lifecycle_active", active_count)
        metrics.set_gauge("wallet_lifecycle_degraded", degraded_count)
        metrics.set_gauge("wallet_lifecycle_retired", retired_count)
        metrics.incr("wallet_scores_updated", updated)
        log.info(
            "Updated wallet scores | updated=%d active=%d degraded=%d retired=%d",
            updated,
            active_count,
            degraded_count,
            retired_count,
        )


async def rebuild_wallet_clusters() -> None:
    """Rebuild wallet clusters from co-purchase behavior."""
    async with AsyncSessionLocal() as db:
        copurchase_pairs = await graph_repo.get_copurchase_pairs(db, min_shared_tokens=2)
        wallets = await wallet_repo.list_active_wallets(db)
        wallet_events: list[dict[str, Any]] = []
        funding_sources: dict[str, str] = {}
        for wallet in wallets:
            funding_sources[wallet.wallet_address] = wallet.source
            events = await wallet_repo.get_recent_wallet_events(db, wallet.wallet_address, limit=200)
            for event in events:
                wallet_events.append(
                    {
                        "wallet_address": event.wallet_address,
                        "token_mint": event.token_mint,
                        "event_type": event.event_type,
                        "event_time": event.event_time,
                    }
                )
        clusters = clustering.build_clusters(copurchase_pairs, wallet_events, funding_sources)
        await db.execute(delete(WalletClusterMember))
        await db.execute(delete(WalletCluster))
        for cluster_data in clusters:
            await graph_repo.save_cluster(
                db,
                cluster_data["cluster_type"],
                cluster_data["members"],
                cluster_data["suspicion_score"] / 100.0,
            )
        await db.commit()
        log.info("Rebuilt %d wallet clusters", len(clusters))


async def retrain_wallet_quality_weights() -> None:
    """Monthly retrain hook for wallet-quality weighting."""
    async with AsyncSessionLocal() as db:
        weights = await retrain_weights_algo(db)
        log.info("Retrained wallet quality weights: %s", weights)


async def run_backtest() -> None:
    """Weekly backtest summary over recent labeled outcomes."""
    async with AsyncSessionLocal() as db:
        outcomes = await alert_repo.list_recent_completed_outcomes(db, limit=500)
        positive = {"HEAVY_HITTER", "TRADEABLE_RUNNER", "SURVIVOR"}
        total = len(outcomes)
        wins = sum(1 for outcome in outcomes if outcome.label in positive)
        hit_rate = (wins / total) if total else 0.0
        log.info("Backtest summary | total=%d wins=%d hit_rate=%.3f", total, wins, hit_rate)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(refresh_open_candidate_scores, "interval", minutes=5, id="refresh_candidates", max_instances=1, coalesce=True)
    scheduler.add_job(label_alert_outcomes, "interval", minutes=15, id="label_outcomes", max_instances=1, coalesce=True)
    scheduler.add_job(update_wallet_posteriors, "interval", hours=6, id="update_posteriors", max_instances=1, coalesce=True)
    scheduler.add_job(update_wallet_scores, "interval", hours=6, id="update_wallet_scores", max_instances=1, coalesce=True)
    scheduler.add_job(discover_new_wallets, "interval", hours=24, id="discover_new_wallets", max_instances=1, coalesce=True)
    scheduler.add_job(rebuild_wallet_clusters, "interval", hours=24, id="rebuild_clusters", max_instances=1, coalesce=True)
    scheduler.add_job(retrain_wallet_quality_weights, "cron", day=1, hour=0, minute=0, id="retrain_wallet_quality_weights", max_instances=1, coalesce=True)
    scheduler.add_job(run_backtest, "cron", day_of_week="sun", hour=1, minute=0, id="run_backtest", max_instances=1, coalesce=True)
    return scheduler


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("Starting WIGS worker process")
    scheduler = build_scheduler()
    scheduler.start()
    loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    run()
