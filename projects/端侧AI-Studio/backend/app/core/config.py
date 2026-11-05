"""运行配置。钥匙只从环境或 backend/.env 读取，不写进代码。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PRODUCT_DIR = BACKEND_DIR.parent
DEFAULT_DATA_DIR = PRODUCT_DIR / "data"


class Settings(BaseSettings):
    invite_code: str = "studio-demo"
    session_secret: str = "change-me"
    database_url: str = ""
    data_dir: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = ""
    sensetime_api_keys: str = ""
    sensetime_base_url: str = "https://token.sensenova.cn/v1"
    sensetime_model: str = "sensenova-u1.5-fast"
    ant_api_key: str = ""
    ant_base_url: str = "https://maas-api.antdigital.com"
    ant_video_model: str = "wan2.7-i2v"
    fake_models: bool = False
    session_days: int = 7
    max_upload_bytes: int = 10 * 1024 * 1024
    deepseek_timeout: float = 60
    sensetime_timeout: float = 600

    model_config = SettingsConfigDict(extra="ignore")

    def sensetime_keys(self) -> list[str]:
        return [item.strip() for item in self.sensetime_api_keys.split(",") if item.strip()]

    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir) if self.data_dir else DEFAULT_DATA_DIR

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        path = self.resolved_data_dir() / "app.db"
        return f"sqlite:///{path}"


def load_settings() -> Settings:
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        return Settings(_env_file=env_file)
    return Settings()
