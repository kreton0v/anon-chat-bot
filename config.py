import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.environ.get("ADMIN_ID", "0"))
    OWNER_ID: int = int(os.environ.get("OWNER_ID", os.environ.get("ADMIN_ID", "0")))
    REVEAL_PRICE: int = int(os.environ.get("REVEAL_PRICE", "100"))
    DATA_DIR: str = os.environ.get("DATA_DIR", "/data")
    WEBHOOK_HOST: str = os.environ.get("WEBHOOK_HOST", "")
    WEBHOOK_PATH: str = os.environ.get("WEBHOOK_PATH", "/webhook")
    WEBAPP_HOST: str = os.environ.get("WEBAPP_HOST", "0.0.0.0")
    WEBAPP_PORT: int = int(os.environ.get("PORT", "8000"))
    POLLING: bool = os.environ.get("POLLING", "false").lower() == "true"

    @property
    def webhook_url(self) -> str:
        return f"{self.WEBHOOK_HOST}{self.WEBHOOK_PATH}"

    @property
    def db_path(self) -> str:
        return os.path.join(self.DATA_DIR, "bot.db")


CONFIG = Config()
