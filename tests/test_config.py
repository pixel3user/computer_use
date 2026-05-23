import os
from pathlib import Path

import pytest
import yaml

from naukri_apply.config import AppConfig, load_config


class TestConfigLoading:
    def test_load_config_from_valid_yaml(self, sample_config_yaml):
        config = load_config(sample_config_yaml)

        assert config.naukri_email == "naukri@example.com"
        assert config.naukri_password == "secret123"
        assert config.user_profile.name == "Test User"
        assert config.headless is True
        assert config.slow_mo == 50

    def test_env_var_overrides_email(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv("NAUKRI_EMAIL", "env_email@example.com")

        config = load_config(sample_config_yaml)

        assert config.naukri_email == "env_email@example.com"

    def test_env_var_overrides_password(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv("NAUKRI_PASSWORD", "env_secret_pass")

        config = load_config(sample_config_yaml)

        assert config.naukri_password == "env_secret_pass"

    def test_missing_required_fields_raises_error(self, tmp_path):
        config_data = {
            "user_profile": {
                "name": "Test User",
                # missing email, phone, resume_path
            },
            "naukri_email": "test@example.com",
            "naukri_password": "pass",
        }

        config_file = tmp_path / "bad_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(Exception):
            load_config(config_file)

    def test_default_values(self, sample_config_yaml, tmp_path):
        # Create config without optional fields
        config_data = {
            "user_profile": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "+91-9876543210",
                "resume_path": "./resume.pdf",
            },
            "naukri_email": "naukri@example.com",
            "naukri_password": "secret123",
        }

        config_file = tmp_path / "minimal_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert config.output_csv == Path("applications.csv")
        assert config.headless is False
        assert config.slow_mo == 100
        assert config.user_data_dir == Path(".browser_data")
