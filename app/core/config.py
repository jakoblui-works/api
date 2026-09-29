from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "site_db"
    user: str = "postgres"
    password: SecretStr

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379


class SentrySettings(BaseModel):
    dsn: str = ""
    environment: str = "development"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )
    log_level: str = "INFO"

    app_name: str = "site-api"
    debug: bool = False

    database: DatabaseSettings
    redis: RedisSettings = RedisSettings()
    sentry: SentrySettings = SentrySettings()


settings = Settings()
