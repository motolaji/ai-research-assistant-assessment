#Config file

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    ...
    """
    # Load var from env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Models
    anthropic_model_name: str = "claude-sonnet-4-6"
    openai_model_name: str = "gpt-4.1-mini"

    # Data
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = base_dir / "mock-data"
    # raw_data_dir: Path = data_dir / "raw"
    # processed_data_dir: Path = data_dir / "processed"
    logs_dir: Path = base_dir / "logs"

    # Governance
    cell_threshold: int = 5

    # 


settings = Settings()