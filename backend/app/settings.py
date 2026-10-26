"""Validated environment, with fail-closed production defaults."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    redis_url: str
    qdrant_url: str
    origins: tuple[str, ...]
    gateway_secret: str
    admin_key: str

    def validate(self):
        if self.env not in {"dev", "test", "prod"}:
            raise ValueError("APP_ENV must be dev/test/prod")
        if self.env == "prod":
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL")
            if not self.redis_url:
                raise ValueError("Production requires Redis")
            if "*" in self.origins:
                raise ValueError("Wildcard CORS forbidden in production")
        import json

        prices = json.loads(os.getenv("MODEL_PRICES_JSON", "{}"))
        if not isinstance(prices, dict):
            raise ValueError("MODEL_PRICES_JSON must be an object")
        for model, price in prices.items():
            if not isinstance(price, dict) or any(
                not isinstance(price.get(k), (int, float)) or price[k] < 0
                for k in ["input", "output"]
            ):
                raise ValueError(
                    "Each model tariff requires non-negative input/output prices"
                )
        for key in [
            "MODEL_CONCURRENCY",
            "MODEL_DAILY_TOKEN_BUDGET",
            "MODEL_DAILY_CALL_LIMIT",
            "MAX_QUEUE_SIZE",
            "REQUESTS_PER_MINUTE",
        ]:
            if int(os.getenv(key, "1")) < 1:
                raise ValueError(key + " must be positive")
        return self


def settings():
    legacy = os.getenv("INSIGHT_DB_PATH")
    default = "sqlite:///" + (
        legacy
        or str(
            Path(
                os.getenv(
                    "STORAGE_DIR",
                    "/app/storage" if Path("/app/storage").exists() else "backend/data",
                )
            )
            / "application.db"
        )
    )
    return Settings(
        os.getenv("APP_ENV", "dev"),
        os.getenv("DATABASE_URL", default),
        os.getenv("REDIS_URL", ""),
        os.getenv("QDRANT_URL", ""),
        tuple(
            x.strip()
            for x in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:8080"
            ).split(",")
            if x.strip()
        ),
        os.getenv("GATEWAY_SIGNING_SECRET", ""),
        os.getenv("ADMIN_API_KEY", ""),
    ).validate()
