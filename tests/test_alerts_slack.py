import asyncio
from types import SimpleNamespace

from wigs import alerts


class DummyDB:
    pass


def _token():
    return SimpleNamespace(token_mint="mint1", name="T", symbol="TK")


def _score(wallets: int):
    return SimpleNamespace(
        id="score1",
        decision="WATCH",
        total_score=50,
        convergence_independent_count=wallets,
        convergence_time_spread_s=30,
        threshold_adjustment=0,
        risk_level="LOW",
        wallet_score=50,
        market_score=50,
        risk_score=50,
        social_score=50,
        history_score=50,
        execution_score=50,
        score_reasons={},
    )


def test_slack_sent_when_wallet_gate_met(monkeypatch):
    sent = []

    async def fake_save_alert(db, **kwargs):
        sent.append(kwargs)

    async def ok(*args, **kwargs):
        return True

    monkeypatch.setattr(alerts.alert_repo, "save_alert", fake_save_alert)
    monkeypatch.setattr(alerts.telegram, "send_message", ok)
    monkeypatch.setattr(alerts.discord, "send_webhook", ok)
    monkeypatch.setattr(alerts.slack, "send_webhook", ok)

    monkeypatch.setattr(alerts.settings, "enable_telegram_alerts", False)
    monkeypatch.setattr(alerts.settings, "enable_discord_alerts", False)
    monkeypatch.setattr(alerts.settings, "enable_slack_alerts", True)
    monkeypatch.setattr(alerts.settings, "slack_alert_webhook_url", "https://hooks.slack.test")
    monkeypatch.setattr(alerts.settings, "slack_min_convergence_wallets", 2)

    asyncio.run(alerts.publish_alert(_token(), _score(2), DummyDB()))

    assert len(sent) == 1
    assert sent[0]["channel"] == "SLACK"
    assert sent[0]["status"] == "SENT"


def test_slack_skipped_below_wallet_gate(monkeypatch):
    sent = []

    async def fake_save_alert(db, **kwargs):
        sent.append(kwargs)

    async def ok(*args, **kwargs):
        return True

    monkeypatch.setattr(alerts.alert_repo, "save_alert", fake_save_alert)
    monkeypatch.setattr(alerts.slack, "send_webhook", ok)

    monkeypatch.setattr(alerts.settings, "enable_telegram_alerts", False)
    monkeypatch.setattr(alerts.settings, "enable_discord_alerts", False)
    monkeypatch.setattr(alerts.settings, "enable_slack_alerts", True)
    monkeypatch.setattr(alerts.settings, "slack_alert_webhook_url", "https://hooks.slack.test")
    monkeypatch.setattr(alerts.settings, "slack_min_convergence_wallets", 2)

    asyncio.run(alerts.publish_alert(_token(), _score(1), DummyDB()))

    assert len(sent) == 1
    assert sent[0]["channel"] == "LOG"
    assert sent[0]["status"] == "SENT"
