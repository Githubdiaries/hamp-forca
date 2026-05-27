from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://hamper:hamper_secret@localhost:5432/hamper_forecast"
    firecrawl_api_key: str = ""
    model_dir: str = "/models"
    forecast_horizon: int = 6
    lstm_window: int = 12
    min_training_rows: int = 18
    train_epochs: int = 80
    market_sources_path: str = "/app/config/market_sources.yaml"


settings = Settings()
