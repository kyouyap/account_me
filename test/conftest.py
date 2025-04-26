"""テストの共通設定。"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch
import yaml

from config.settings import settings, Settings

# テストファイルのディレクトリパスを取得
test_dir = Path(__file__).parent
# プロジェクトのルートディレクトリパスを取得
project_root = test_dir.parent


def pytest_sessionstart(session):
    """テストセッション開始時の設定を行います。"""
    # srcディレクトリをPythonパスに追加
    sys.path.insert(0, str(project_root / "src"))


def pytest_configure(config):
    """pytestの設定を行います。"""
    config.addinivalue_line(
        "markers",
        "integration: マークされたテストはインテグレーションテストとして実行されます",
    )


# main.pyをテストコレクションから除外
collect_ignore = ["../src/main.py"]


@pytest.fixture
def test_settings():
    """テスト用の設定をロードするフィクスチャ。

    test/config/settings_test.yamlからテスト用の設定をロードして、
    本番用の設定をオーバーライドします。
    """
    # テスト用の設定ファイルパス
    test_settings_path = Path(__file__).parent / "config" / "settings_test.yaml"

    # テスト用の設定ファイルが存在する場合は読み込む
    if test_settings_path.exists():
        with open(test_settings_path, "r", encoding="utf-8") as f:
            test_config = yaml.safe_load(f)

        # Settingsクラスのインスタンスを作成
        test_settings = Settings.model_validate(test_config)
        return test_settings

    # テスト用の設定ファイルが存在しない場合は本番用の設定を使用
    return settings


@pytest.fixture(autouse=True)
def patch_settings(test_settings):
    """テスト実行時に設定をオーバーライドするフィクスチャ。

    autouse=Trueを設定しているため、自動的に全テストに適用されます。
    """
    with (
        patch("scraper.browser.settings", test_settings),
        patch("scraper.downloader.settings", test_settings),
        patch("scraper.scraper.settings", test_settings),
    ):
        yield test_settings
