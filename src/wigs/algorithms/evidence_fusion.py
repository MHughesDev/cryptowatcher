"""Evidence fusion scorer — combines all sub-scores into a final decision.

Applies:
  1. Component-weighted total_score formula
  2. Convergence threshold adjustment (lowers thresholds for multi-wallet events)
  3. Forced STRONG_WATCH override for rapid convergence
  4. Hard veto override forces AVOID
"""

from __future__ import annotations

from dataclasses import dataclass

from wigs.algorithms.convergence import ConvergenceResult
from wigs.algorithms.safety_veto import RiskReport
from wigs.algorithms.social_verifier import SocialScore
from wigs.config import get_settings

settings = get_settings()


@dataclass
class TokenScoreResult:
    total_score: int
    decision: str                   # AVOID / WATCH / STRONG_WATCH / STRONG_CANDIDATE
    wallet_score: int
    market_score: int
    risk_score: int
    social_score: int
    history_score: int
    execution_score: int
    convergence_independent_count: int
    convergence_time_spread_s: float
    threshold_adjustment: int
    score_reasons: dict[str, object]
    risk_level: str                 # LOW / MEDIUM / HIGH / CRITICAL


def _classify_decision(total: int, threshold_adjustment: int) -> str:
    watch = settings.score_watch_threshold - threshold_adjustment
    strong_watch = settings.score_strong_watch_threshold - threshold_adjustment
    strong_candidate = settings.score_strong_candidate_threshold - threshold_adjustment

    if total >= strong_candidate:
        return "STRONG_CANDIDATE"
    if total >= strong_watch:
        return "STRONG_WATCH"
    if total >= watch:
        return "WATCH"
    return "AVOID"


def _risk_level(risk_score: int, vetoes: list[str]) -> str:
    if vetoes:
        return "CRITICAL"
    if risk_score < 40:
        return "HIGH"
    if risk_score < 70:
        return "MEDIUM"
    return "LOW"


def compute_final_score(
    *,
    wallet_score: int,
    market_score: int,
    risk_report: RiskReport,
    social_score: SocialScore,
    history_score: int,
    execution_score: int,
    convergence: ConvergenceResult,
) -> TokenScoreResult:
    # Hard veto override
    if risk_report.has_hard_veto():
        return TokenScoreResult(
            total_score=0,
            decision="AVOID",
            wallet_score=wallet_score,
            market_score=market_score,
            risk_score=0,
            social_score=social_score.value,
            history_score=history_score,
            execution_score=execution_score,
            convergence_independent_count=convergence.independent_buyer_count,
            convergence_time_spread_s=convergence.time_spread_seconds,
            threshold_adjustment=0,
            score_reasons={"vetoes": risk_report.vetoes, "penalties": risk_report.penalties},
            risk_level="CRITICAL",
        )

    total = int(
        0.35 * wallet_score
        + 0.20 * market_score
        + 0.20 * risk_report.risk_score
        + 0.15 * social_score.value
        + 0.07 * history_score
        + 0.03 * execution_score
    )
    total = min(100, max(0, total))

    adj = convergence.threshold_adjustment
    decision = _classify_decision(total, adj)

    # Convergence forced upgrade: 3+ independent wallets within 10 min → minimum STRONG_WATCH
    if convergence.qualifies_for_forced_strong_watch:
        if decision == "WATCH":
            decision = "STRONG_WATCH"
        elif decision == "AVOID" and risk_report.risk_score > 0:
            decision = "WATCH"  # partial upgrade even from AVOID if no hard veto

    return TokenScoreResult(
        total_score=total,
        decision=decision,
        wallet_score=wallet_score,
        market_score=market_score,
        risk_score=risk_report.risk_score,
        social_score=social_score.value,
        history_score=history_score,
        execution_score=execution_score,
        convergence_independent_count=convergence.independent_buyer_count,
        convergence_time_spread_s=convergence.time_spread_seconds,
        threshold_adjustment=adj,
        score_reasons={
            "vetoes": risk_report.vetoes,
            "penalties": [p[0] for p in risk_report.penalties],
            "gini": risk_report.gini,
            "hhi": risk_report.hhi,
            "ds_risky_belief": risk_report.ds_risky_belief,
            "narrative_type": social_score.narrative_type,
            "convergence_forced_upgrade": convergence.qualifies_for_forced_strong_watch,
        },
        risk_level=_risk_level(risk_report.risk_score, risk_report.vetoes),
    )
