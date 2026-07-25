from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    project_name: str="AgentForge"
    env: str="dev"

    class Config:
        env_file = ".env"

settings = Settings()