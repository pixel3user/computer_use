import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from naukri_apply.models import UserProfile

load_dotenv()


class AppConfig(BaseModel):
    user_profile: UserProfile
    naukri_email: str
    naukri_password: str
    output_csv: Path = Path("applications.csv")
    headless: bool = False
    slow_mo: int = 100
    user_data_dir: Path = Path(".browser_data")


def load_config(config_path: str | Path) -> AppConfig:
    """Load application configuration from a YAML file.

    Environment variables NAUKRI_EMAIL and NAUKRI_PASSWORD override
    the values specified in the YAML file.
    """
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

    return AppConfig(**data)
