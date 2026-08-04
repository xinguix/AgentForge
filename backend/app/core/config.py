from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    project_name: str="AgentForge"
    env: str="dev"
    database_url: str  #从这个环境变量读取
    redis_url: str = "redis://redis:6379"
    upload_dir: str = "./uploads"

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    default_model: str = "deepseek-chat"

    class Config:
        env_file = ".env"
        extra = "ignore"   #忽略多余的env变量

settings = Settings()