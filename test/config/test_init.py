"""設定管理モジュールのテスト。"""

from unittest.mock import mock_open, patch

import pytest
import yaml

from src.config import Config, ConfigurationError


@pytest.fixture
def config():
    """テスト用のConfigインスタンスを生成。"""
    # 各テストの前にインスタンスをリセット
    Config._instance = None
    Config._initialized = False
    return Config()


@pytest.fixture
def mock_settings():
    """テスト用の設定データ。"""
    return {
        "moneyforward": {
            "base_url": "http://example.com",
            "endpoints": {"login": "/login"},
        },
        "spreadsheet": {
            "sheet_id": "test_sheet_id",
            "range": "A1:Z100",
        },
        "paths": {
            "downloads": "/tmp/downloads",
            "outputs": "/tmp/outputs",
        },
    }


def test_singleton_pattern():
    """シングルトンパターンの検証。"""
    config1 = Config()
    config2 = Config()
    assert config1 is config2


def test_init_with_valid_settings(config, mock_settings):
    """有効な設定ファイルでの初期化テスト。"""
    mock_yaml = yaml.dump(mock_settings)
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        config._load_settings()
        assert config.settings == mock_settings


def test_init_with_missing_settings_file(config):
    """設定ファイルが存在しない場合のテスト。"""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(ConfigurationError) as exc_info:
            config._load_settings()
        assert "設定ファイルが見つかりません" in str(exc_info.value)


def test_init_with_invalid_settings_file(config):
    """設定ファイルがディレクトリの場合のテスト。"""
    with patch("pathlib.Path.exists", return_value=True), patch(
        "pathlib.Path.is_file", return_value=False
    ), pytest.raises(ConfigurationError) as exc_info:
        config._load_settings()
    assert "設定ファイルが正しくありません" in str(exc_info.value)


def test_init_with_empty_settings_file(config):
    """空の設定ファイルの場合のテスト。"""
    with patch("builtins.open", mock_open(read_data="")):
        with pytest.raises(ConfigurationError) as exc_info:
            config._load_settings()
        assert "設定ファイルが空です" in str(exc_info.value)


def test_init_with_invalid_yaml(config):
    """不正なYAML形式の設定ファイルの場合のテスト。"""
    invalid_yaml = "invalid: yaml: content: ["
    with patch("builtins.open", mock_open(read_data=invalid_yaml)):
        with pytest.raises(ConfigurationError) as exc_info:
            config._load_settings()
        assert "設定ファイルの読み込みに失敗" in str(exc_info.value)


def test_init_with_non_dict_yaml(config):
    """辞書以外のYAML形式の設定ファイルの場合のテスト。"""
    non_dict_yaml = "- item1\n- item2"
    with patch("builtins.open", mock_open(read_data=non_dict_yaml)):
        with pytest.raises(ConfigurationError) as exc_info:
            config._load_settings()
        assert "設定ファイルの形式が正しくありません" in str(exc_info.value)


def test_load_env(config):
    """環境変数読み込みのテスト。"""
    with patch("src.config.load_dotenv") as mock_load_dotenv:
        config._load_env()
        mock_load_dotenv.assert_called_once()


def test_get_setting_success(config, mock_settings):
    """設定値の取得テスト（成功）。"""
    config.settings = mock_settings
    assert config.get_setting("moneyforward", "base_url") == "http://example.com"
    assert config.get_setting("spreadsheet", "sheet_id") == "test_sheet_id"


def test_get_setting_failure(config):
    """設定値の取得テスト（失敗）。"""
    config.settings = {}
    with pytest.raises(ConfigurationError) as exc_info:
        config.get_setting("nonexistent", "key")
    assert "設定が見つかりません" in str(exc_info.value)


def test_moneyforward_property(config, mock_settings):
    """moneyforwardプロパティのテスト。"""
    config.settings = mock_settings
    assert config.moneyforward == mock_settings["moneyforward"]


def test_spreadsheet_property(config, mock_settings):
    """spreadsheetプロパティのテスト。"""
    config.settings = mock_settings
    assert config.spreadsheet == mock_settings["spreadsheet"]


def test_paths_property(config, mock_settings):
    """pathsプロパティのテスト。"""
    config.settings = mock_settings
    assert config.paths == mock_settings["paths"]


def test_property_with_missing_key(config):
    """存在しないキーに対するプロパティアクセスのテスト。"""
    config.settings = {}
    with pytest.raises(ConfigurationError):
        _ = config.moneyforward
    with pytest.raises(ConfigurationError):
        _ = config.spreadsheet
    with pytest.raises(ConfigurationError):
        _ = config.paths
