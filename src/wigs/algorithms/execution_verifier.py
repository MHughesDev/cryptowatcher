"""Execution realism helpers around Jupiter sellability."""

from __future__ import annotations

from wigs.clients import jupiter
from wigs.config import get_settings

settings = get_settings()


async def check_sellability(token_mint: str) -> jupiter.SellabilityReport:
    """Returns Jupiter-based sellability report, failing closed if needed."""
    try:
        return await jupiter.estimate_sellability(token_mint)
    except Exception:
        return jupiter.SellabilityReport(
            route_exists=False,
            price_impact_025_sol=None,
            price_impact_1_sol=None,
            price_impact_5_sol=None,
            all_quotes_succeeded=False,
        )


def score_execution(
    report: jupiter.SellabilityReport,
    max_impact_1sol: float = 0.15,
) -> int:
    if not report.route_exists:
        return 0
    impact_1 = report.price_impact_1_sol if report.price_impact_1_sol is not None else 1.0
    impact_5 = report.price_impact_5_sol if report.price_impact_5_sol is not None else 1.0
    if impact_1 < max_impact_1sol and impact_5 < settings.max_price_impact_5_sol:
        return 100
    if impact_1 < (max_impact_1sol * 2.0) and impact_5 < (settings.max_price_impact_5_sol * 2.0):
        return 60
    return 0
