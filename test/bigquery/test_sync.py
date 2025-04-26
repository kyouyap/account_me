"""BigQuery同期処理のテスト。"""

import datetime
import json  # json をインポート
import logging  # logging をインポート
from unittest.mock import Mock

import pandas as pd
import pytest

from bigquery.sync import BigQuerySync
from exceptions.custom_exceptions import BigQueryError

# テスト用のロガー設定 (必要に応じて)
# logging.basicConfig(level=logging.WARNING)


class TestBigQuerySync:
    """BigQuerySync のテストクラス。"""

    def test_load_all_spreadsheet_data(self, mock_spreadsheet):
        """スプレッドシートからの全データ取得テスト。"""
        # mock_spreadsheet はタプル (mock, household_ws, assets_ws) を返す
        spreadsheet_mock, household_ws_mock, assets_ws_mock = mock_spreadsheet
        sync = BigQuerySync()
        df_household, df_assets = sync._load_all_spreadsheet_data(spreadsheet_mock)

        # 家計簿データの検証
        assert not df_household.empty
        assert len(df_household) == 2
        assert list(df_household.columns) == [
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
        assert df_household["ID"].iloc[0] == "test-id-1"
        # get_all_values が呼ばれたか確認
        household_ws_mock.get_all_values.assert_called_once()

        # 資産データの検証
        assert not df_assets.empty
        assert len(df_assets) == 2
        assert list(df_assets.columns) == [
            "日付",
            "合計（円）",
            "預金・現金・暗号資産（円）",
            "投資信託（円）",
        ]
        assert df_assets["合計（円）"].iloc[0] == "1000000"
        # get_all_values が呼ばれたか確認
        assets_ws_mock.get_all_values.assert_called_once()

    def test_load_empty_spreadsheet_data(self, mock_empty_spreadsheet):
        """空のスプレッドシートからのデータ取得テスト。"""
        # mock_empty_spreadsheet はタプル (mock, household_ws, assets_ws) を返す
        spreadsheet_mock, household_ws_mock, assets_ws_mock = mock_empty_spreadsheet
        sync = BigQuerySync()
        df_household, df_assets = sync._load_all_spreadsheet_data(spreadsheet_mock)

        # 空のデータフレームの検証
        assert df_household.empty
        assert df_assets.empty
        # get_all_values が呼ばれたか確認
        household_ws_mock.get_all_values.assert_called_once()
        assets_ws_mock.get_all_values.assert_called_once()

    def test_load_spreadsheet_data_error(self, mock_error_spreadsheet):
        """スプレッドシートからのデータ取得エラーテスト。"""
        sync = BigQuerySync()
        with pytest.raises(BigQueryError) as exc_info:
            sync._load_all_spreadsheet_data(mock_error_spreadsheet)
        assert "スプレッドシートからのデータ取得に失敗しました" in str(exc_info.value)

    def test_transform_household_data(self, sample_household_data):
        """家計簿データの変換処理テスト。"""
        sync = BigQuerySync()
        transformed = sync._transform_household_data(sample_household_data)

        # 変換後のデータ構造を確認
        expected_columns = [
            "id",
            "target_flag",
            "date",
            "description",
            "amount",
            "institution",
            "major_category",
            "sub_category",
            "memo",
            "transfer_flag",
            "created_at",
            "updated_at",
        ]
        assert list(transformed.columns) == expected_columns

        # データ型の確認
        assert transformed["target_flag"].dtype == bool
        assert transformed["transfer_flag"].dtype == bool
        assert transformed["amount"].dtype == int
        assert isinstance(transformed["date"].iloc[0], datetime.date)
        assert isinstance(transformed["created_at"].iloc[0], datetime.datetime)

        # 値の確認
        assert transformed["id"].iloc[0] == "test-id-1"
        assert transformed["amount"].iloc[0] == 1000
        assert transformed["major_category"].iloc[0] == "食費"

    def test_transform_assets_data(self, sample_assets_data):
        """資産データの変換処理テスト。"""
        sync = BigQuerySync()
        transformed = sync._transform_assets_data(sample_assets_data)

        # 変換後のデータ構造を確認
        expected_columns = [
            "date",
            "total_amount",
            "deposit_amount",
            "investment_amount",
            "created_at",
            "updated_at",
        ]
        assert list(transformed.columns) == expected_columns

        # データ型の確認
        assert isinstance(transformed["date"].iloc[0], datetime.date)
        assert transformed["total_amount"].dtype == int
        assert transformed["deposit_amount"].dtype == int
        assert transformed["investment_amount"].dtype == int
        assert isinstance(transformed["created_at"].iloc[0], datetime.datetime)

        # 値の確認
        assert transformed["total_amount"].iloc[0] == 1000000
        assert transformed["deposit_amount"].iloc[0] == 500000

    def test_is_table_empty_true(self, mock_bq_client):
        """空テーブル判定テスト（空の場合）。"""
        mock_bq_client.query().result().to_dataframe.return_value = pd.DataFrame(
            {"count": [0]}
        )

        sync = BigQuerySync()
        assert sync._is_table_empty("test_table") is True

    def test_is_table_empty_false(self, mock_bq_client):
        """空テーブル判定テスト（データがある場合）。"""
        mock_bq_client.query().result().to_dataframe.return_value = pd.DataFrame(
            {"count": [10]}
        )

        sync = BigQuerySync()
        assert sync._is_table_empty("test_table") is False

    def test_sync_with_empty_tables(
        self, mocker, mock_bq_client, mock_spreadsheet, mock_credentials
    ):
        """空テーブルに対する初期同期のテスト。"""
        # mock_spreadsheet はタプル (mock, household_ws, assets_ws) を返す
        spreadsheet_mock, household_ws_mock, assets_ws_mock = mock_spreadsheet

        # 認証・クライアントのモック
        gspread_client = Mock()
        # タプルの最初の要素を使用
        gspread_client.open_by_key.return_value = spreadsheet_mock
        mocker.patch("gspread.authorize", return_value=gspread_client)
        # 認証情報取得をモック (秘密鍵パースエラー回避)
        mocker.patch(
            "oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_dict",
            return_value=Mock(),
        )

        # テーブルが空の状態をモック
        df_empty = pd.DataFrame({"count": [0]})
        mock_bq_client.query.return_value.result.return_value.to_dataframe.return_value = df_empty  # noqa: E501

        sync = BigQuerySync()
        # 呼び出し前のカウントをログ出力
        logging.warning(
            f"Before sync: household call_count="
            f"{household_ws_mock.get_all_values.call_count}"
        )
        logging.warning(
            f"Before sync: assets call_count={assets_ws_mock.get_all_values.call_count}"
        )
        sync.sync()
        # 呼び出し後のカウントをログ出力
        logging.warning(
            f"After sync: household call_count="
            f"{household_ws_mock.get_all_values.call_count}"
        )
        logging.warning(
            f"After sync: assets call_count={assets_ws_mock.get_all_values.call_count}"
        )

        # スプレッドシートの各ワークシートが1回ずつ読み込まれたことを確認
        household_ws_mock.get_all_values.assert_called_once()
        assets_ws_mock.get_all_values.assert_called_once()

        # BigQueryへの書き込みが実行されたことを確認
        assert mock_bq_client.load_table_from_dataframe.called
        assert (
            mock_bq_client.load_table_from_dataframe.call_count == 2
        )  # household_data(tmp)とassets_data(tmp) の計2回

    def test_sync_with_existing_data(self, mocker, mock_bq_client, mock_credentials):
        """既存データがある場合の同期テスト。"""
        # mock_spreadsheet はタプルを返すが、このテストでは使用しない
        # 認証・クライアントのモック (gspread.authorize は sync 内で呼ばれる)
        gspread_client = Mock()
        # open_by_key は sync 内で呼ばれるが、
        # その後の worksheet アクセスは _load_all_spreadsheet_data ではないため、
        # このテストでは spreadsheet_mock 自体の詳細なモックは不要
        mocker.patch("gspread.authorize", return_value=gspread_client)
        # 認証情報取得をモック (秘密鍵パースエラー回避)
        mocker.patch(
            "oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_dict",
            return_value=Mock(),
        )

        # CSVファイルの読み込みをモック
        # (このテストでは _load_household_data/_load_assets_data が呼ばれる想定)
        csv_data_household = pd.DataFrame(
            {
                "計算対象": [True],
                "日付": ["2024/04/26"],
                "内容": ["テスト"],
                "金額（円）": [1000],
                "保有金融機関": ["テスト銀行"],
                "大項目": ["食費"],
                "中項目": ["食料品"],
                "メモ": ["なし"],
                "振替": [False],
                "ID": ["new-id-1"],  # 既存データと異なるID
            }
        )
        csv_data_assets = pd.DataFrame(
            {
                "日付": ["2024/04/26"],
                "合計（円）": [1100000],
                "預金・現金・暗号資産（円）": [600000],
                "投資信託（円）": [500000],
            }
        )
        # read_csv が複数回呼ばれることを想定し、side_effect を使用
        mocker.patch(
            "pandas.read_csv",
            side_effect=[csv_data_household, csv_data_assets],
        )

        # テーブルにデータが存在する状態をモック
        df_count = pd.DataFrame({"count": [10]})
        # query の呼び出し順序を明確にするため、configure_mock を使用
        mock_bq_client.query.configure_mock(
            side_effect=[
                # 1. _is_table_empty (household)
                Mock(
                    result=Mock(
                        return_value=Mock(to_dataframe=Mock(return_value=df_count))
                    )
                ),
                # 2. _is_table_empty (assets)
                Mock(
                    result=Mock(
                        return_value=Mock(to_dataframe=Mock(return_value=df_count))
                    )
                ),
                # 3. _sync_household_data (MERGE) - 成功を想定
                Mock(result=Mock(return_value=None)),  # MERGE は結果を返さない
                # 4. _sync_assets_data (MERGE) - 成功を想定
                Mock(result=Mock(return_value=None)),  # MERGE は結果を返さない
            ]
        )

        sync = BigQuerySync()
        sync.sync()

        # 差分同期が実行されたことを確認
        # pandas.read_csv が2回呼ばれたか
        assert pd.read_csv.call_count == 2
        # BigQueryへのクエリが4回実行されたか (_is_table_empty x2, MERGE x2)
        assert mock_bq_client.query.call_count == 4
        # BigQueryへのDataFrameロードが2回実行されたか (tmp x2)
        assert mock_bq_client.load_table_from_dataframe.call_count == 2

    def test_sync_error_no_spreadsheet_key(self, mocker):
        """スプレッドシートキーが未設定の場合のテスト。"""

        # SPREADSHEET_KEY のみ None を返すように修正
        def mock_getenv(key, default=None):
            if key == "SPREADSHEET_KEY":
                return None
            elif key == "SPREADSHEET_CREDENTIAL_JSON":
                # 認証情報は有効なものを返す（他のテストに影響を与えないように）
                return json.dumps(
                    {
                        "type": "service_account",
                        "project_id": "test",
                        "private_key_id": "test",
                        "private_key": "test",
                        "client_email": "test",
                        "client_id": "test",
                    }
                )
            return default  # その他のキーはデフォルト動作

        mocker.patch("os.getenv", side_effect=mock_getenv)

        sync = BigQuerySync()
        with pytest.raises(BigQueryError) as exc_info:
            sync.sync()
        assert "SPREADSHEET_KEYが環境変数に設定されていません" in str(exc_info.value)
