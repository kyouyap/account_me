"""ロギング設定のテスト。"""

import logging
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from src.config.logging_config import setup_logging


@pytest.fixture
def sample_yaml_config():
    """テスト用のYAML設定を提供する。"""
    return """
version: 1
formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: default
    level: INFO
loggers:
  '':
    handlers: [console]
    level: INFO
"""


def test_setup_logging_with_yaml(sample_yaml_config):
    """YAMLファイルが存在する場合のテスト。"""
    mock_path = Path("/app/config/logging.yaml")

    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("builtins.open", mock_open(read_data=sample_yaml_config)) as mock_file,
        patch("logging.config.dictConfig") as mock_dict_config,
    ):
        mock_exists.return_value = True
        setup_logging()

        # ファイルが正しいパスでオープンされたことを確認
        mock_file.assert_called_once_with(mock_path, "r", encoding="utf-8")

        # 設定が正しく適用されたことを確認
        expected_config = yaml.safe_load(sample_yaml_config)
        mock_dict_config.assert_called_once_with(expected_config)


def test_setup_logging_without_yaml():
    """YAMLファイルが存在しない場合のテスト。"""
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("logging.basicConfig") as mock_basic_config,
        patch("logging.warning") as mock_warning,
    ):
        mock_exists.return_value = False
        setup_logging()

        # 基本設定が正しく呼び出されたことを確認
        mock_basic_config.assert_called_once()
        kwargs = mock_basic_config.call_args[1]

        assert kwargs["level"] == logging.INFO
        assert (
            kwargs["format"] == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        assert len(kwargs["handlers"]) == 2

        # 警告メッセージが出力されたことを確認
        mock_warning.assert_called_once_with(
            "ロギング設定ファイルが見つかりません: %s", Path("/app/config/logging.yaml")
        )
