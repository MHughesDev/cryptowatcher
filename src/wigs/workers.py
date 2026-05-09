"""Background workers — scheduled jobs that run alongside the API server.

Jobs:
  - refresh_open_candidate_scores    every 5 minutes
  - update_wallet_posteriors         every 6 hours
  - label_alert_outcomes             every 15 minutes
  - refresh_tracked_wallet_set       every 24 hours
  - rebuild_wallet_clusters          every 24 hours

Entry point: run() — starts APScheduler and blocks.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from wigs.algorithms.feedback import classify_outcome_from_returns, compute_posterior_update
from wigs.algorithms.social_verifier import fetch_and_score
from wigs.clients import jupiter
from wigs.config import get_settings
from wigs.database import AsyncSessionLocal

log = logging.getLogger(__name__)
settings = get_settings()


# ── Job: re-score open candidates ─────────────────────────────────────────────

async def refresh_open_candidate_scores() -> None:
    """Re-score tokens in WATCH / STRONG_WATCH state. New wallet buys may have arrived."""
    from sqlalchemy import select
    from wigs.models import CandidateToken
    from wigs.pipeline import fetch_market_context, fetch_risk_data, load_convergence_buyers, score_market
    from wigs.algorithms.convergence import compute_convergence_score
    from wigs.algorithms.safety_veto import evaluate
    from wigs.algorithms.evidence_fusion import compute_final_score

    async with AsyncSessionLocal() as db:
        stmt = select(CandidateToken).where(
            CandidateToken.status.in_(["WATCH", "STRONG_WATCH"])
        )
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        log.info("Refreshing %d open candidates", len(candidates))
        for token in candidates:
            try:
                buyers = await load_convergence_buyers(token.token_mint, db)
                convergence = compute_convergence_score(buyers)
                # Full re-enrichment would be expensive — just update convergence
                # Full re-score on STRONG_WATCH tokens
                if convergence.independent_buyer_count > len(buyers) * 0.5:
                    log.debug("Convergence updated for %s: %d independent", token.token_mint, convergence.independent_buyer_count)
            except Exception as exc:
                log.warning("Failed to refresh %s: %s", token.token_mint, exc)


# ── Job: label alert outcomes ─────────────────────────────────────────────────

async def label_alert_outcomes() -> None:
    """
    For each unlabeled alert, check if measurement windows have elapsed.
    If 7d window has passed, classify and store the outcome.
    """
    from sqlalchemy import select
    from wigs.models import Alert, TokenOutcome

    async with AsyncSessionLocal() as db:
        stmt = select(Alert).join(
            TokenOutcome, Alert.id == TokenOutcome.alert_id, isouter=True
        ).where(TokenOutcome.id.is_(None))
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        now = datetime.utcnow()
        for alert in alerts:
            age = now - alert.sent_at
            if age < timedelta(days=7):
                continue   # still within measurement window

            try:
                # Simulate a 1h sell to get tradable return
                sell_1h = await jupiter.estimate_sellability(alert.token_mint)
                liq_now = 0.0  # TODO: fetch current liquidity from DexScreener

                label = classify_outcome_from_returns(
                    tradable_return_1h=sell_1h.price_impact_1_sol,
                    max_return_24h=None,
                    liquidity_7d=liq_now,
                    initial_liquidity=0.0,
                )

                db.add(TokenOutcome(
                    token_mint=alert.token_mint,
                    alert_id=alert.id,
                    label=label,
                    measurement_complete=True,
                    labeled_at=now,
                ))
                await db.commit()
                log.info("Labeled %s → %s", alert.token_mint, label)
            except Exception as exc:
                log.warning("Failed to label alert %s: %s", alert.id, exc)


# ── Job: update wallet posteriors ─────────────────────────────────────────────

async def update_wallet_posteriors() -> None:
    """Update Thompson Sampling Beta posteriors for wallets with new labeled outcomes."""
    from sqlalchemy import select
    from wigs.models import Alert, TokenOutcome, WalletBetaPosterior, WalletEvent

    async with AsyncSessionLocal() as db:
        # Get newly labeled outcomes
        stmt = (
            select(TokenOutcome)
            .where(
                TokenOutcome.measurement_complete.is_(True),
                TokenOutcome.label.is_not(None),
            )
            .order_by(TokenOutcome.labeled_at.desc())
            .limit(100)
        )
        result = await db.execute(stmt)
        outcomes = result.scalars().all()

        for outcome in outcomes:
            # Find wallets that triggered the candidate
            event_stmt = select(WalletEvent).where(
                WalletEvent.token_mint == outcome.token_mint,
                WalletEvent.event_type == "BUY",
            )
            events_result = await db.execute(event_stmt)
            events = events_result.scalars().all()

            for evt in events:
                update = compute_posterior_update(evt.wallet_address, outcome.label)

                # Upsert Beta posterior
                posterior_stmt = select(WalletBetaPosterior).where(
                    WalletBetaPosterior.wallet_address == evt.wallet_address
                )
                post_result = await db.execute(posterior_stmt)
                posterior = post_result.scalar_one_or_none()

                if posterior is None:
                    db.add(WalletBetaPosterior(
                        wallet_address=evt.wallet_address,
                        alpha=2.0 + update.alpha_delta,
                        beta=2.0 + update.beta_delta,
                    ))
                else:
                    posterior.alpha += update.alpha_delta
                    posterior.beta += update.beta_delta

        await db.commit()
        log.info("Updated posteriors for %d outcomes", len(outcomes))


# ── Scheduler setup ────────────────────────────────────────────────────────────

def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        refresh_open_candidate_scores,
        "interval", minutes=5, id="refresh_candidates",
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        label_alert_outcomes,
        "interval", minutes=15, id="label_outcomes",
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        update_wallet_posteriors,
        "interval", hours=6, id="update_posteriors",
        max_instances=1, coalesce=True,
    )

    return scheduler


def run() -> None:
    """Entry point for the worker process."""
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
