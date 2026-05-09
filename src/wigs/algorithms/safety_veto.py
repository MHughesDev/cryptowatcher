"""Safety veto engine — hard and soft risk evaluation.

Hard vetoes override score entirely. Soft penalties reduce risk_score.
Dempster-Shafer combination catches multi-partial-signal risk cases
that would slip through individual threshold checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from wigs.config import get_settings

settings = get_settings()


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ConcentrationReport:
    gini: float
    hhi: float
    top_10_pct: float
    top_20_pct: float
    holder_count: int


@dataclass
class RiskReport:
    vetoes: list[str] = field(default_factory=list)
    penalties: list[tuple[str, int]] = field(default_factory=list)
    risk_score: int = 100
    gini: float | None = None
    hhi: float | None = None
    top_10_pct: float | None = None
    ds_risky_belief: float = 0.0

    def has_hard_veto(self) -> bool:
        return bool(self.vetoes)

    def penalty_total(self) -> int:
        return sum(pts for _, pts in self.penalties)


# ── Concentration metrics ─────────────────────────────────────────────────────

def compute_holder_concentration(holders: list[dict[str, Any]], total_supply: float) -> ConcentrationReport:
    """
    holders: list of {amount: float} dicts from getTokenLargestAccounts.
    total_supply: from getTokenSupply.
    """
    if not holders or total_supply <= 0:
        return ConcentrationReport(gini=1.0, hhi=1.0, top_10_pct=1.0, top_20_pct=1.0, holder_count=0)

    balances = sorted(
        [float(h.get("amount", 0)) / total_supply for h in holders],
        reverse=True,
    )
    n = len(balances)

    # Gini coefficient
    sorted_asc = sorted(balances)
    gini_num = sum((i + 1) * b for i, b in enumerate(sorted_asc))
    gini = (2 * gini_num) / (n * sum(sorted_asc)) - (n + 1) / n if sum(sorted_asc) > 0 else 1.0

    # Herfindahl-Hirschman Index
    hhi = sum(b ** 2 for b in balances)

    top_10_pct = sum(balances[:10])
    top_20_pct = sum(balances[:20])

    return ConcentrationReport(
        gini=round(gini, 4),
        hhi=round(hhi, 4),
        top_10_pct=round(top_10_pct, 4),
        top_20_pct=round(top_20_pct, 4),
        holder_count=n,
    )


# ── Dempster-Shafer evidence combination ─────────────────────────────────────

def _ds_combine(bpas: list[dict[str, float]]) -> dict[str, float]:
    """
    Combine a list of basic probability assignments using Dempster's rule.
    Each BPA is a dict with keys from {"SAFE", "RISKY", "UNCERTAIN"}.
    Returns the combined belief distribution.
    """
    if not bpas:
        return {"SAFE": 0.5, "RISKY": 0.0, "UNCERTAIN": 0.5}

    combined = bpas[0].copy()

    for bpa in bpas[1:]:
        new_combined: dict[str, float] = {}
        conflict = 0.0

        # Enumerate all intersections
        for a_key, a_val in combined.items():
            for b_key, b_val in bpa.items():
                # Intersection of singletons
                if a_key == b_key or "UNCERTAIN" in (a_key, b_key):
                    result_key = a_key if b_key == "UNCERTAIN" else b_key
                    new_combined[result_key] = new_combined.get(result_key, 0.0) + a_val * b_val
                else:
                    conflict += a_val * b_val  # empty set → conflict

        # Normalize by (1 - K)
        denom = 1.0 - conflict
        if denom <= 0:
            # Total conflict — default to uncertain
            combined = {"SAFE": 0.0, "RISKY": 0.5, "UNCERTAIN": 0.5}
        else:
            combined = {k: v / denom for k, v in new_combined.items()}

    return combined


def _bpa_from_concentration(report: ConcentrationReport) -> dict[str, float]:
    risky = 0.0
    if report.gini > 0.90:
        risky += 0.5
    if report.hhi > 0.25:
        risky += 0.3
    if report.top_10_pct > 0.60:
        risky += 0.2
    risky = min(1.0, risky)
    return {"RISKY": risky, "SAFE": max(0.0, 0.8 - risky), "UNCERTAIN": min(0.2, 1.0 - risky)}


def _bpa_from_liquidity(liquidity_usd: float) -> dict[str, float]:
    if liquidity_usd < settings.min_liquidity_usd:
        return {"RISKY": 0.8, "SAFE": 0.0, "UNCERTAIN": 0.2}
    if liquidity_usd < settings.min_liquidity_usd * 3:
        return {"RISKY": 0.3, "SAFE": 0.4, "UNCERTAIN": 0.3}
    return {"RISKY": 0.0, "SAFE": 0.8, "UNCERTAIN": 0.2}


def _bpa_from_authority(mint_active: bool | None, freeze_active: bool | None) -> dict[str, float]:
    risk = 0.0
    if mint_active:
        risk += 0.6
    if freeze_active:
        risk += 0.4
    risk = min(1.0, risk)
    return {"RISKY": risk, "SAFE": max(0.0, 1.0 - risk - 0.1), "UNCERTAIN": 0.1}


# ── Main evaluation ───────────────────────────────────────────────────────────

def evaluate(
    *,
    liquidity_usd: float,
    mint_authority_active: bool | None,
    freeze_authority_active: bool | None,
    concentration: ConcentrationReport,
    sell_quote_exists: bool,
    price_impact_1_sol: float | None,
    price_impact_5_sol: float | None,
    pool_age_minutes: float | None,
    volume_authenticity_ratio: float | None,
    has_social_data: bool,
    independent_buyer_count: int,
    cluster_is_independent: bool,
    kol_already_called: bool,
    dev_dump_detected: bool,
    copycat_mint: bool,
    social_drainer_link: bool,
) -> RiskReport:
    vetoes: list[str] = []
    penalties: list[tuple[str, int]] = []

    # ── Hard vetoes ────────────────────────────────────────────────────────
    if not sell_quote_exists:
        vetoes.append("NO_SELL_ROUTE")

    if liquidity_usd < settings.min_liquidity_usd:
        vetoes.append("LIQUIDITY_TOO_LOW")

    if price_impact_1_sol is not None and price_impact_1_sol > settings.max_price_impact_1_sol:
        vetoes.append("PRICE_IMPACT_TOO_HIGH")
    elif price_impact_5_sol is not None and price_impact_5_sol > settings.max_price_impact_5_sol:
        vetoes.append("PRICE_IMPACT_TOO_HIGH")

    if mint_authority_active:
        vetoes.append("ACTIVE_MINT_AUTHORITY")

    if freeze_authority_active:
        vetoes.append("ACTIVE_FREEZE_AUTHORITY")

    if (
        concentration.gini > settings.max_gini_coefficient
        or concentration.top_10_pct > settings.max_top_10_holder_pct
    ):
        vetoes.append("TOP_HOLDER_TOO_CONCENTRATED")

    if dev_dump_detected:
        vetoes.append("DEV_DUMP_DETECTED")

    if copycat_mint:
        vetoes.append("COPYCAT_MINT")

    if social_drainer_link:
        vetoes.append("SOCIAL_DRAINER_LINK")

    # ── Soft penalties ─────────────────────────────────────────────────────
    if pool_age_minutes is not None and pool_age_minutes < 10:
        penalties.append(("POOL_TOO_NEW", 15))

    if volume_authenticity_ratio is not None and volume_authenticity_ratio < 0.2:
        penalties.append(("VOLUME_TOO_BOTLIKE", 20))

    if not has_social_data:
        penalties.append(("SOCIAL_TOO_THIN", 10))

    if independent_buyer_count == 1:
        penalties.append(("SINGLE_WALLET_SIGNAL", 10))

    if not cluster_is_independent:
        penalties.append(("CLUSTER_NOT_INDEPENDENT", 20))

    if kol_already_called:
        penalties.append(("KOL_ALREADY_CALLED", 15))

    # ── Dempster-Shafer combination for partial signals ────────────────────
    bpas = [
        _bpa_from_concentration(concentration),
        _bpa_from_liquidity(liquidity_usd),
        _bpa_from_authority(mint_authority_active, freeze_authority_active),
    ]
    ds_result = _ds_combine(bpas)
    ds_risky = ds_result.get("RISKY", 0.0)

    if ds_risky > 0.85 and not vetoes:
        vetoes.append("DS_COMBINED_RISK")
    elif ds_risky > 0.60:
        penalties.append(("DS_PARTIAL_RISK", 20))

    # ── Compute final risk score ───────────────────────────────────────────
    if vetoes:
        risk_score = 0
    else:
        risk_score = max(0, 100 - sum(pts for _, pts in penalties))

    return RiskReport(
        vetoes=vetoes,
        penalties=penalties,
        risk_score=risk_score,
        gini=concentration.gini,
        hhi=concentration.hhi,
        top_10_pct=concentration.top_10_pct,
        ds_risky_belief=ds_risky,
    )
