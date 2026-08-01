from pydantic_settings import BaseSettings, SettingsConfigDict
# a sub library from pydantic used to validate config data like .env
from functools import lru_cache
# a tool to prever reloading .env values each request

# the nested classes below is a standard structure 
class Settings(BaseSettings):
    # here you define the same vars used in .env file in the chosen datatype
    model_config= SettingsConfigDict(

        # this to automatic check when every value changes
        validate_assignment=True,
        # the path to your file:
        env_file=".env",
        # to ignore validation to the non-mentioned vars below but mentioned in the .env
        extra="ignore"
        )
    APP_NAME: str
    APP_VERSION: str
    FILE_MAX_SIZE: int
    GEMINI_API_KEY: str
    FILE_ALLOWED_TYPES: list
    FILE_DEFAULT_CHUNK_SIZE: int
    DATABASE_URL: str
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    REDIS_TTL: int = 86400

@lru_cache
def get_settings() -> Settings:
    # lru_cache ensures Settings() is only created once — .env is read once per process
    return Settings()