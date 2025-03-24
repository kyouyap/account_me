"""スクレイピング処理を実行するメインモジュール。"""

import datetime
import logging
import os
from pathlib import Path
from typing import List

import pandas as pd

from config.settings import settings
from exceptions.custom_exceptions import MoneyForwardError
from scraper.browser import BrowserManager
from scraper.downloader import FileDownloader

logger = logging.getLogger(__name__)


class MoneyForwardScraper:
    """MoneyForwardのスクレイピングを実行するクラス。"""

    def __init__(self) -> None:
        """スクレイパーの初期化。"""
        self.download_dir = Path(settings.paths.downloads)
        self.browser_manager = BrowserManager()
        self.file_downloader = FileDownloader(self.download_dir)

    def _check_env_variables(self) -> None:
        """必要な環境変数が設定されているか確認します。

        Raises:
            MoneyForwardError: 必要な環境変数が設定されていない場合。
        """
        required_vars = ["EMAIL", "PASSWORD", "SELENIUM_URL"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise MoneyForwardError(
                f"環境変数が設定されていません: {', '.join(missing_vars)}"
            )

    def _clean_directories(self) -> None:
        """作業ディレクトリをクリーンアップします。"""
        try:
            self.file_downloader.clean_download_dir()
        except OSError as e:
            logger.error(
                "ダウンロードディレクトリのクリーンアップに失敗しました: %s", e
            )

        for directory in [
            Path(settings.paths.outputs.aggregated_files.detail),
            Path(settings.paths.outputs.aggregated_files.assets),
        ]:
            try:
                if directory.exists():
                    for file in directory.glob("*"):
                        try:
                            file.unlink()
                        except OSError as e:
                            logger.error("ファイルの削除に失敗しました %s: %s", file, e)
                else:
                    directory.mkdir(parents=True)
            except OSError as e:
                logger.error("ディレクトリの操作に失敗しました %s: %s", directory, e)

    def _read_csv_with_encoding(self, file_path: Path) -> pd.DataFrame:
        """複数のエンコーディングを試行してCSVファイルを読み込みます。

        Args:
            file_path: 読み込むCSVファイルのパス。

        Returns:
            pd.DataFrame: 読み込んだデータフレーム。

        Raises:
            MoneyForwardError: すべてのエンコーディングで読み込みに失敗した場合。
        """
        # ファイルサイズチェック
        if file_path.stat().st_size == 0:
            raise MoneyForwardError("CSVファイルが空です。")

        encodings = ["utf-8", "shift-jis", "cp932"]
        errors = []
        decode_errors = []

        for encoding in encodings:
            try:
                logger.info(
                    "ファイル '%s' をエンコーディング '%s' で読み込み試行中",
                    file_path,
                    encoding,
                )
                df = pd.read_csv(file_path, encoding=encoding)
                if df.empty:
                    logger.warning("CSVファイルにデータがありません")
                    continue

                logger.info(
                    "ファイル '%s' をエンコーディング '%s' で読み込みに成功",
                    file_path,
                    encoding,
                )
                return df
            except UnicodeDecodeError as e:
                logger.warning(
                    "エンコーディング '%s' での読み込みに失敗: %s",
                    encoding,
                    str(e),
                )
                decode_errors.append(f"{encoding}: {str(e)}")
            except Exception as e:
                logger.error(
                    "ファイル '%s' の読み込み中に予期せぬエラーが発生: %s",
                    file_path,
                    str(e),
                )
                errors.append(f"{encoding}: {str(e)}")

        # エラー内容に応じたメッセージを表示
        if decode_errors:
            error_details = "\n".join(decode_errors)
            raise MoneyForwardError(
                f"CSVファイル '{file_path}' を読み込めませんでした。対応していないエンコーディングの可能性があります。\n詳細:\n{error_details}"
            )
        elif errors:
            error_details = "\n".join(errors)
            raise MoneyForwardError(
                f"CSVファイルの読み込みに失敗しました: \n{error_details}"
            )
        else:
            raise MoneyForwardError(
                f"CSVファイル '{file_path}' の読み込みに失敗しました: データが空です"
            )

    def _aggregate_csv_files(self, output_path: Path) -> None:
        """CSVファイルを集約します。

        Args:
            output_path: 出力ファイルのパス。

        Raises:
            MoneyForwardError: CSVファイルの集約に失敗した場合。
        """
        try:
            # CSVファイルを読み込んで結合
            all_dfs: List[pd.DataFrame] = []
            csv_files = list(self.download_dir.glob("*.csv"))
            logger.info("集約対象のCSVファイル数: %d", len(csv_files))

            for file_path in csv_files:
                logger.info("ファイル '%s' の処理を開始", file_path)
                df = self._read_csv_with_encoding(file_path)
                if "金額（円）" in df.columns and "保有金融機関" in df.columns:
                    # アメリカン・エキスプレスカードの金額を半額に
                    for rule in settings.moneyforward.special_rules:
                        if rule.action == "divide_amount":
                            # 警告を防ぐため、明示的に数値型に変換
                            mask = df["保有金融機関"] == rule.institution
                            df.loc[mask, "金額（円）"] = (
                                df.loc[mask, "金額（円）"].astype(float) / rule.value
                            )
                all_dfs.append(df)

            if all_dfs:
                # データを結合して重複を削除
                final_df = pd.concat(all_dfs).drop_duplicates().reset_index(drop=True)

                # ディレクトリが存在しない場合は作成
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # CSVファイルとして保存
                final_df.to_csv(output_path, index=False, encoding="utf-8-sig")
                logger.info(
                    "CSVファイルを集約しました: %s（レコード数: %d）",
                    output_path,
                    len(final_df),
                )
            else:
                raise MoneyForwardError("集約するCSVファイルがありません。")

        except Exception as e:
            raise MoneyForwardError(f"CSVファイルの集約に失敗しました: {e}") from e

    def scrape(self) -> None:
        """スクレイピングを実行します。"""
        try:
            self._check_env_variables()
            self._clean_directories()

            current_date = datetime.datetime.now().strftime("%Y%m%d")
            email = os.getenv("EMAIL")
            password = os.getenv("PASSWORD")

            if not email or not password:
                raise MoneyForwardError(
                    "EMAIL/PASSWORDが環境変数に設定されていません。"
                )

            with self.browser_manager as browser:
                # ログインしてリンクを取得
                browser.login(email, password)
                links = browser.get_links_for_download(
                    f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.accounts}"
                )
                logger.info("ダウンロードリンクを取得しました: %d件", len(links))

                # アカウントページからのダウンロード
                self.file_downloader.download_from_links(browser.driver, links)
                detail_output = (
                    Path(settings.paths.outputs.aggregated_files.detail)
                    / f"detail_{current_date}.csv"
                )
                self._aggregate_csv_files(detail_output)

                # 履歴ページからのダウンロード
                self.file_downloader.clean_download_dir()
                history_links = [
                    f"{settings.moneyforward.base_url}{settings.moneyforward.endpoints.history}"
                ]
                self.file_downloader.download_from_links(browser.driver, history_links)
                assets_output = (
                    Path(settings.paths.outputs.aggregated_files.assets)
                    / f"assets_{current_date}.csv"
                )
                self._aggregate_csv_files(assets_output)

            self.file_downloader.clean_download_dir()
            logger.info("スクレイピングが完了しました。")

        except Exception as e:
            self.file_downloader.clean_download_dir()
            raise MoneyForwardError(f"スクレイピングに失敗しました: {e}") from e
