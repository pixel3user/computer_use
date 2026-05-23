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

    def test_llm_config_defaults(self, tmp_path):
        """Test that LLM config has correct defaults when not specified."""
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

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert config.llm.enabled is True
        assert config.llm.model == "meta-llama/llama-4-scout-17b-16e-instruct"
        assert config.llm.max_tokens == 4096
        assert config.llm.temperature == 0.2
        assert config.llm.max_steps == 50

    def test_quota_config_defaults(self, tmp_path):
        """Test that quota config has correct defaults when not specified."""
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

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert config.quota.max_naukri_applications == 50
        assert config.quota.enable_direct_apply is True

    def test_llm_config_from_yaml(self, tmp_path):
        """Test that LLM config can be loaded from YAML."""
        config_data = {
            "user_profile": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "+91-9876543210",
                "resume_path": "./resume.pdf",
            },
            "naukri_email": "naukri@example.com",
            "naukri_password": "secret123",
            "llm": {
                "enabled": False,
                "model": "custom-model",
                "max_tokens": 2048,
                "temperature": 0.5,
            },
            "quota": {
                "max_naukri_applications": 25,
                "enable_direct_apply": False,
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert config.llm.enabled is False
        assert config.llm.model == "custom-model"
        assert config.llm.max_tokens == 2048
        assert config.llm.temperature == 0.5
        assert config.quota.max_naukri_applications == 25
        assert config.quota.enable_direct_apply is False

    def test_groq_api_key_from_env(self, tmp_path, monkeypatch):
        """Test that GROQ_API_KEY is loaded from environment."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_123")

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

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert config.groq_api_key == "gsk_test_key_123"

    def test_groq_api_key_none_when_not_set(self, tmp_path, monkeypatch):
        """Test that groq_api_key is None when env var is not set."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

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

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert config.groq_api_key is None
