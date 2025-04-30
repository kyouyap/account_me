"""BigQuery同期モジュール。"""

import datetime
import json
import logging
import os
from pathlib import Path

import gspread
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials

from config.secrets import get_project_id
from config.settings import settings
from exceptions.custom_exceptions import BigQueryError

logger = logging.getLogger(__name__)


class BigQuerySync:
    """BigQueryとの同期を管理するクラス。"""

    def __init__(self) -> None:
        """初期化。"""

        info = json.loads(os.environ["SPREADSHEET_CREDENTIAL_JSON"])  # type: ignore
        creds = service_account.Credentials.from_service_account_info(info)
        self._client = bigquery.Client(project=get_project_id(), credentials=creds)
        # データセットを指定してテーブルを完全修飾
        dataset = "moneyforward"
        self._household_table = f"{dataset}.household_data"
        self._assets_table = f"{dataset}.assets_data"

    def _get_credentials(self) -> ServiceAccountCredentials:
        """Google APIクライアントの認証情報を取得。

        Returns:
            ServiceAccountCredentials: 認証済みのクレデンシャル

        Raises:
            BigQueryError: 認証情報の取得に失敗した場合
        """
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
            credentials_info = json.loads(os.getenv("SPREADSHEET_CREDENTIAL_JSON"))  # type: ignore
            return ServiceAccountCredentials.from_json_keyfile_dict(
                credentials_info, scope
            )
        except Exception as e:
            raise BigQueryError(f"認証情報の取得に失敗しました: {e}") from e

    def _is_table_empty(self, table_name: str) -> bool:
        """指定テーブルが空かどうかを判定。

        Args:
            table_name: テーブル名

        Returns:
            bool: テーブルが空の場合True
        """
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        count = self._client.query(query).result().to_dataframe()["count"][0]
        return bool(count == 0)  # numpy.bool_ → Python bool に変換

    def _load_all_spreadsheet_data(
        self, spreadsheet: gspread.Spreadsheet
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """スプレッドシートから全データを取得。

        Args:
            spreadsheet: データ取得元のスプレッドシート

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                家計簿データと資産データのタプル

        Raises:
            BigQueryError: データ取得に失敗した場合
        """
        try:
            # 家計簿データ取得
            household_worksheet = spreadsheet.worksheet(
                settings.spreadsheet.worksheets.household_data.name
            )
            settings_config = settings.spreadsheet.worksheets.household_data
            # 全データを取得（ヘッダー行含む）
            all_values = household_worksheet.get_all_values()
            # ヘッダー行（3行目）までスキップしてデータ行を取得
            data_rows = all_values[3:]  # 4行目以降がデータ

            # 設定で定義された列のインデックスのみを抽出
            columns = [col.name for col in settings_config.columns]
            # 1-basedから0-basedに変換
            column_indices = [col.col - 1 for col in settings_config.columns]

            # 必要な列のデータのみを抽出（データ行のみ）
            filtered_data = [[row[i] for i in column_indices] for row in data_rows]

            # DataFrameの作成（columnsパラメータで列名を明示的に指定）
            df_household = pd.DataFrame(
                data=filtered_data,
                columns=columns,
            )

            # 資産データ取得
            assets_worksheet = spreadsheet.worksheet(
                settings.spreadsheet.worksheets.assets_data.name
            )
            settings_config = settings.spreadsheet.worksheets.assets_data
            # 全データを取得（ヘッダー行含む）
            all_values = assets_worksheet.get_all_values()
            # ヘッダー行（3行目）までスキップしてデータ行を取得
            data_rows = all_values[3:]  # 4行目以降がデータ

            # 設定で定義された列のインデックスのみを抽出
            columns = [col.name for col in settings_config.columns]
            column_indices = [col.col - 1 for col in settings_config.columns]

            # 必要な列のデータのみを抽出（データ行のみ）
            filtered_data = [[row[i] for i in column_indices] for row in data_rows]

            # DataFrameの作成（columnsパラメータで列名を明示的に指定）
            df_assets = pd.DataFrame(
                data=filtered_data,
                columns=columns,
            )

            return df_household, df_assets

        except Exception as e:
            raise BigQueryError(
                f"スプレッドシートからのデータ取得に失敗しました: {e}"
            ) from e

    def _transform_household_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """家計簿データをBigQuery用に変換。

        Args:
            df: 変換元のデータフレーム

        Returns:
            pd.DataFrame: 変換後のデータフレーム

        Raises:
            ValueError: データの変換に失敗した場合
        """
        df_bq = df.copy()

        # 「日付」という文字列を含む行を削除
        df_bq = df_bq[df_bq["日付"] != "日付"].copy()

        # カラム名の変更を最初に実行
        df_bq = df_bq.rename(
            columns={
                "計算対象": "target_flag",
                "内容": "description",
                "金額（円）": "amount",
                "保有金融機関": "institution",
                "大項目": "major_category",
                "中項目": "sub_category",
                "メモ": "memo",
                "振替": "transfer_flag",
                "ID": "id",
            }
        )

        # 日付フォーマットの変換
        try:
            df_bq["date"] = pd.to_datetime(df_bq["日付"], format="%Y/%m/%d").dt.date
        except ValueError as e:
            logger.error(
                f"日付の変換に失敗しました。データサンプル: \n{df_bq['日付'].head()}"
            )
            raise ValueError(f"日付の変換に失敗しました: {e}") from e

        # データ型の変換（エラー処理を追加）
        try:
            # フラグの変換
            # 1/0を適切にブール値に変換
            df_bq["target_flag"] = (
                df_bq["target_flag"]
                .fillna("0")
                .astype(str)
                .map({"1": True, "0": False})
            )
            df_bq["transfer_flag"] = df_bq["transfer_flag"].fillna(False).astype(bool)

            # 金額の変換（小数点を考慮）と丸め処理
            df_bq["amount"] = (
                pd.to_numeric(df_bq["amount"], errors="coerce")
                .round()  # 明示的な丸め処理
                .fillna(0)
                .astype("Int64")
            )
        except ValueError as e:
            logger.error(
                f"データ型の変換に失敗しました:\n"
                f"金額のサンプル: {df_bq['金額（円）'].head()}\n"
                f"エラー: {e}"
            )
            raise ValueError(f"データ型の変換に失敗しました: {e}") from e

        # タイムスタンプの追加
        current_time = datetime.datetime.now(datetime.UTC)
        df_bq["created_at"] = current_time
        df_bq["updated_at"] = current_time

        return df_bq[
            [
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
        ]

    def _transform_assets_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """資産データをBigQuery用に変換（縦持ちデータに変換）。

        Args:
            df: 変換元のデータフレーム

        Returns:
            pd.DataFrame: 変換後のデータフレーム
        """
        df_bq = df.copy()

        # 「日付」という文字列を含む行を削除
        df_bq = df_bq[df_bq["日付"] != "日付"].copy()

        # 日付フォーマットの変換
        try:
            df_bq["date"] = pd.to_datetime(df_bq["日付"], format="%Y/%m/%d").dt.date
        except ValueError as e:
            logger.error(
                f"日付の変換に失敗しました。データサンプル: \n{df_bq['日付'].head()}"
            )
            raise ValueError(f"日付の変換に失敗しました: {e}") from e

        # カラム名の変更と金額の変換
        try:
            # 預金データの処理
            df_deposit = df_bq.copy()
            df_deposit["category"] = "deposit"

            def _convert_amount(series):
                """金額列を数値型に変換する共通関数"""
                if series.dtype == "object":
                    # 文字列型の場合、¥記号とカンマを削除してから変換
                    return (
                        pd.to_numeric(
                            series.astype(str)
                            .str.replace("¥", "", regex=False)
                            .str.replace(",", "", regex=False),
                            errors="coerce",
                        )
                        .round()
                        .fillna(0)
                        .astype("Int64")
                    )
                else:
                    # 既に数値型の場合は直接変換
                    return (
                        pd.to_numeric(series, errors="coerce")
                        .round()
                        .fillna(0)
                        .astype("Int64")
                    )

            # 資産カテゴリごとにデータを処理する
            categories = [
                {"category": "deposit", "amount_column": "預金・現金・暗号資産（円）"},
                {"category": "investment", "amount_column": "投資信託（円）"},
            ]

            dfs = []
            for cat in categories:
                df_cat = df_bq.copy()
                df_cat["category"] = cat["category"]
                df_cat["amount"] = _convert_amount(df_cat[cat["amount_column"]])
                df_cat = df_cat[df_cat.amount != 0]  # 金額が0のレコードを除外
                dfs.append(df_cat)

            # すべてのデータフレームを結合
            df_bq = pd.concat(dfs)

        except ValueError as e:
            logger.error(
                f"データ型の変換に失敗しました:\n"
                f"データのサンプル:\n"
                f"預金: {df_bq['預金・現金・暗号資産（円）'].head()}\n"
                f"投資: {df_bq['投資信託（円）'].head()}\n"
                f"エラー: {e}"
            )
            raise ValueError(f"データ型の変換に失敗しました: {e}") from e

        # タイムスタンプの追加
        current_time = datetime.datetime.now(datetime.UTC)
        df_bq["created_at"] = current_time
        df_bq["updated_at"] = current_time

        return df_bq[
            [
                "date",
                "category",
                "amount",
                "created_at",
                "updated_at",
            ]
        ]

    def _load_household_data(self, date: datetime.datetime) -> pd.DataFrame:
        """家計簿データを読み込む。

        Args:
            date: データの日付

        Returns:
            pd.DataFrame: 読み込んだデータ

        Raises:
            BigQueryError: データの読み込みに失敗した場合
        """
        try:
            detail_path = (
                Path(settings.paths.outputs.aggregated_files.detail)
                / f"detail_{date.strftime('%Y%m%d')}.csv"
            )
            df = pd.read_csv(detail_path, encoding="utf-8-sig")
            # 必要なカラムが存在するか確認し、なければ追加
            if "メモ" not in df.columns:
                df["メモ"] = "なし"
            if "振替" not in df.columns:
                df["振替"] = False  # デフォルト値を設定
            if "計算対象" not in df.columns:
                df["計算対象"] = True  # デフォルト値を設定
            return df
        except Exception as e:
            raise BigQueryError(f"家計簿データの読み込みに失敗しました: {e}") from e

    def _load_assets_data(self, date: datetime.datetime) -> pd.DataFrame:
        """資産データを読み込む。

        Args:
            date: データの日付

        Returns:
            pd.DataFrame: 読み込んだデータ

        Raises:
            BigQueryError: データの読み込みに失敗した場合
        """
        try:
            assets_path = (
                Path(settings.paths.outputs.aggregated_files.assets)
                / f"assets_{date.strftime('%Y%m%d')}.csv"
            )
            return pd.read_csv(assets_path, encoding="utf-8-sig")
        except Exception as e:
            raise BigQueryError(f"資産データの読み込みに失敗しました: {e}") from e

    def _sync_household_data(self, df: pd.DataFrame) -> None:
        """家計簿データの同期処理。

        Args:
            df: 同期するデータフレーム

        Raises:
            BigQueryError: 同期に失敗した場合
        """
        if df.empty:
            logger.info("同期対象の家計簿データがありません。")
            return
        try:
            # データの変換
            df_bq = self._transform_household_data(df)

            # 一時テーブルに書き込み
            tmp_table = f"{self._household_table}_tmp"
            job_config = bigquery.LoadJobConfig(
                # スキーマを明示的に指定 (変換後のカラム)
                schema=[
                    bigquery.SchemaField("id", "STRING"),
                    bigquery.SchemaField("target_flag", "BOOLEAN"),
                    bigquery.SchemaField("date", "DATE"),
                    bigquery.SchemaField("description", "STRING"),
                    bigquery.SchemaField("amount", "INTEGER"),
                    bigquery.SchemaField("institution", "STRING"),
                    bigquery.SchemaField("major_category", "STRING"),
                    bigquery.SchemaField("sub_category", "STRING"),
                    bigquery.SchemaField("memo", "STRING"),
                    bigquery.SchemaField("transfer_flag", "BOOLEAN"),
                    bigquery.SchemaField("created_at", "TIMESTAMP"),
                    bigquery.SchemaField("updated_at", "TIMESTAMP"),
                ],
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                clustering_fields=["date", "major_category", "sub_category"],
            )

            self._client.load_table_from_dataframe(
                df_bq, tmp_table, job_config=job_config
            ).result()
            logger.info(
                f"{len(df_bq)}件の家計簿データを一時テーブル "
                f"{tmp_table} にロードしました。"
            )

            # メインテーブルの更新 (MERGE)
            merge_query = f"""
            MERGE `{self._household_table}` T
            USING `{tmp_table}` S
            ON T.id = S.id
            WHEN MATCHED THEN
                UPDATE SET
                    target_flag = S.target_flag,
                    date = S.date,
                    description = S.description,
                    amount = S.amount,
                    institution = S.institution,
                    major_category = S.major_category,
                    sub_category = S.sub_category,
                    memo = S.memo,
                    transfer_flag = S.transfer_flag,
                    updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (id, target_flag, date, description, amount,
                        institution, major_category, sub_category,
                        memo, transfer_flag, created_at, updated_at)
                VALUES (S.id, S.target_flag, S.date, S.description, S.amount,
                        S.institution, S.major_category, S.sub_category,
                        S.memo, S.transfer_flag, S.created_at, S.updated_at)
            """
            self._client.query(merge_query).result()  # result() を待つ
            logger.info(
                f"家計簿データテーブル {self._household_table} をMERGEしました。"
            )

        except Exception as e:
            logger.error(f"家計簿データの同期に失敗しました: {e}", exc_info=True)
            raise BigQueryError(f"家計簿データの同期に失敗しました: {e}") from e

    def _sync_assets_data(self, df: pd.DataFrame) -> None:
        """資産データの同期処理。

        Args:
            df: 同期するデータフレーム

        Raises:
            BigQueryError: 同期に失敗した場合
        """
        if df.empty:
            logger.info("同期対象の資産データがありません。")
            return
        try:
            # データの変換
            df_bq = self._transform_assets_data(df)

            # 一時テーブルに書き込み
            tmp_table = f"{self._assets_table}_tmp"
            job_config = bigquery.LoadJobConfig(
                # スキーマを明示的に指定 (変換後のカラム)
                schema=[
                    bigquery.SchemaField("date", "DATE"),
                    bigquery.SchemaField("category", "STRING"),
                    bigquery.SchemaField("amount", "INTEGER"),
                    bigquery.SchemaField("created_at", "TIMESTAMP"),
                    bigquery.SchemaField("updated_at", "TIMESTAMP"),
                ],
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                # クラスタリング設定を追加
                clustering_fields=["date", "category"],
            )

            self._client.load_table_from_dataframe(
                df_bq, tmp_table, job_config=job_config
            ).result()
            logger.info(
                f"{len(df_bq)}件の資産データを一時テーブル"
                f" {tmp_table} にロードしました。"
            )

            # メインテーブルの更新 (MERGE)
            merge_query = f"""
            MERGE `{self._assets_table}` T
            USING `{tmp_table}` S
            ON T.date = S.date AND T.category = S.category
            WHEN MATCHED THEN
                UPDATE SET
                    amount = S.amount,
                    updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN
                INSERT (date, category, amount, created_at, updated_at)
                VALUES (S.date, S.category, S.amount, S.created_at, S.updated_at)
            """
            self._client.query(merge_query).result()  # result() を待つ
            logger.info(f"資産データテーブル {self._assets_table} をMERGEしました。")

        except Exception as e:
            logger.error(f"資産データの同期に失敗しました: {e}", exc_info=True)
            raise BigQueryError(f"資産データの同期に失敗しました: {e}") from e

    def sync(self) -> None:
        """BigQueryの同期を実行。"""
        try:
            logger.info("BigQuery同期処理を開始します。")
            # スプレッドシートクライアントの取得
            spreadsheet_key = os.getenv("SPREADSHEET_KEY")
            if not spreadsheet_key:
                raise BigQueryError("SPREADSHEET_KEYが環境変数に設定されていません。")

            client = gspread.authorize(self._get_credentials())
            spreadsheet = client.open_by_key(spreadsheet_key)
            logger.info("スプレッドシートへの接続を確立しました。")

            # テーブルが空かどうかを最初に確認
            is_household_empty = self._is_table_empty(self._household_table)
            is_assets_empty = self._is_table_empty(self._assets_table)
            logger.info(
                f"テーブル状態: household_empty={is_household_empty},"
                f"assets_empty={is_assets_empty}"
            )

            df_household_all = None
            df_assets_all = None

            # どちらかのテーブルが空の場合、全データを一度だけ読み込む
            if is_household_empty or is_assets_empty:
                logger.info(
                    "初回同期または片方のテーブルが空のため、"
                    "スプレッドシートから全データを読み込みます。"
                )
                df_household_all, df_assets_all = self._load_all_spreadsheet_data(
                    spreadsheet
                )
                logger.info(
                    f"スプレッドシートから全データ読み込み完了。"
                    f"家計簿: {len(df_household_all)}件, 資産: {len(df_assets_all)}件"
                )

            # 家計簿データの同期
            if is_household_empty:
                if df_household_all is not None:
                    logger.info("家計簿テーブルが空のため、全データを同期します。")
                    self._sync_household_data(df_household_all)
                else:
                    logger.warning(
                        "家計簿テーブルは空ですが、スプレッドシートデータの読み込みに失敗したか、データがありませんでした。"
                    )
            else:
                logger.info(
                    "家計簿テーブルに既存データがあるため、差分データを同期します。"
                )
                today = datetime.datetime.now(datetime.UTC)
                try:
                    household_data = self._load_household_data(today)
                    self._sync_household_data(household_data)
                    logger.info("家計簿の差分データをBigQueryに同期しました。")
                except FileNotFoundError:
                    logger.warning(
                        f"{today.strftime('%Y%m%d')} "
                        "の家計簿CSVファイルが見つかりません。"
                        "差分同期をスキップします。"
                    )
                except Exception as e:
                    logger.error(
                        f"家計簿の差分データ同期中にエラーが発生しました: {e}",
                        exc_info=True,
                    )

            # 資産データの同期
            if is_assets_empty:
                if df_assets_all is not None:
                    logger.info("資産テーブルが空のため、全データを同期します。")
                    self._sync_assets_data(df_assets_all)
                else:
                    logger.warning(
                        "資産テーブルは空ですが、スプレッドシートデータの読み込みに失敗したか、データがありませんでした。"
                    )
            else:
                logger.info(
                    "資産テーブルに既存データがあるため、差分データを同期します。"
                )
                today = datetime.datetime.now(datetime.UTC)
                try:
                    assets_data = self._load_assets_data(today)
                    self._sync_assets_data(assets_data)
                    logger.info("資産の差分データをBigQueryに同期しました。")
                except FileNotFoundError:
                    logger.warning(
                        f"{today.strftime('%Y%m%d')} "
                        "の資産CSVファイルが見つかりません。"
                        "差分同期をスキップします。"
                    )
                except Exception as e:
                    logger.error(
                        f"資産の差分データ同期中にエラーが発生しました: {e}",
                        exc_info=True,
                    )

            logger.info("BigQuery同期処理が正常に完了しました。")

        except Exception as e:
            logger.error(
                f"BigQueryの同期処理全体でエラーが発生しました: {e}",
                exc_info=True,
            )
            raise BigQueryError(f"BigQueryの同期に失敗しました: {e}") from e
