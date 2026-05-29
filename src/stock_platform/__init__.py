from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "jckchen"
    db_password: str = "123"
    db_name: str = "stock_market"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8501

    crawler_delay: float = 0.5
    crawler_timeout: int = 10
    crawler_retries: int = 3

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
