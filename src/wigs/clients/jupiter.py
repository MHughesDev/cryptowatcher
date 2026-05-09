"""Jupiter Quote API client — execution realism and sellability checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
LAMPORTS_PER_SOL = 1_000_000_000

BASE_URL = "https://quote-api.jup.ag/v6"


@dataclass
class QuoteResult:
    input_mint: str
    output_mint: str
    in_amount: int
    out_amount: int
    price_impact_pct: float
    route_plan: list[Any]
    success: bool
    error: str | None = None


@dataclass
class SellabilityReport:
    route_exists: bool
    price_impact_025_sol: float | None
    price_impact_1_sol: float | None
    price_impact_5_sol: float | None
    all_quotes_succeeded: bool

    @property
    def execution_score(self) -> int:
        if not self.route_exists:
            return 0
        impacts = [i for i in [self.price_impact_025_sol, self.price_impact_1_sol] if i is not None]
        if not impacts:
            return 50
        avg_impact = sum(impacts) / len(impacts)
        if avg_impact > 0.30:
            return 10
        if avg_impact > 0.15:
            return 40
        if avg_impact > 0.05:
            return 70
        return 100


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
async def quote(
    input_mint: str,
    output_mint: str,
    amount_lamports: int,
    slippage_bps: int = 500,
    *,
    client: httpx.AsyncClient | None = None,
) -> QuoteResult:
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount_lamports,
        "slippageBps": slippage_bps,
    }
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        try:
            resp = await c.get(f"{BASE_URL}/quote", params=params)
            if resp.status_code == 400:
                return QuoteResult(
                    input_mint=input_mint, output_mint=output_mint,
                    in_amount=amount_lamports, out_amount=0,
                    price_impact_pct=1.0, route_plan=[],
                    success=False, error=resp.text,
                )
            resp.raise_for_status()
            data = resp.json()
            return QuoteResult(
                input_mint=input_mint,
                output_mint=output_mint,
                in_amount=int(data["inAmount"]),
                out_amount=int(data["outAmount"]),
                price_impact_pct=float(data.get("priceImpactPct", 0)),
                route_plan=data.get("routePlan", []),
                success=True,
            )
        except Exception as e:
            return QuoteResult(
                input_mint=input_mint, output_mint=output_mint,
                in_amount=amount_lamports, out_amount=0,
                price_impact_pct=1.0, route_plan=[],
                success=False, error=str(e),
            )


async def estimate_sellability(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> SellabilityReport:
    """Simulate selling the token at 0.25, 1, and 5 SOL equivalent sizes."""
    sizes = [
        int(0.25 * LAMPORTS_PER_SOL),
        int(1.0 * LAMPORTS_PER_SOL),
        int(5.0 * LAMPORTS_PER_SOL),
    ]
    results = []
    for amount in sizes:
        q = await quote(token_mint, SOL_MINT, amount, client=client)
        results.append(q)

    q025, q1, q5 = results
    return SellabilityReport(
        route_exists=q025.success or q1.success,
        price_impact_025_sol=q025.price_impact_pct if q025.success else None,
        price_impact_1_sol=q1.price_impact_pct if q1.success else None,
        price_impact_5_sol=q5.price_impact_pct if q5.success else None,
        all_quotes_succeeded=all(r.success for r in results),
    )
