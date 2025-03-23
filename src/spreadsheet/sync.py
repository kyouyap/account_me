"""スプレッドシート同期モジュール。"""

import datetime
import logging
import os
from pathlib import Path
from typing import Optional

import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials

from config.settings import settings
from exceptions.custom_exceptions import SpreadsheetError

logger = logging.getLogger(__name__)


class SpreadsheetSync:
    """Google Spreadsheetとの同期を管理するクラス。"""

    def __init__(self):
        """初期化。"""
        self._client: Optional[gspread.Client] = None

    def _get_client(self) -> gspread.Client:
        """Google Spreadsheet APIクライアントを取得。

        Returns:
            gspread.Client: 認証済みのクライアントインスタンス。

        Raises:
            SpreadsheetError: クライアントの初期化に失敗した場合。
        """
        if not self._client:
            try:
                scope = [
                    "https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive",
                ]
                credentials = ServiceAccountCredentials.from_json_keyfile_name(
                    settings.paths.credentials, scope
                )
                self._client = gspread.authorize(credentials)
            except Exception as e:
                raise SpreadsheetError(
                    f"Google Spreadsheet APIの認証に失敗しました: {e}"
                ) from e
        return self._client

    def _check_env_variables(self) -> None:
        """必要な環境変数が設定されているか確認。

        Raises:
            SpreadsheetError: 必要な環境変数が設定されていない場合。
        """
        if not os.getenv("SPREADSHEET_KEY"):
            raise SpreadsheetError("SPREADSHEET_KEYが環境変数に設定されていません。")

    def _load_household_data(self, date: datetime.datetime) -> pd.DataFrame:
        """家計簿データを読み込む。

        Args:
            date: データの日付。

        Returns:
            pd.DataFrame: 読み込んだデータ。

        Raises:
            SpreadsheetError: データの読み込みに失敗した場合。
        """
        try:
            detail_path = (
                Path(settings.paths.outputs.aggregated_files.detail)
                / f"detail_{date.strftime('%Y%m%d')}.csv"
            )
            df = pd.read_csv(detail_path, encoding="utf-8-sig")
            df["メモ"] = "なし"  # メモ列を追加
            return df
        except Exception as e:
            raise SpreadsheetError(f"家計簿データの読み込みに失敗しました: {e}") from e

    def _load_assets_data(self, date: datetime.datetime) -> pd.DataFrame:
        """資産データを読み込む。

        Args:
            date: データの日付。

        Returns:
            pd.DataFrame: 読み込んだデータ。

        Raises:
            SpreadsheetError: データの読み込みに失敗した場合。
        """
        try:
            assets_path = (
                Path(settings.paths.outputs.aggregated_files.assets)
                / f"assets_{date.strftime('%Y%m%d')}.csv"
            )
            return pd.read_csv(assets_path, encoding="utf-8-sig")
        except Exception as e:
            raise SpreadsheetError(f"資産データの読み込みに失敗しました: {e}") from e

    def _update_household_data(
        self, worksheet: gspread.Worksheet, df: pd.DataFrame
    ) -> None:
        """家計簿データをスプレッドシートに更新。

        Args:
            worksheet: 更新対象のワークシート。
            df: 更新するデータ。

        Raises:
            SpreadsheetError: 更新に失敗した場合。
        """
        try:
            # 既存データの取得
            settings_config = settings.spreadsheet.worksheets.household_data
            df_sps = get_as_dataframe(
                worksheet,
                usecols=[
                    col.col - 1 for col in settings_config.columns
                ],  # 0-based indexing
                header=3,
            )[[col.name for col in settings_config.columns]]
            df_sps.dropna(subset=["ID"], inplace=True)

            # データの結合と加工
            df_sps = pd.concat([df, df_sps], ignore_index=True)
            df_sps["日付"] = pd.to_datetime(df_sps["日付"], format="mixed")
            df_sps["日付"] = df_sps["日付"].dt.strftime("%Y/%m/%d")
            df_sps.sort_values(by="日付", ascending=False, inplace=True)
            df_sps = df_sps.drop_duplicates(subset=["ID"], keep="first")

            # スプレッドシートに書き込み
            set_with_dataframe(
                worksheet,
                df_sps,
                row=settings_config.start_row,
                col=settings_config.columns[0].col,
                include_index=False,
                include_column_header=True,
                resize=True,
            )
        except Exception as e:
            raise SpreadsheetError(f"家計簿データの更新に失敗しました: {e}") from e

    def _update_assets_data(
        self, worksheet: gspread.Worksheet, df: pd.DataFrame
    ) -> None:
        """資産データをスプレッドシートに更新。

        Args:
            worksheet: 更新対象のワークシート。
            df: 更新するデータ。

        Raises:
            SpreadsheetError: 更新に失敗した場合。
        """
        try:
            # 既存データの取得
            settings_config = settings.spreadsheet.worksheets.assets_data
            df_sps = get_as_dataframe(
                worksheet,
                usecols=list(range(len(settings_config.columns))),
                header=3,
            )[[col.name for col in settings_config.columns]].dropna()

            # データの結合と加工
            df_sps = pd.concat([df_sps, df], ignore_index=True)
            df_sps["日付"] = pd.to_datetime(df_sps["日付"], format="mixed")
            df_sps["日付"] = df_sps["日付"].dt.strftime("%Y/%m/%d")
            df_sps.sort_values(by="日付", ascending=True, inplace=True)
            df_sps = df_sps.drop_duplicates(subset=["日付"], keep="last")

            # スプレッドシートに書き込み
            set_with_dataframe(
                worksheet,
                df_sps,
                row=settings_config.start_row,
                col=settings_config.columns[0].col,
                include_index=False,
                include_column_header=True,
                resize=True,
            )
        except Exception as e:
            raise SpreadsheetError(f"資産データの更新に失敗しました: {e}") from e

    def sync(self) -> None:
        """スプレッドシートの同期を実行。"""
        try:
            self._check_env_variables()
            spreadsheet_key = os.getenv("SPREADSHEET_KEY")
            if not spreadsheet_key:
                raise SpreadsheetError(
                    "SPREADSHEET_KEYが環境変数に設定されていません。"
                )

            # スプレッドシートに接続
            client = self._get_client()
            spreadsheet = client.open_by_key(spreadsheet_key)

            # 現在の日付を取得
            current_date = datetime.datetime.now()

            # 家計簿データの同期
            household_data = self._load_household_data(current_date)
            household_worksheet = spreadsheet.worksheet(
                settings.spreadsheet.worksheets.household_data.name
            )
            self._update_household_data(household_worksheet, household_data)
            logger.info("家計簿データを同期しました。")

            # 資産データの同期
            assets_data = self._load_assets_data(current_date)
            assets_worksheet = spreadsheet.worksheet(
                settings.spreadsheet.worksheets.assets_data.name
            )
            self._update_assets_data(assets_worksheet, assets_data)
            logger.info("資産データを同期しました。")

        except Exception as e:
            raise SpreadsheetError(f"スプレッドシートの同期に失敗しました: {e}") from e
