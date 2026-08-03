from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    database_path: str = getenv("DATABASE_PATH", "./data/billing.db")
    admin_api_key: str = getenv("ADMIN_API_KEY", "")
    demo_tenant_api_key: str = getenv("DEMO_TENANT_API_KEY", "")
    stripe_secret_key: str = getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe_pro_price_id: str = getenv("STRIPE_PRO_PRICE_ID", "")
    base_url: str = getenv("BASE_URL", "http://localhost:8000")


settings = Settings()

