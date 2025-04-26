"""BigQueryテストのためのフィクスチャ。"""

import json

import pandas as pd
import pytest

from src.config.settings import settings

# ダミーのPEM形式秘密鍵 (テスト用)
# 本番環境のキーとは異なる、テスト専用のものです
DUMMY_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJS8VykQ+x4F
yQyBw5Xhrh2jWRGeWaD+d/k+J/X/Z6ZQWf7aJcQXks/+VSoqJy4eH767F8N/p0D8
... (省略: これはダミーであり、実際のキーではありません) ...
+lXyrWg9a4V+wBwT9V+T4aQ==
-----END PRIVATE KEY-----
"""


@pytest.fixture
def mock_bq_client(mocker):
    """BigQueryクライアントのモック。"""
    mock = mocker.Mock()
    mocker.patch("google.cloud.bigquery.Client", return_value=mock)
    return mock


@pytest.fixture
def mock_credentials(mocker):
    """認証情報のモック."""
    json_data = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "test-key-id",
        "private_key": DUMMY_PRIVATE_KEY,  # ダミーキーを使用
        "client_email": "test@example.com",
        "client_id": "test-client-id",
    }
    mocker.patch(
        "os.getenv",
        side_effect=lambda key: (
            json.dumps(json_data)
            if key == "SPREADSHEET_CREDENTIAL_JSON"
            else "test-key"
        ),
    )
    return json_data


@pytest.fixture
def mock_spreadsheet(mocker):
    """正常系のスプレッドシートモック。"""
    mock = mocker.Mock()

    # 家計簿ワークシートのモック
    household_worksheet = mocker.Mock()
    household_worksheet.get_all_values.return_value = [
        [""],  # 1行目: 空行
        [""],  # 2行目: 空行
        [
            "計算対象",
            "日付",
            "内容",
            "金額（円）",
            "保有金融機関",
            "大項目",
            "中項目",
            "メモ",
            "振替",
            "ID",
        ],  # 3行目: ヘッダー
        [
            "TRUE",
            "2024/04/26",
            "テスト取引1",
            "1000",
            "テスト銀行",
            "食費",
            "食料品",
            "なし",
            "FALSE",
            "test-id-1",
        ],
        [
            "TRUE",
            "2024/04/25",
            "テスト取引2",
            "2000",
            "テスト銀行",
            "日用品",
            "消耗品",
            "なし",
            "FALSE",
            "test-id-2",
        ],
    ]

    # 資産ワークシートのモック
    assets_worksheet = mocker.Mock()
    assets_worksheet.get_all_values.return_value = [
        [""],  # 1行目: 空行
        [""],  # 2行目: 空行
        [
            "日付",
            "合計（円）",
            "預金・現金・暗号資産（円）",
            "投資信託（円）",
        ],  # 3行目: ヘッダー
        ["2024/04/26", "1000000", "500000", "500000"],
        ["2024/04/25", "900000", "400000", "500000"],
    ]

    # settings.yamlのモック値を設定
    mocker.patch(
        "config.settings.settings.spreadsheet.worksheets.household_data.columns",
        [
            type("Column", (), {"name": col})
            for col in [
                "計算対象",
                "日付",
                "内容",
                "金額（円）",
                "保有金融機関",
                "大項目",
                "中項目",
                "メモ",
                "振替",
                "ID",
            ]
        ],
    )
    mocker.patch(
        "config.settings.settings.spreadsheet.worksheets.assets_data.columns",
        [
            type("Column", (), {"name": col})
            for col in [
                "日付",
                "合計（円）",
                "預金・現金・暗号資産（円）",
                "投資信託（円）",
            ]
        ],
    )

    def _mock_worksheet_impl(name):
        # settings オブジェクトの状態に依存しないように、ワークシート名を直接比較する
        if name == "@家計簿データ 貼付":
            return household_worksheet
        elif name == "@資産推移 貼付":
            return assets_worksheet
        else:
            raise ValueError(f"Unknown worksheet name: {name}")

    mock.worksheet = mocker.Mock(side_effect=_mock_worksheet_impl)
    # 内部のワークシートモックも返すように変更
    return mock, household_worksheet, assets_worksheet


@pytest.fixture
def mock_empty_spreadsheet(mocker):
    """空のワークシートを持つスプレッドシートモック。"""
    mock = mocker.Mock()

    # 空の家計簿ワークシート
    household_worksheet = mocker.Mock()
    household_worksheet.get_all_values.return_value = [
        [""],  # 1行目: 空行
        [""],  # 2行目: 空行
        [
            "計算対象",
            "日付",
            "内容",
            "金額（円）",
            "保有金融機関",
            "大項目",
            "中項目",
            "メモ",
            "振替",
            "ID",
        ],  # 3行目: ヘッダー
    ]

    # 空の資産ワークシート
    assets_worksheet = mocker.Mock()
    assets_worksheet.get_all_values.return_value = [
        [""],  # 1行目: 空行
        [""],  # 2行目: 空行
        [
            "日付",
            "合計（円）",
            "預金・現金・暗号資産（円）",
            "投資信託（円）",
        ],  # 3行目: ヘッダー
    ]

    # settings.yamlのモック値を設定
    mocker.patch(
        "config.settings.settings.spreadsheet.worksheets.household_data.columns",
        [
            type("Column", (), {"name": col})
            for col in [
                "計算対象",
                "日付",
                "内容",
                "金額（円）",
                "保有金融機関",
                "大項目",
                "中項目",
                "メモ",
                "振替",
                "ID",
            ]
        ],
    )
    mocker.patch(
        "config.settings.settings.spreadsheet.worksheets.assets_data.columns",
        [
            type("Column", (), {"name": col})
            for col in [
                "日付",
                "合計（円）",
                "預金・現金・暗号資産（円）",
                "投資信託（円）",
            ]
        ],
    )

    def _mock_worksheet_impl_empty(name):
        # settings オブジェクトの状態に依存しないように、ワークシート名を直接比較する
        # settings.yaml の値を使うように修正
        if name == settings.spreadsheet.worksheets.household_data.name:
            return household_worksheet
        elif name == settings.spreadsheet.worksheets.assets_data.name:
            return assets_worksheet
        else:
            raise ValueError(f"Unknown worksheet name: {name}")

    mock.worksheet = mocker.Mock(side_effect=_mock_worksheet_impl_empty)
    # 内部のワークシートモックも返すように変更
    return mock, household_worksheet, assets_worksheet


@pytest.fixture
def mock_error_spreadsheet(mocker):
    """エラーを発生させるスプレッドシートモック。"""
    mock = mocker.Mock()
    mock.worksheet.side_effect = Exception("シートの取得に失敗しました")
    return mock


@pytest.fixture
def sample_household_data():
    """家計簿のサンプルデータ。"""
    return pd.DataFrame(
        {
            "計算対象": [True, True],
            "日付": ["2024/04/26", "2024/04/25"],
            "内容": ["テスト取引1", "テスト取引2"],
            "金額（円）": [1000, 2000],
            "保有金融機関": ["テスト銀行", "テスト銀行"],
            "大項目": ["食費", "日用品"],
            "中項目": ["食料品", "消耗品"],
            "メモ": ["なし", "なし"],
            "振替": [False, False],
            "ID": ["test-id-1", "test-id-2"],
        }
    )


@pytest.fixture
def sample_assets_data():
    """資産のサンプルデータ。"""
    return pd.DataFrame(
        {
            "日付": ["2024/04/26", "2024/04/25"],
            "合計（円）": [1000000, 900000],
            "預金・現金・暗号資産（円）": [500000, 400000],
            "投資信託（円）": [500000, 500000],
        }
    )
