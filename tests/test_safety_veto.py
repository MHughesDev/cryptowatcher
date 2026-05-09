"""Tests for safety veto engine — hard vetoes, soft penalties, DS combination."""

from wigs.algorithms.safety_veto import ConcentrationReport, compute_holder_concentration, evaluate


def _safe_concentration() -> ConcentrationReport:
    return ConcentrationReport(gini=0.65, hhi=0.05, top_10_pct=0.30, top_20_pct=0.45, holder_count=500)


def test_no_sell_route_triggers_hard_veto():
    report = evaluate(
        liquidity_usd=50_000,
        mint_authority_active=False,
        freeze_authority_active=False,
        concentration=_safe_concentration(),
        sell_quote_exists=False,       # ← triggers veto
        price_impact_1_sol=0.01,
        price_impact_5_sol=0.05,
        pool_age_minutes=60,
        volume_authenticity_ratio=0.5,
        has_social_data=True,
        independent_buyer_count=3,
        cluster_is_independent=True,
        kol_already_called=False,
        dev_dump_detected=False,
        copycat_mint=False,
        social_drainer_link=False,
    )
    assert report.has_hard_veto()
    assert "NO_SELL_ROUTE" in report.vetoes
    assert report.risk_score == 0


def test_mint_authority_triggers_hard_veto():
    report = evaluate(
        liquidity_usd=100_000,
        mint_authority_active=True,    # ← triggers veto
        freeze_authority_active=False,
        concentration=_safe_concentration(),
        sell_quote_exists=True,
        price_impact_1_sol=0.02,
        price_impact_5_sol=0.10,
        pool_age_minutes=120,
        volume_authenticity_ratio=0.6,
        has_social_data=True,
        independent_buyer_count=2,
        cluster_is_independent=True,
        kol_already_called=False,
        dev_dump_detected=False,
        copycat_mint=False,
        social_drainer_link=False,
    )
    assert "ACTIVE_MINT_AUTHORITY" in report.vetoes
    assert report.risk_score == 0


def test_clean_token_no_veto():
    report = evaluate(
        liquidity_usd=100_000,
        mint_authority_active=False,
        freeze_authority_active=False,
        concentration=_safe_concentration(),
        sell_quote_exists=True,
        price_impact_1_sol=0.02,
        price_impact_5_sol=0.10,
        pool_age_minutes=120,
        volume_authenticity_ratio=0.6,
        has_social_data=True,
        independent_buyer_count=3,
        cluster_is_independent=True,
        kol_already_called=False,
        dev_dump_detected=False,
        copycat_mint=False,
        social_drainer_link=False,
    )
    assert not report.has_hard_veto()
    assert report.risk_score == 100


def test_gini_concentration_check():
    holders = [{"amount": str(i * 100_000)} for i in range(10, 0, -1)]
    total = sum(i * 100_000 for i in range(1, 11))
    report = compute_holder_concentration(holders, float(total))
    assert 0.0 <= report.gini <= 1.0
    assert 0.0 <= report.hhi <= 1.0
    assert 0.0 <= report.top_10_pct <= 1.0


def test_soft_penalty_single_wallet():
    report = evaluate(
        liquidity_usd=50_000,
        mint_authority_active=False,
        freeze_authority_active=False,
        concentration=_safe_concentration(),
        sell_quote_exists=True,
        price_impact_1_sol=0.05,
        price_impact_5_sol=0.15,
        pool_age_minutes=60,
        volume_authenticity_ratio=0.5,
        has_social_data=True,
        independent_buyer_count=1,    # ← single wallet penalty
        cluster_is_independent=True,
        kol_already_called=False,
        dev_dump_detected=False,
        copycat_mint=False,
        social_drainer_link=False,
    )
    assert not report.has_hard_veto()
    assert any(p[0] == "SINGLE_WALLET_SIGNAL" for p in report.penalties)
    assert report.risk_score < 100
