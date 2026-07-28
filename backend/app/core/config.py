from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    project_name: str="AgentForge"
    env: str="dev"
    database_url: str  #从这个环境变量读取

    class Config:
        env_file = ".env"
        extra = "ignore"   #忽略多余的env变量

settings = Settings()