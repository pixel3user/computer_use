import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from naukri_apply.models import LLMConfig, QuotaConfig, UserProfile


class AppConfig(BaseModel):
    user_profile: UserProfile
    naukri_email: str
    naukri_password: str
    output_csv: Path = Path("applications.csv")
    headless: bool = False
    slow_mo: int = 100
    user_data_dir: Path = Path(".browser_data")
    delay_between_applications: float = 5.0
    signup_password: Optional[str] = None
    llm: LLMConfig = LLMConfig()
    quota: QuotaConfig = QuotaConfig()
    groq_api_key: Optional[str] = None


def load_config(config_path: str | Path) -> AppConfig:
    """Load application configuration from a YAML file.

    Environment variables NAUKRI_EMAIL and NAUKRI_PASSWORD override
    the values specified in the YAML file. A .env file is loaded
    at this point (not at import time) to inject secrets.
    """
    from dotenv import load_dotenv

    load_dotenv()

    config_path = Path(config_path)

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    # Allow env var overrides for credentials
    env_email = os.environ.get("NAUKRI_EMAIL")
    env_password = os.environ.get("NAUKRI_PASSWORD")

    if env_email:
        data["naukri_email"] = env_email
    if env_password:
        data["naukri_password"] = env_password

    # Load GROQ_API_KEY from environment
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if groq_api_key:
        data["groq_api_key"] = groq_api_key

    return AppConfig(**data)
