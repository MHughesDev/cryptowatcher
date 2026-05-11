from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Helius ────────────────────────────────────────────────────────────────
    helius_api_key: str = ""
    helius_rpc_url: str = "https://mainnet.helius-rpc.com"
    helius_webhook_secret: str = ""

    # ── Solana ────────────────────────────────────────────────────────────────
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"

    # ── Market APIs ───────────────────────────────────────────────────────────
    birdeye_api_key: str = ""
    bitquery_api_key: str = ""

    # ── Social APIs ───────────────────────────────────────────────────────────
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "wigs/0.1"

    telegram_bot_token: str = ""
    telegram_alert_chat_id: str = ""

    discord_alert_webhook_url: str = ""
    slack_alert_webhook_url: str = ""

    youtube_api_key: str = ""

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://wigs:wigs@localhost:5432/wigs"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Scoring thresholds ────────────────────────────────────────────────────
    min_liquidity_usd: float = 5_000.0
    max_price_impact_1_sol: float = 0.15
    max_price_impact_5_sol: float = 0.40
    max_gini_coefficient: float = 0.90
    max_hhi: float = 0.25
    max_top_10_holder_pct: float = 0.60

    score_watch_threshold: int = 45
    score_strong_watch_threshold: int = 60
    score_strong_candidate_threshold: int = 75

    # ── Convergence ───────────────────────────────────────────────────────────
    convergence_recency_lambda: float = 0.05
    convergence_forced_upgrade_min_wallets: int = 3
    convergence_forced_upgrade_max_spread_seconds: int = 600

    # ── Wallet scoring ────────────────────────────────────────────────────────
    wallet_freshness_lambda: float = 0.1
    wallet_active_quality_threshold: int = 50
    wallet_degraded_quality_threshold: int = 25

    # ── Feature flags ─────────────────────────────────────────────────────────
    enable_telegram_alerts: bool = True
    enable_discord_alerts: bool = True
    enable_slack_alerts: bool = False
    slack_min_convergence_wallets: int = 2
    enable_social_scoring: bool = True
    enable_gdelt: bool = True
    enable_youtube: bool = True
    enable_posterior_trust_weighting: bool = False
    enable_posterior_trust_shadow_logging: bool = True
    posterior_trust_min_multiplier: float = 0.7
    posterior_trust_max_multiplier: float = 1.3
    kol_precall_min_hits: int = 2
    kol_precall_min_lead_seconds: int = 60
    kol_precall_max_lead_seconds: int = 21600
    kol_precall_wallet_blocklist: list[str] = Field(default_factory=list)

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def decision_thresholds(self) -> dict[str, int]:
        return {
            "WATCH": self.score_watch_threshold,
            "STRONG_WATCH": self.score_strong_watch_threshold,
            "STRONG_CANDIDATE": self.score_strong_candidate_threshold,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
