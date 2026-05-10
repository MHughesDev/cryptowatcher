"""Alert publisher — formats and sends scored candidates to Telegram / Discord / log."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from wigs.clients import discord, telegram
from wigs.config import get_settings
from wigs.models import CandidateToken, TokenScore
from wigs.repositories import alert_repo

log = logging.getLogger(__name__)
settings = get_settings()

SOLSCAN_URL = "https://solscan.io/token"
DEXSCREENER_URL = "https://dexscreener.com/solana"

DECISION_EMOJI = {
    "STRONG_CANDIDATE": "🔥",
    "STRONG_WATCH":     "👀",
    "WATCH":            "📌",
    "AVOID":            "❌",
}

RISK_EMOJI = {
    "LOW":      "🟢",
    "MEDIUM":   "🟡",
    "HIGH":     "🔴",
    "CRITICAL": "⛔",
}


def format_alert_message(token: CandidateToken, score: TokenScore) -> str:
    name_str = f"{token.name} ({token.symbol})" if token.name and token.symbol else (token.name or token.symbol or "Unknown")
    decision_emoji = DECISION_EMOJI.get(score.decision, "")
    risk_emoji = RISK_EMOJI.get(score.risk_level, "")

    convergence_line = (
        f"  🤝 Wallets: {score.convergence_independent_count} independent"
    )
    if score.convergence_time_spread_s is not None:
        spread = int(score.convergence_time_spread_s)
        convergence_line += f" ({spread}s spread)"
    if score.threshold_adjustment > 0:
        convergence_line += f" [threshold -{score.threshold_adjustment}pt]"

    reasons = score.score_reasons or {}
    vetoes = reasons.get("vetoes", [])
    penalties = reasons.get("penalties", [])

    veto_str = "\n  ".join(vetoes) if vetoes else "None"
    penalty_str = ", ".join(penalties) if penalties else "None"

    lines = [
        f"{decision_emoji} <b>WIGS Alert — {score.decision}</b>",
        "",
        f"<b>{name_str}</b>",
        f"  Mint: <code>{token.token_mint}</code>",
        f"  Links: <a href='{SOLSCAN_URL}/{token.token_mint}'>Solscan</a>  |  <a href='{DEXSCREENER_URL}/{token.token_mint}'>DexScreener</a>",
        "",
        f"<b>Score: {score.total_score}/100</b>  {risk_emoji} Risk: {score.risk_level}",
        f"  Wallet:     {score.wallet_score}",
        f"  Market:     {score.market_score}",
        f"  Risk:       {score.risk_score}",
        f"  Social:     {score.social_score}",
        f"  History:    {score.history_score}",
        f"  Execution:  {score.execution_score}",
        "",
        convergence_line,
        "",
        f"  Vetoes:   {veto_str}",
        f"  Penalties: {penalty_str}",
        "",
        f"<i>Detected: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>",
    ]
    return "\n".join(lines)


async def publish_alert(
    token: CandidateToken,
    score: TokenScore,
    db: AsyncSession,
) -> None:
    """Format and send an alert to all configured channels. Log is always written."""
    message = format_alert_message(token, score)

    # Log first — always
    log.info("ALERT %s | %s | score=%d | wallets=%d",
             score.decision, token.token_mint, score.total_score,
             score.convergence_independent_count)

    channels_sent: list[str] = []

    if settings.enable_telegram_alerts and settings.telegram_bot_token:
        ok = await telegram.send_message(message)
        channels_sent.append("TELEGRAM" if ok else "TELEGRAM_FAILED")

    if settings.enable_discord_alerts and settings.discord_alert_webhook_url:
        # Discord doesn't support HTML — strip tags
        plain = (message
                 .replace("<b>", "**").replace("</b>", "**")
                 .replace("<i>", "_").replace("</i>", "_")
                 .replace("<code>", "`").replace("</code>", "`")
                 .replace("<a href='", "").replace("'>", " ").replace("</a>", ""))
        ok = await discord.send_webhook(plain)
        channels_sent.append("DISCORD" if ok else "DISCORD_FAILED")

    # Persist one alert row per channel
    for channel_str in channels_sent or ["LOG"]:
        channel = channel_str.split("_")[0]  # strip _FAILED suffix for enum
        status = "SENT" if "FAILED" not in channel_str else "FAILED"
        await alert_repo.save_alert(
            db,
            token_mint=token.token_mint,
            score_id=score.id,
            channel=channel,
            decision=score.decision,
            message=message,
            status=status,
        )
