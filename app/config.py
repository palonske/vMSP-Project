from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Default to localhost for dev, but override via ENV
    BASE_URL: str = "http://127.0.0.1:8000"

    # OCPI version configuration
    # Add new versions to this list as they are implemented (e.g., ["2.1.1", "2.2.1"])
    SUPPORTED_OCPI_VERSIONS: List[str] = ["2.1.1"]
    DEFAULT_OCPI_VERSION: str = "2.1.1"  # Primary version for new connections

    # This automatically looks for a .env file
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()