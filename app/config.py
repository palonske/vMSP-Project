from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Default to localhost for dev, but override via ENV
    BASE_URL: str = "http://127.0.0.1:8000"
    OCPI_VERSION: str = "2.1.1"

    # This automatically looks for a .env file
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()