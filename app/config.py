from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    admin_username: str = Field(..., env="ADMIN_USERNAME")
    admin_password: str = Field(..., env="ADMIN_PASSWORD")
    session_secret: Optional[str] = Field(None, env="SESSION_SECRET")
    session_cookie_name: str = Field("session_admin", env="SESSION_COOKIE_NAME")

    seafile_server: str = Field(..., env="SEAFILE_SERVER")
    seafile_repo_id: str = Field(..., env="SEAFILE_REPO_ID")
    seafile_token: str = Field(..., env="SEAFILE_TOKEN")

    database_url: str = Field("sqlite:///./coffee_machines.db", env="DATABASE_URL")
    allowed_origins_raw: str = Field("", env="ALLOWED_ORIGINS")

    # Telegram for lead notifications
    telegram_bot_token: Optional[str] = Field(None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, env="TELEGRAM_CHAT_ID")

    # Ozon Seller API
    ozon_client_id: Optional[str] = Field(None, env="OZON_CLIENT_ID")
    ozon_api_key: Optional[str] = Field(None, env="OZON_API_KEY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> List[str]:
        if not self.allowed_origins_raw:
            return []
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def resolved_session_secret(self) -> str:
        # Фоллбек: если переменная не задана, используем пароль админа.
        return self.session_secret or self.admin_password
