"""設定管理モジュールのテスト。"""

import os
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml
from pydantic import ValidationError

from config.base import BaseAppModel, BaseAppSettings
from config.settings import (
    AppSettings,
    AuthSettings,
    SeleniumSettings,
    Endpoints,
    SpecialRule,
    MoneyForwardSettings,
    SpreadsheetSettings,
    PathSettings,
)


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """テスト用の設定データを提供。"""
    return {
        "moneyforward": {
            "base_url": "https://moneyforward.com",
            "auth": {
                "email": "test@example.com",
                "password": "testpassword",
                "two_factor_enabled": False,
            },
            "endpoints": {
                "login": "/login",
                "accounts": "/accounts",
                "history": "/history",
            },
            "selenium": {
                "download_directory": "/tmp/downloads",
                "timeout": 30,
                "retry_count": 3,
            },
            "special_rules": [
                {
                    "institution": "アメリカン・エキスプレス",
                    "action": "divide",
                    "value": 2.0,
                }
            ],
            "history": {"months_to_download": 3},
        },
        "spreadsheet": {
            "worksheets": {
                "household_data": {
                    "name": "家計簿",
                    "start_row": 2,
                    "columns": [{"name": "日付", "col": 1}, {"name": "金額", "col": 2}],
                },
                "assets_data": {
                    "name": "資産",
                    "start_row": 2,
                    "columns": [{"name": "日付", "col": 1}, {"name": "金額", "col": 2}],
                },
            }
        },
        "paths": {
            "outputs": {
                "base": "/tmp/outputs",
                "aggregated_files": {
                    "detail": "/tmp/outputs/detail.csv",
                    "assets": "/tmp/outputs/assets.csv",
                },
            },
            "downloads": "/tmp/downloads",
            "chrome_driver": "/usr/local/bin/chromedriver",
        },
    }


@pytest.fixture
def config_file(tmp_path: Path, sample_config: Dict[str, Any]) -> Path:
    """テスト用の設定ファイルを作成。"""
    config_path = tmp_path / "settings.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(sample_config, f)
    return config_path


class TestBaseAppModel:
    """BaseAppModelのテスト。"""

    def test_path_validator(self):
        """パスのバリデーションテスト。"""

        class TestModel(BaseAppModel):
            test_path: Path
            test_dir: Path

        model = TestModel(test_path="/tmp/test.txt", test_dir="/tmp/test_dir")
        assert isinstance(model.test_path, Path)
        assert isinstance(model.test_dir, Path)
        assert model.test_dir.exists()


class TestBaseAppSettings:
    """BaseAppSettingsのテスト。"""

    def test_load_yaml(self, config_file: Path):
        """YAML読み込みのテスト。"""

        class TestSettings(BaseAppSettings):
            test_value: str

        config = TestSettings.load_yaml(config_file)
        assert isinstance(config, dict)

    def test_load_with_env_vars(self, config_file: Path):
        """環境変数との統合テスト。"""

        class TestSettings(BaseAppSettings):
            test_value: str = "default"

        os.environ["APP_TEST_VALUE"] = "env_value"
        settings = TestSettings.load(config_file)
        assert settings.test_value == "env_value"

    def test_save_yaml(self, tmp_path: Path):
        """YAML保存のテスト。"""

        class TestSettings(BaseAppSettings):
            test_value: str = "test"

        settings = TestSettings()
        save_path = tmp_path / "test_settings.yaml"
        settings.save_yaml(save_path)
        assert save_path.exists()


class TestAuthSettings:
    """AuthSettingsのテスト。"""

    def test_valid_auth_settings(self):
        """有効な認証設定のテスト。"""
        settings = AuthSettings(
            email="test@example.com", password="testpassword", two_factor_enabled=False
        )
        assert settings.email == "test@example.com"
        assert settings.password.get_secret_value() == "testpassword"
        assert settings.two_factor_enabled is False

    def test_invalid_email(self):
        """無効なメールアドレスのテスト。"""
        with pytest.raises(ValidationError):
            AuthSettings(email="invalid-email", password="testpassword")


class TestSeleniumSettings:
    """SeleniumSettingsのテスト。"""

    def test_valid_settings(self):
        """有効な設定のテスト。"""
        settings = SeleniumSettings(
            download_directory="/tmp/downloads", timeout=30, retry_count=3
        )
        assert settings.timeout == 30
        assert settings.retry_count == 3

    def test_invalid_timeout(self):
        """無効なタイムアウト値のテスト。"""
        with pytest.raises(ValidationError):
            SeleniumSettings(
                download_directory="/tmp/downloads", timeout=0, retry_count=3
            )


class TestEndpoints:
    """Endpointsのテスト。"""

    def test_valid_endpoints(self):
        """有効なエンドポイントのテスト。"""
        endpoints = Endpoints(login="/login", accounts="/accounts", history="/history")
        assert endpoints.login == "/login"

    def test_invalid_endpoint(self):
        """無効なエンドポイントのテスト。"""
        with pytest.raises(ValidationError):
            Endpoints(login="invalid-path", accounts="/accounts", history="/history")


class TestSpecialRule:
    """SpecialRuleのテスト。"""

    def test_valid_rule(self):
        """有効なルールのテスト。"""
        rule = SpecialRule(institution="テスト銀行", action="multiply", value=2.0)
        assert rule.value == 2.0

    def test_invalid_action(self):
        """無効なアクションのテスト。"""
        with pytest.raises(ValidationError):
            SpecialRule(institution="テスト銀行", action="invalid", value=2.0)


class TestAppSettings:
    """AppSettingsのテスト。"""

    def test_load_from_yaml(self, config_file: Path):
        """YAMLからの読み込みテスト。"""
        settings = AppSettings.load(yaml_path=config_file)
        assert isinstance(settings.moneyforward, MoneyForwardSettings)
        assert isinstance(settings.spreadsheet, SpreadsheetSettings)
        assert isinstance(settings.paths, PathSettings)

    def test_settings_dependencies(self, config_file: Path):
        """設定の依存関係テスト。"""
        settings = AppSettings.load(yaml_path=config_file)
        assert (
            settings.moneyforward.selenium.download_directory
            == settings.paths.downloads
        )

    def test_validation_errors(self, sample_config: Dict[str, Any], tmp_path: Path):
        """バリデーションエラーのテスト。"""
        # URLの形式が無効な場合
        invalid_config = sample_config.copy()
        invalid_config["moneyforward"]["base_url"] = "invalid-url"

        config_path = tmp_path / "invalid_settings.yaml"
        with open(config_path, "w") as f:
            yaml.safe_dump(invalid_config, f)

        with pytest.raises(ValidationError):
            AppSettings.load(yaml_path=config_path)

    def test_path_creation(self, config_file: Path):
        """パスの自動作成テスト。"""
        settings = AppSettings.load(yaml_path=config_file)
        assert settings.paths.downloads.exists()
        assert settings.paths.outputs.base.exists()
