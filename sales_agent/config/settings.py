"""
Configuration for the Lexcom Sales Agent.
All config via env vars — copy .env.example to .env and fill in.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ConnectWise Manage
    cw_site_url: str = ""
    cw_company_id: str = ""
    cw_public_key: str = ""
    cw_private_key: str = ""
    cw_client_id: str = ""

    # TD Synnex StreamOne Ion
    tdsynnex_hostname: str = ""
    tdsynnex_account_id: str = ""
    tdsynnex_refresh_token: str = ""

    # Ollama (optional — for future AI-powered product matching)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct-v0.3-q4_K_M"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
