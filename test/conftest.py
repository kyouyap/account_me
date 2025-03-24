"""テストの共通設定。"""

import sys
from pathlib import Path

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
